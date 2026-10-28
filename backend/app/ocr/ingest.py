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

import gc
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

from .. import config
from ..gpu import big_slot
from ..rag import search as rag_search
from ..rag.chunker import Section, chunk_section, sections_from_toc
from . import digest, figures
from .arbiter import choose
from .paths import UNLIMITED_BATCH, UNLIMITED_SCRIPTS_DISABLED
from .tesseract import dpi_for as tess_dpi, ocr_image, ocr_pdf, tess_langs
from .markdown import page_markdown
from .triage import classify_page, read_toc, render_png
from .types import EngineResult, PageRecord, TocEntry
from .unlimited import OcrOOM

log = logging.getLogger(__name__)

MAX_BYTES = 2 * 1024 ** 3
MAX_PAGES = 1000
UNLIMITED_DPI = 200
FRONT_PAGES = 15         # scanned books without bookmarks: OCR their contents pages first
FOCUS_MATCH = 80
FORMAT = 2               # PageRecord.fmt of a digital page stored as Markdown

# The progress bar of an upload is one continuous run, split into bands that follow the real work:
READ_HI = 0.30           # 0.02 - 0.30   reading every page (text layer to Markdown, or marking it for OCR), one step per page
OCR_HI = 0.80            # 0.30 - 0.80   OCR of scanned pages, one step per page (skipped when the PDF has none)
INDEX_HI = 0.97          # then          indexing section by section; the last steps look for pictures

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


_page_lock = threading.Lock()


def update_page(sha: str, page: int, change: Callable[[PageRecord], None]) -> PageRecord | None:
    """Load the page's record fresh from disk, change it, save it. The OCR upgrade and the figure pass write to the same files from two
    threads; going through here (under one lock, from a fresh copy) means neither overwrites what the other just stored."""
    with _page_lock:
        rec = load_page(sha, page)
        if rec is None:
            return None
        change(rec)
        save_page(sha, rec)
        return rec


def _write_info(sha: str, info: dict) -> None:
    (upload_dir(sha) / "info.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")


def read_info(sha: str) -> dict | None:
    p = upload_dir(sha) / "info.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


_JUNK_TITLE = re.compile(r"(?i)^(microsoft\b|untitled\b|document\d*$)|\.(docx?|pptx?|odt|pdf|tex|indd)$")


def _title(doc: fitz.Document, path: Path, sha: str) -> str:
    """The PDF's own title if it is a real one, else the uploaded file's name (saved by the upload route)."""
    meta = ((doc.metadata or {}).get("title") or "").strip()
    if meta and not _JUNK_TITLE.search(meta):
        return meta
    name = upload_dir(sha) / "name.txt"
    if name.exists() and name.read_text(encoding="utf-8").strip():
        return name.read_text(encoding="utf-8").strip()
    return path.stem


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
    recs = [records[p] for p in range(first, last + 1) if p in records and records[p].indexed_text().strip()]
    col.delete_section(sha, idx)
    if not recs:
        return
    engines = "+".join(sorted({r.engine for r in recs}))
    chunks = chunk_section({**meta, "engine": engines}, section,
                           [(r.page, r.indexed_text(), r.low_confidence) for r in recs], count)
    col.add(chunks)


def _tesseract_pass(src: Path, doc: fitz.Document, todo: list[int], langs: str, dpi: int, records: dict[int, PageRecord],
                    sha: str, on_page: Callable[[int], None]) -> None:
    """Read `todo` (already in priority order) with Tesseract; calls on_page(p) as each page is saved."""

    def apply(p: int, res: EngineResult) -> None:
        rec = records[p]
        rec.text = rec.tess_text = res.text
        rec.tess_conf = res.confidence
        rec.engine, rec.status = "tesseract", "tesseract"
        save_page(sha, rec)
        on_page(p)

    def fail(p: int, err: Exception) -> None:
        log.warning("Page %d of %s failed Tesseract: %s", p, sha, err)
        records[p].status = "failed"
        save_page(sha, records[p])
        on_page(p)

    retry: list[int] = []
    for p, res in ocr_pdf(str(src), todo, langs, dpi):
        if isinstance(res, Exception):
            retry.append(p)                              # a crashed worker can kill its neighbours' tasks too
        else:
            apply(p, res)
    for p in retry:                                      # one more try, alone and in this process
        try:
            apply(p, ocr_image(render_png(doc[p - 1], dpi), langs))
        except Exception as e:  # noqa: BLE001
            fail(p, e)


def _read_order(todo: list[int], focus_pages: list[int], front_pages: list[int]) -> list[int]:
    """Pages the student asked about first (so their lesson can start), then the contents pages, then the rest."""
    want = set(todo)
    out, seen = [], set()
    for p in [*focus_pages, *front_pages, *sorted(want)]:
        if p in want and p not in seen:
            seen.add(p)
            out.append(p)
    return out


# ---------------------------------------------------------------- pass 1

def ingest_pdf(path: Path, lang: str | None, focus: str | None, progress: Progress, *,
               unlimited=None, embedder=None, notes: bool = True, digester=None, describer=None) -> dict:
    path = Path(path)
    n = validate_pdf(path)
    sha = file_sha(path)
    d = upload_dir(sha)
    d.mkdir(parents=True, exist_ok=True)
    src = d / "source.pdf"
    if not src.exists():
        shutil.copyfile(path, src)
    fast = None
    if embedder is None:
        from ..rag.embed import gpu_embedder, shared_embedder
        embedder = shared_embedder()
        fast = gpu_embedder()                    # pass 1 only: the GPU is idle and every CPU core belongs to Tesseract
    col = rag_search.writable_collection(f"upload:{sha}", fast or embedder)

    with fitz.open(src) as doc:
        toc = read_toc(doc)
        sections = sections_from_toc(n, toc)
        title = _title(doc, path, sha)
        meta = {"doc_id": sha, "title": title, "lang": lang or "", "source": "upload", "license": "",
                "url": f"upload:{sha}"}
        progress("Reading the PDF", 0.02)

        records: dict[int, PageRecord] = {}
        for p in range(1, n + 1):
            rec = load_page(sha, p)
            if rec is not None and rec.kind == "digital" and rec.fmt < FORMAT:
                rec = None                                       # stored as plain text by an older version: redo it as Markdown (cheap)
            if rec is None:
                page = doc[p - 1]
                if classify_page(page, lang) == "digital":
                    rec = PageRecord(p, "digital", page_markdown(doc, p - 1), "text-layer", status="final", fmt=FORMAT)
                else:
                    rec = PageRecord(p, "scanned")
                save_page(sha, rec)
            records[p] = rec
            progress(f"Reading page {p} of {n}", 0.02 + (READ_HI - 0.02) * p / n)

        scanned = [p for p in records if records[p].kind == "scanned"]
        index_lo = OCR_HI if scanned else READ_HI              # no scanned pages: no OCR band, indexing follows reading directly
        todo = [p for p in scanned if records[p].status == "pending"]
        done = len(scanned) - len(todo)
        prev = read_info(sha) or {}
        indexed = set(prev.get("indexed_sections", [])) if not todo else set()
        langs = tess_langs(lang)
        early_focus = resolve_focus(toc, n, focus)

        # Study notes are written 30 pages at a time, each window the moment its last page has been read.
        pages_text = {p: r.text for p, r in records.items()}
        tracker = digest.WindowTracker(d, n, set(todo), pages_text, digester) if notes else None

        if todo:
            # A section is indexed the moment its last scanned page is read, so the student's chapter becomes
            # searchable first and a section is never re-embedded again and again while its pages trickle in.
            waiting = {s[0]: {p for p in todo if _section_of(sections, p) is s} for s in sections}

            def on_page(p: int) -> None:                 # called from this thread only, as results stream in
                nonlocal done
                s = _section_of(sections, p)
                done += 1
                pages_text[p] = records[p].text
                if tracker:
                    tracker.page_done(p)
                waiting[s[0]].discard(p)
                if not waiting[s[0]]:
                    _reindex(col, sha, meta, s, records, embedder.count_tokens)
                    indexed.add(s[0])
                progress(f"OCR {done} / {len(scanned)} pages (Tesseract)", READ_HI + (OCR_HI - READ_HI) * done / max(len(scanned), 1))

            front = [] if toc else list(range(1, min(FRONT_PAGES, n) + 1))
            _tesseract_pass(src, doc, _read_order(todo, early_focus, front), langs, tess_dpi(lang), records, sha, on_page)
        elif scanned:
            progress(f"OCR {done} / {len(scanned)} pages (cached)", OCR_HI)       # (a PDF with no scanned pages has no OCR band at all)

        rest = [s for s in sections if s[0] not in indexed]
        for k, s in enumerate(rest, 1):
            _reindex(col, sha, meta, s, records, embedder.count_tokens)
            indexed.add(s[0])
            progress(f"Indexing section {k} of {len(rest)}", index_lo + (INDEX_HI - 0.01 - index_lo) * k / len(rest))
        progress("Looking for pictures", INDEX_HI - 0.01)
        figs = figures.find(doc) if describer is not False and (describer is not None or config.PDF_FIGURES) else []

    if fast is not None:                         # pass 1 is done: hand the collection back to the CPU embedder, free the GPU
        col.embedder = embedder
        del fast
        gc.collect()
        from ..rag.embed import release_gpu
        release_gpu()

    focus_pages = resolve_focus(toc, n, focus)
    if focus and not focus_pages:
        hit_ids = [cid for cid, _ in col.keyword(focus, 10)]
        focus_pages = sorted({p for c in col.get(hit_ids) for p in range(c.page_start, c.page_end + 1)})

    info = {"sha": sha, "title": title, "pages": n, "digital": n - len(scanned), "scanned": len(scanned),
            "lang": lang, "toc": [t.__dict__ for t in toc], "focus_pages": focus_pages,
            "indexed_sections": sorted(indexed), "figures": len(figs)}
    _write_info(sha, info)
    progress("PDF is searchable", 1.0)

    if unlimited is not False and lang not in UNLIMITED_SCRIPTS_DISABLED:
        toc_pages = [] if toc else list(range(1, min(FRONT_PAGES, n) + 1))
        conf = {p: records[p].tess_conf or 0.0 for p in scanned if records[p].status != "failed"}
        order = [p for p in priority_order(n, toc_pages, focus_pages, conf)
                 if records[p].kind == "scanned" and records[p].status != "final"]
        if order:
            _start_upgrade(sha, src, sections, meta, lang or "en", order, unlimited, embedder)
    if figs:
        _start_figures(sha, src, sections, meta, figures.order(figs, focus_pages), embedder, describer)
    return {k: v for k, v in info.items() if k != "indexed_sections"}


# ---------------------------------------------------------------- figures: what the pictures in the PDF show (llava, in the background)

_fig_threads: dict[str, threading.Thread] = {}


def _fig_state(sha: str) -> dict:
    p = upload_dir(sha) / "figures.json"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"found": 0, "described": 0, "state": "none"}


def _write_fig_state(sha: str, **kw) -> None:
    (upload_dir(sha) / "figures.json").write_text(json.dumps({**_fig_state(sha), **kw}), encoding="utf-8")


def _start_figures(sha, src, sections, meta, order, embedder, describer) -> None:
    with _up_lock:
        t = _fig_threads.get(sha)
        if t and t.is_alive():
            return
        _write_fig_state(sha, found=len(order), described=0, state="describing")
        t = threading.Thread(target=_describe_figures, name=f"figures-{sha}", daemon=True, args=(sha, src, sections, meta, order, embedder, describer))
        _fig_threads[sha] = t
        t.start()


def _describe_figures(sha, src, sections, meta, order, embedder, describer) -> None:
    """One figure at a time, in the order the student needs them. Holds the big GPU slot like the OCR upgrade does and steps aside whenever a
    lesson needs the language model; every description is saved on its page and that section is searched again with it."""
    from .. import vision
    describe = describer or vision.describe_figure
    col = rag_search.writable_collection(f"upload:{sha}", embedder)
    done, i = 0, 0
    state = "done"
    try:
        with fitz.open(src) as doc:
            while i < len(order):
                with big_slot.hold("vision"):
                    while i < len(order) and not big_slot.should_yield("vision"):
                        f = order[i]
                        try:
                            caption = describe(figures.png_of(doc, f["xref"]))
                        except vision.VisionUnavailable as e:
                            log.warning("PDF figures of %s skipped: %s", sha, e)
                            state, i = "unavailable", len(order)
                            break
                        except Exception as e:  # noqa: BLE001  one picture that cannot be read does not stop the others
                            log.warning("figure %s of %s could not be described: %s", f["xref"], sha, e)
                            caption = ""
                        i += 1
                        if not caption:
                            continue
                        done += 1
                        rec = update_page(sha, f["page"], lambda r, x=f["xref"], c=caption: r.figures.append({"xref": x, "caption": c}))
                        if rec is not None:
                            section = _section_of(sections, f["page"])
                            records = {p: load_page(sha, p) for p in range(section[2], section[3] + 1)}
                            _reindex(col, sha, meta, section, {p: r for p, r in records.items() if r}, embedder.count_tokens)
                        _write_fig_state(sha, described=done)
    except Exception:
        log.exception("describing the figures of %s stopped", sha)
        state = "error"
    finally:
        _write_fig_state(sha, state=state, described=done)


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
        threads = list(_upgraders.values()) + list(_fig_threads.values())
    for t in threads:
        t.join(timeout)
    return not any(t.is_alive() for t in threads)


UNLIMITED_ON = os.getenv("UNLIMITED_OCR", "1") != "0"
UNLIMITED_MIN_FREE_GB = float(os.getenv("UNLIMITED_MIN_FREE_GB", "7.0"))      # the model needs about 6.7 GB of the card


def _upgrade(sha, src, sections, meta, lang, order, unlimited, embedder) -> None:
    from .. import config
    free = config.gpu_free_gb()
    if not UNLIMITED_ON or (unlimited is None and (free is None or free < UNLIMITED_MIN_FREE_GB)):
        # It cannot fit next to the language model: loading it anyway failed page after page, each try leaving memory behind, until the backend died.
        log.info("Unlimited-OCR skipped for %s (%s): Tesseract's text is kept", sha, "switched off" if not UNLIMITED_ON else f"{free or 0:.1f} GB free")
        return
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
                            if "out of memory" in str(e).lower():          # it will not fit now: free what was loaded and stop, never retry page after page
                                unlimited.unload()
                                log.warning("Unlimited-OCR stopped for %s: not enough GPU memory; Tesseract's text is kept", sha)
                                return
                            results = [None] * len(pages)
                        for p, res in zip(pages, results):
                            rec = records[p]
                            tess = EngineResult("tesseract", rec.tess_text, rec.tess_conf)
                            dec = choose(tess, res, lang, lexicon)

                            def upgrade(r, res=res, dec=dec):                  # on a fresh copy of the page: figures stored meanwhile stay
                                r.uni_text = res.text if res else ""
                                r.text, r.engine = dec.text, dec.engine
                                r.agreement, r.low_confidence = dec.agreement, dec.low_confidence
                                r.status = "final" if r.text.strip() else "failed"

                            records[p] = update_page(sha, p, upgrade) or rec
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
        "figures": _fig_state(sha),
        "notes": digest.progress(upload_dir(sha), info["pages"]),
    }
