"""Uploaded PDF -> searchable collection, using both OCR engines.

Pass 1 (synchronous, inside the upload job): digital pages use their text layer; scanned pages go
through Tesseract in a process pool. Each batch is indexed as soon as it finishes, so the PDF is
searchable within minutes, even for a 1,000-page scan.

Pass 2 (background thread): Unlimited-OCR re-reads scanned pages in priority order (front matter,
the pages the student asked about, the worst Tesseract pages, then the rest). The arbiter keeps the
better read per page, and that page's section is re-indexed. Pass 2 holds gpu.big_slot and steps
aside between batches whenever a lesson needs the LLM.

Everything is cached per page under data/uploads/<sha>/pages/, so re-uploads and restarts resume.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import threading
from pathlib import Path
from typing import Callable

import fitz
from rapidfuzz import fuzz

from ..gpu import big_slot
from ..rag import search as rag_search
from ..rag.chunker import Section, chunk_section, sections_from_toc
from .arbiter import choose
from .paths import UNLIMITED_BATCH, UNLIMITED_SCRIPTS_DISABLED
from .tesseract import ocr_image, ocr_many, tess_langs
from .triage import classify_page, read_toc, render_png
from .types import EngineResult, PageRecord, TocEntry
from .unlimited import OcrOOM

log = logging.getLogger(__name__)

MAX_BYTES = 2 * 1024 ** 3
MAX_PAGES = 5000
TESS_DPI = 300
UNLIMITED_DPI = 200
TESS_BATCH = 32
FRONT_PAGES = 15         # scanned books without bookmarks: OCR their contents pages first
FOCUS_MATCH = 80

Progress = Callable[[str, float], None]


class UploadError(ValueError):
    """A PDF we refuse, with a message fit to show the student."""


# ---------------------------------------------------------------- files and cache

def file_sha(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()[:16]


def upload_dir(sha: str) -> Path:
    return rag_search.UPLOADS_DIR / sha


def load_page(sha: str, page: int) -> PageRecord | None:
    p = upload_dir(sha) / "pages" / f"{page}.json"
    return PageRecord.from_json(json.loads(p.read_text(encoding="utf-8"))) if p.exists() else None


def save_page(sha: str, rec: PageRecord) -> None:
    d = upload_dir(sha) / "pages"
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / f"{rec.page}.json.tmp"
    tmp.write_text(json.dumps(rec.to_json(), ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, d / f"{rec.page}.json")


def _write_info(sha: str, info: dict) -> None:
    (upload_dir(sha) / "info.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")


def read_info(sha: str) -> dict | None:
    p = upload_dir(sha) / "info.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def validate_pdf(path: Path) -> int:
    if path.stat().st_size > MAX_BYTES:
        raise UploadError("PDF is larger than 2 GB")
    try:
        doc = fitz.open(path)
    except Exception:
        raise UploadError("Not a readable PDF") from None
    with doc:
        if not doc.is_pdf:
            raise UploadError("Not a readable PDF")
        if doc.needs_pass:
            raise UploadError("PDF is password-protected")
        n = doc.page_count
    if n == 0:
        raise UploadError("Not a readable PDF")
    if n > MAX_PAGES:
        raise UploadError(f"PDF has more than {MAX_PAGES:,} pages")
    return n


# ---------------------------------------------------------------- what to read first

def resolve_focus(toc: list[TocEntry], n_pages: int, focus: str | None) -> list[int]:
    """Pages a request points at: "pages 120-135", "page 7", "chapter 4", or a TOC title."""
    if not focus:
        return []
    f = focus.lower()
    clip = lambda a, b: list(range(max(a, 1), min(b, n_pages) + 1))  # noqa: E731
    if m := re.search(r"pages?\s+(\d+)\s*(?:-|–|to)\s*(\d+)", f):
        return clip(int(m[1]), int(m[2]))
    if m := re.search(r"page\s+(\d+)", f):
        return clip(int(m[1]), int(m[1]))
    chapters = [s for s in sections_from_toc(n_pages, toc) if s[1] != "Front matter"] if toc else []
    if m := re.search(r"chapter\s+(\d+)", f):
        i = int(m[1]) - 1
        return clip(chapters[i][2], chapters[i][3]) if 0 <= i < len(chapters) else []
    best = max(chapters, key=lambda s: fuzz.partial_ratio(f, s[1].lower()), default=None)
    if best and fuzz.partial_ratio(f, best[1].lower()) >= FOCUS_MATCH:
        return clip(best[2], best[3])
    return []


def priority_order(n_pages: int, toc_pages: list[int], focus_pages: list[int],
                   tess_conf: dict[int, float]) -> list[int]:
    order: list[int] = []
    seen: set[int] = set()

    def add(p: int) -> None:
        if 1 <= p <= n_pages and p not in seen:
            seen.add(p)
            order.append(p)

    for p in toc_pages:
        add(p)
    for p in focus_pages:
        add(p)
    for p in sorted(tess_conf, key=lambda q: (tess_conf[q], q)):
        add(p)
    for p in range(1, n_pages + 1):
        add(p)
    return order


# ---------------------------------------------------------------- indexing

def _section_of(sections: list[Section], page: int) -> Section:
    for s in sections:
        if s[2] <= page <= s[3]:
            return s
    return sections[-1]


def _reindex(col, sha: str, meta: dict, section: Section, records: dict[int, PageRecord], count) -> None:
    idx, _, first, last = section
    recs = [records[p] for p in range(first, last + 1) if p in records and records[p].text.strip()]
    col.delete_section(sha, idx)
    if not recs:
        return
    engines = "+".join(sorted({r.engine for r in recs}))
    chunks = chunk_section({**meta, "engine": engines}, section,
                           [(r.page, r.text, r.low_confidence) for r in recs], count)
    col.add(chunks)


def _render_for_tesseract(doc: fitz.Document, page: int) -> bytes:
    return render_png(doc[page - 1], TESS_DPI)


def _tesseract_batch(doc, batch: list[int], langs: str, records: dict[int, PageRecord], sha: str) -> None:
    items, done = [], set()
    for p in batch:
        try:
            items.append((p, _render_for_tesseract(doc, p)))
        except Exception as e:
            log.warning("Page %d of %s could not be rendered: %s", p, sha, e)
            records[p].status = "failed"
            save_page(sha, records[p])
            done.add(p)

    def apply(p: int, res: EngineResult) -> None:
        rec = records[p]
        rec.text = rec.tess_text = res.text
        rec.tess_conf = res.confidence
        rec.engine, rec.status = "tesseract", "tesseract"
        save_page(sha, rec)
        done.add(p)

    try:
        for p, res in ocr_many(items, langs):
            apply(p, res)
    except Exception as e:
        # One bad page aborts the pool's stream: finish the rest one by one so only that page fails.
        log.warning("Tesseract batch failed (%s); retrying its pages one at a time", e)
        for p, png in items:
            if p in done:
                continue
            try:
                apply(p, ocr_image(png, langs))
            except Exception as e2:
                log.warning("Page %d of %s failed Tesseract: %s", p, sha, e2)
                records[p].status = "failed"
                save_page(sha, records[p])
                done.add(p)


# ---------------------------------------------------------------- pass 1

def ingest_pdf(path: Path, lang: str | None, focus: str | None, progress: Progress, *,
               unlimited=None, embedder=None) -> dict:
    path = Path(path)
    n = validate_pdf(path)
    sha = file_sha(path)
    d = upload_dir(sha)
    d.mkdir(parents=True, exist_ok=True)
    src = d / "source.pdf"
    if not src.exists():
        shutil.copyfile(path, src)
    if embedder is None:
        from ..rag.embed import shared_embedder
        embedder = shared_embedder()
    col = rag_search.writable_collection(f"upload:{sha}", embedder)

    with fitz.open(src) as doc:
        toc = read_toc(doc)
        sections = sections_from_toc(n, toc)
        title = (doc.metadata or {}).get("title") or path.stem
        meta = {"doc_id": sha, "title": title, "lang": lang or "", "source": "upload", "license": "",
                "url": f"upload:{sha}"}
        progress("Reading the PDF", 0.02)

        records: dict[int, PageRecord] = {}
        for p in range(1, n + 1):
            rec = load_page(sha, p)
            if rec is None:
                page = doc[p - 1]
                if classify_page(page) == "digital":
                    text = page.get_text("text").strip()
                    rec = PageRecord(p, "digital", text, "text-layer", status="final")
                else:
                    rec = PageRecord(p, "scanned")
                save_page(sha, rec)
            records[p] = rec

        scanned = [p for p in records if records[p].kind == "scanned"]
        todo = [p for p in scanned if records[p].status == "pending"]
        done = len(scanned) - len(todo)
        prev = read_info(sha) or {}
        indexed = set(prev.get("indexed_sections", [])) if not todo else set()
        langs = tess_langs(lang)

        for i in range(0, len(todo), TESS_BATCH):
            batch = todo[i:i + TESS_BATCH]
            _tesseract_batch(doc, batch, langs, records, sha)
            done += len(batch)
            progress(f"OCR {done} / {len(scanned)} pages (Tesseract)", 0.05 + 0.85 * done / max(len(scanned), 1))
            for s in {_section_of(sections, p) for p in batch}:
                _reindex(col, sha, meta, s, records, embedder.count_tokens)
                indexed.add(s[0])
        if not todo:
            progress(f"OCR {done} / {len(scanned)} pages (cached)", 0.9)

        for s in sections:
            if s[0] not in indexed:
                _reindex(col, sha, meta, s, records, embedder.count_tokens)
                indexed.add(s[0])

    focus_pages = resolve_focus(toc, n, focus)
    if focus and not focus_pages:
        hit_ids = [cid for cid, _ in col.keyword(focus, 10)]
        focus_pages = sorted({p for c in col.get(hit_ids) for p in range(c.page_start, c.page_end + 1)})

    info = {"sha": sha, "title": title, "pages": n, "digital": n - len(scanned), "scanned": len(scanned),
            "lang": lang, "toc": [t.__dict__ for t in toc], "focus_pages": focus_pages,
            "indexed_sections": sorted(indexed)}
    _write_info(sha, info)
    progress("PDF is searchable", 1.0)

    if unlimited is not False and lang not in UNLIMITED_SCRIPTS_DISABLED:
        toc_pages = [] if toc else list(range(1, min(FRONT_PAGES, n) + 1))
        conf = {p: records[p].tess_conf or 0.0 for p in scanned if records[p].status != "failed"}
        order = [p for p in priority_order(n, toc_pages, focus_pages, conf)
                 if records[p].kind == "scanned" and records[p].status != "final"]
        if order:
            _start_upgrade(sha, src, sections, meta, lang or "en", order, unlimited, embedder)
    return {k: v for k, v in info.items() if k != "indexed_sections"}


# ---------------------------------------------------------------- pass 2

_upgraders: dict[str, threading.Thread] = {}
_up_lock = threading.Lock()
_lexicons: dict[str, set[str] | None] = {}


def _lexicon(lang: str) -> set[str] | None:
    if lang not in _lexicons:
        p = rag_search.LIBRARY_DIR / f"lexicon_{lang}.txt"
        _lexicons[lang] = set(p.read_text(encoding="utf-8").split()) if p.exists() else None
    return _lexicons[lang]


def _start_upgrade(sha, src, sections, meta, lang, order, unlimited, embedder) -> None:
    with _up_lock:
        t = _upgraders.get(sha)
        if t and t.is_alive():
            return
        t = threading.Thread(target=_upgrade, name=f"uocr-{sha}", daemon=True,
                             args=(sha, src, sections, meta, lang, order, unlimited, embedder))
        _upgraders[sha] = t
        t.start()


def wait_for_upgrades(timeout: float | None = None) -> bool:
    """Join running pass-2 threads (tests, shutdown). True if all finished."""
    with _up_lock:
        threads = list(_upgraders.values())
    for t in threads:
        t.join(timeout)
    return not any(t.is_alive() for t in threads)


def _upgrade(sha, src, sections, meta, lang, order, unlimited, embedder) -> None:
    if unlimited is None:
        from .unlimited import UnlimitedOCR
        unlimited = UnlimitedOCR()
    col = rag_search.writable_collection(f"upload:{sha}", embedder)
    records = {p: load_page(sha, p) for p in range(1, max(order) + 1)}
    lexicon = _lexicon(lang)
    batch, i = UNLIMITED_BATCH, 0
    try:
        with fitz.open(src) as doc:
            while i < len(order):
                with big_slot.hold("ocr"):
                    while i < len(order) and not big_slot.should_yield("ocr"):
                        pages = order[i:i + batch]
                        try:
                            results = unlimited.ocr([render_png(doc[p - 1], UNLIMITED_DPI) for p in pages])
                        except OcrOOM:
                            if batch > 1:
                                batch = max(1, batch // 2)
                                continue
                            results = [None]          # keep Tesseract's text for this page
                        except Exception as e:
                            log.warning("Unlimited-OCR failed on %s pages %s: %s", sha, pages, e)
                            results = [None] * len(pages)
                        for p, res in zip(pages, results):
                            rec = records[p]
                            tess = EngineResult("tesseract", rec.tess_text, rec.tess_conf)
                            dec = choose(tess, res, lang, lexicon)
                            rec.uni_text = res.text if res else ""
                            rec.text, rec.engine = dec.text, dec.engine
                            rec.agreement, rec.low_confidence = dec.agreement, dec.low_confidence
                            rec.status = "final" if rec.text.strip() else "failed"
                            save_page(sha, rec)
                        for s in {_section_of(sections, p) for p in pages[:len(results)]}:
                            _reindex(col, sha, meta, s, records, embedder.count_tokens)
                        i += len(results)
                    unlimited.unload()                # step aside for the LLM, or finished
    except Exception:
        log.exception("OCR upgrade of %s stopped", sha)
    finally:
        unlimited.unload()


# ---------------------------------------------------------------- status

def upload_status(sha: str) -> dict | None:
    info = read_info(sha)
    if info is None:
        return None
    recs = [load_page(sha, p) for p in range(1, info["pages"] + 1)]
    scanned = [r for r in recs if r and r.kind == "scanned"]
    with _up_lock:
        t = _upgraders.get(sha)
        running = bool(t and t.is_alive())
    pending = any(r.status == "pending" for r in scanned)
    return {
        "sha": sha, "title": info["title"], "pages": info["pages"],
        "digital": info["digital"], "scanned": info["scanned"],
        "tesseract_done": sum(r.status in ("tesseract", "final") and bool(r.tess_text) for r in scanned),
        "unlimited_done": sum(r.status == "final" for r in scanned),
        "failed": sum(r.status == "failed" for r in scanned),
        "low_confidence": sum(r.low_confidence for r in scanned),
        "state": "ocr" if pending else "upgrading" if running else "ready",
    }
