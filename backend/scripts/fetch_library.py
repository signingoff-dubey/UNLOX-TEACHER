"""Download the offline library sources into data/library/raw/<source>.jsonl (run while online).

    python scripts/fetch_library.py --source vital|simple|indic|ncert|openstax|archive [--limit N]

Each line: {"doc_id", "source", "title", "lang", "url", "license", "text"}. Resumable: doc_ids already
in the JSONL are skipped. data/library/manifest.json records counts and sha256 per source.

Wikipedia comes from the wikimedia/wikipedia parquet dump (20231101), downloaded beforehand with:
    hf download wikimedia/wikipedia --repo-type dataset --local-dir data/library/wikipedia \\
        --include "20231101.en/*" --include "20231101.simple/*" --include "20231101.hi/*" ...
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
import time
import zipfile
from pathlib import Path
from typing import Iterator

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.rag.paths import LIBRARY_DIR  # noqa: E402

RAW = LIBRARY_DIR / "raw"
WIKI = LIBRARY_DIR / "wikipedia"
INDIC = ["hi", "te", "ta", "ml", "mr", "kn", "bn", "gu"]
UA = {"User-Agent": "chanakya-library/1.0 (offline education hackathon project)"}
WIKI_LICENSE = "CC BY-SA 4.0"
ARCHIVE_CAP_BYTES = 5 * 1024 ** 3
PAGES_PER_RECORD = 10



def _session() -> requests.Session:
    """Retries with backoff: ncert.nic.in and archive.org drop connections under load."""
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    s = requests.Session()
    retry = Retry(total=6, backoff_factor=2, status_forcelist=[429, 500, 502, 503, 504],
                  allowed_methods=["GET"], raise_on_status=False)
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.headers.update(UA)
    return s


http = _session()


# ---------------------------------------------------------------- filters

def keep_record(text: str, title: str, min_words: int = 200) -> bool:
    if title.endswith("(disambiguation)") or title.startswith("List of"):
        return False
    if len(text.split()) < min_words:
        return False
    chars = [c for c in text if not c.isspace()]
    return bool(chars) and sum(c.isalpha() for c in chars) / len(chars) >= 0.6


# ---------------------------------------------------------------- output

class Sink:
    def __init__(self, source: str) -> None:
        RAW.mkdir(parents=True, exist_ok=True)
        self.path = RAW / f"{source}.jsonl"
        self.seen: set[str] = set()
        if self.path.exists():
            with open(self.path, encoding="utf-8") as f:
                self.seen = {json.loads(line)["doc_id"] for line in f if line.strip()}
        self.f = open(self.path, "a", encoding="utf-8")
        self.added = 0
        self.source = source

    def __contains__(self, doc_id: str) -> bool:
        return doc_id in self.seen

    def write(self, rec: dict) -> None:
        if rec["doc_id"] in self.seen:
            return
        self.seen.add(rec["doc_id"])
        self.f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        self.added += 1

    def close(self) -> None:
        self.f.close()
        manifest_file = LIBRARY_DIR / "manifest.json"
        manifest = json.loads(manifest_file.read_text(encoding="utf-8")) if manifest_file.exists() else {}
        h = hashlib.sha256()
        with open(self.path, "rb") as f:
            for block in iter(lambda: f.read(1 << 20), b""):
                h.update(block)
        manifest[self.source] = {"file": self.path.name, "records": len(self.seen), "added": self.added,
                                 "sha256": h.hexdigest(), "date": time.strftime("%Y-%m-%d %H:%M")}
        manifest_file.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
        print(f"{self.source}: +{self.added} records, {len(self.seen)} total -> {self.path}")


# ---------------------------------------------------------------- wikipedia

def wiki_rows(config: str) -> Iterator[dict]:
    import pyarrow.parquet as pq
    files = sorted((WIKI / f"20231101.{config}").glob("*.parquet"))
    if not files:
        raise SystemExit(f"No parquet files for {config} under {WIKI}; run the hf download first")
    for path in files:
        pf = pq.ParquetFile(path)
        for batch in pf.iter_batches(batch_size=2000, columns=["id", "url", "title", "text"]):
            yield from batch.to_pylist()


def vital_titles() -> set[str]:
    cache = LIBRARY_DIR / "vital_titles.txt"
    if cache.exists() and cache.stat().st_size:
        return set(cache.read_text(encoding="utf-8").splitlines())
    api = "https://en.wikipedia.org/w/api.php"
    pages, params = [], {"action": "query", "list": "allpages", "apnamespace": 4,
                         "apprefix": "Vital articles/Level 5/", "apfilterredir": "nonredirects",
                         "aplimit": "max", "format": "json"}
    while True:
        r = http.get(api, params=params, headers=UA, timeout=60).json()
        pages += [p["title"] for p in r["query"]["allpages"]
                  if "Article alerts" not in p["title"] and "Archive" not in p["title"]]
        if "continue" not in r:
            break
        params.update(r["continue"])
    titles: set[str] = set()
    for i in range(0, len(pages), 20):
        params = {"action": "query", "prop": "links", "titles": "|".join(pages[i:i + 20]),
                  "plnamespace": 0, "pllimit": "max", "format": "json"}
        while True:
            r = http.get(api, params=params, headers=UA, timeout=60).json()
            for page in r["query"]["pages"].values():
                titles.update(link["title"] for link in page.get("links", []))
            if "continue" not in r:
                break
            params.update(r["continue"])
        print(f"vital: {len(titles)} titles from {min(i + 20, len(pages))}/{len(pages)} list pages", flush=True)
    if not titles:
        raise SystemExit("No Vital Articles titles found; the list pages may have moved again")
    cache.write_text("\n".join(sorted(titles)), encoding="utf-8")
    return titles


def fetch_wiki(config: str, lang: str, sink: Sink, limit: int | None, only: set[str] | None = None) -> None:
    for row in wiki_rows(config):
        if only is not None and row["title"] not in only:
            continue
        doc_id = f"wiki-{config}-{row['id']}"
        if doc_id in sink or not keep_record(row["text"], row["title"]):
            continue
        sink.write({"doc_id": doc_id, "source": f"wikipedia-{config}", "title": row["title"], "lang": lang,
                    "url": row["url"], "license": WIKI_LICENSE, "text": row["text"]})
        if limit and sink.added >= limit:
            return


# ---------------------------------------------------------------- PDFs (NCERT, OpenStax)

def pdf_records(data: bytes, doc_id: str, title: str, lang: str, url: str, license: str, source: str
                ) -> Iterator[dict]:
    """One record per PAGES_PER_RECORD pages, using the text layer. Pages whose text layer is unusable
    (scans, or legacy-font Hindi stored as Latin gibberish) are OCR'd with Tesseract."""
    import fitz

    from app.ocr.arbiter import _native_share
    from app.ocr.tesseract import ocr_image, tess_langs
    from app.ocr.triage import classify_page, render_png

    with fitz.open(stream=data, filetype="pdf") as doc:
        texts = []
        for page in doc:
            text = page.get_text("text").strip()
            bad_script = lang != "en" and text and _native_share(text, lang) < 0.3
            if classify_page(page) == "scanned" or bad_script:
                try:
                    text = ocr_image(render_png(page, 300), tess_langs(lang)).text
                except Exception as e:
                    print(f"  OCR failed on {doc_id} p{page.number + 1}: {e}")
                    text = ""
            texts.append(text)
    for a in range(0, len(texts), PAGES_PER_RECORD):
        body = "\n\n".join(t for t in texts[a:a + PAGES_PER_RECORD] if t)
        if keep_record(body, title, min_words=50):
            yield {"doc_id": f"{doc_id}-p{a + 1}", "source": source,
                   "title": f"{title} (pp. {a + 1}–{min(a + PAGES_PER_RECORD, len(texts))})", "lang": lang,
                   "url": url, "license": license, "text": body}


def ncert_codes() -> list[str]:
    html = http.get("https://ncert.nic.in/textbook.php", headers=UA, timeout=60).text
    codes = sorted({m for m in re.findall(r"textbook\.php\?([a-z]+[0-9])=\d+-\d+", html)})
    return [c for c in codes if c[0] in "fghijkl" and c[1] in "eh"]          # classes 6-12, English/Hindi


def fetch_ncert(sink: Sink, limit: int | None) -> None:
    for n, code in enumerate(ncert_codes(), 1):
        if any(d.startswith(f"ncert-{code}") for d in sink.seen):
            continue
        url = f"https://ncert.nic.in/textbook/pdf/{code}dd.zip"
        try:
            z = zipfile.ZipFile(io.BytesIO(http.get(url, headers=UA, timeout=600).content))
        except Exception as e:
            print(f"ncert {code}: download failed ({e})")
            continue
        lang = "hi" if code[1] == "h" else "en"
        cls = "fghijkl".index(code[0]) + 6
        for name in sorted(z.namelist()):
            if not name.lower().endswith(".pdf"):
                continue
            chapter = Path(name).stem
            for rec in pdf_records(z.read(name), f"ncert-{chapter}", f"NCERT Class {cls} {chapter}", lang,
                                   f"https://ncert.nic.in/textbook/pdf/{Path(name).name}",
                                   "NCERT (copyrighted; local use only)", "ncert"):
                sink.write(rec)
        print(f"ncert: {n} books, {sink.added} records", flush=True)
        if limit and sink.added >= limit:
            return


def fetch_openstax(sink: Sink, limit: int | None) -> None:
    api = ("https://openstax.org/apps/cms/api/v2/pages/?type=books.Book"
           "&fields=title,book_state,high_resolution_pdf_url&limit=200")
    books = [b for b in http.get(api, headers=UA, timeout=60).json()["items"]
             if b.get("book_state") == "live" and b.get("high_resolution_pdf_url")]
    for n, b in enumerate(books, 1):
        slug = re.sub(r"\W+", "-", b["title"].lower()).strip("-")
        if any(d.startswith(f"openstax-{slug}-p") for d in sink.seen):
            continue
        try:
            data = http.get(b["high_resolution_pdf_url"], headers=UA, timeout=900).content
        except Exception as e:
            print(f"openstax {b['title']}: download failed ({e})")
            continue
        for rec in pdf_records(data, f"openstax-{slug}", b["title"], "en", b["high_resolution_pdf_url"],
                               "CC BY 4.0 (OpenStax)", "openstax"):
            sink.write(rec)
        print(f"openstax: {n}/{len(books)} books, {sink.added} records", flush=True)
        if limit and sink.added >= limit:
            return


# ---------------------------------------------------------------- archive.org

def _lexicon() -> set[str] | None:
    p = LIBRARY_DIR / "lexicon_en.txt"
    if p.exists():
        return set(p.read_text(encoding="utf-8").split())
    src = RAW / "simple.jsonl"
    if not src.exists():
        return None
    counts: dict[str, int] = {}
    with open(src, encoding="utf-8") as f:
        for i, line in enumerate(f):
            for w in re.findall(r"[a-z]+", json.loads(line)["text"].lower()):
                counts[w] = counts.get(w, 0) + 1
            if i > 50000:
                break
    return {w for w, c in counts.items() if c >= 3}


def fetch_archive(sink: Sink, limit: int | None) -> None:
    lexicon = _lexicon()
    if lexicon is None:
        print("archive: fetch --source simple first (its vocabulary filters bad scans)")
    q = ('mediatype:texts AND (licenseurl:*publicdomain* OR licenseurl:*creativecommons*) '
         'AND subject:(science OR mathematics OR history OR technology) '
         'AND language:(eng OR English OR hin OR Hindi) AND format:"DjVuTXT"')
    total = sum(len(json.loads(l)["text"].encode()) for l in open(sink.path, encoding="utf-8")) \
        if sink.path.stat().st_size else 0
    page = 1
    while total < ARCHIVE_CAP_BYTES:
        params = {"q": q, "fl[]": ["identifier", "title", "licenseurl", "language"], "rows": 500,
                  "page": page, "output": "json", "sort[]": "downloads desc"}
        docs = http.get("https://archive.org/advancedsearch.php", params=params, headers=UA,
                            timeout=120).json()["response"]["docs"]
        if not docs:
            break
        for d in docs:
            doc_id = f"archive-{d['identifier']}"
            if doc_id in sink:
                continue
            url = f"https://archive.org/download/{d['identifier']}/{d['identifier']}_djvu.txt"
            try:
                r = http.get(url, headers=UA, timeout=300)
                r.raise_for_status()
                text = r.text
            except Exception:
                continue
            title = d.get("title") if isinstance(d.get("title"), str) else d["identifier"]
            lang = "hi" if "hin" in str(d.get("language", "")).lower() else "en"
            if not keep_record(text, title):
                continue
            if lexicon and lang == "en":
                words = re.findall(r"[a-z]+", text[:200000].lower())
                if words and sum(w in lexicon for w in words) / len(words) < 0.7:
                    continue                                  # OCR too noisy
            sink.write({"doc_id": doc_id, "source": "archive", "title": title, "lang": lang,
                        "url": f"https://archive.org/details/{d['identifier']}",
                        "license": str(d.get("licenseurl", "")), "text": text})
            total += len(text.encode())
            if total >= ARCHIVE_CAP_BYTES or (limit and sink.added >= limit):
                return
        print(f"archive: {sink.added} books, {total / 2**30:.2f} GB", flush=True)
        page += 1


# ---------------------------------------------------------------- main

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, choices=["vital", "simple", "indic", "ncert", "openstax", "archive"])
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()
    sink = Sink(args.source)
    try:
        if args.source == "vital":
            fetch_wiki("en", "en", sink, args.limit, only=vital_titles())
        elif args.source == "simple":
            fetch_wiki("simple", "en", sink, args.limit)
        elif args.source == "indic":
            for lang in INDIC:
                fetch_wiki(lang, lang, sink, args.limit)
        elif args.source == "ncert":
            fetch_ncert(sink, args.limit)
        elif args.source == "openstax":
            fetch_openstax(sink, args.limit)
        else:
            fetch_archive(sink, args.limit)
    finally:
        sink.close()


if __name__ == "__main__":
    main()
