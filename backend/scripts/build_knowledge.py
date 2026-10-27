"""Builds the offline knowledge base used for retrieval (RAG).

    python scripts/build_knowledge.py              fetch missing articles, then (re)index everything
    python scripts/build_knowledge.py --no-fetch   only re-index (fully offline)

Sources:
  1. Every title in data/topics.txt from Simple English Wikipedia (falls back to English Wikipedia).
     Text is CC BY-SA 4.0; each lesson lists the articles it drew on.
  2. Any .txt / .md files you drop into data/kb_extra/ (your own notes, worksheets, syllabus text).

Raw articles are cached in data/kb/raw/, so re-indexing never needs the internet.
Needs Ollama running with the embedding model (default: nomic-embed-text).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

import numpy as np
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import config  # noqa: E402
from app.knowledge import DOC_PREFIX, KnowledgeBase, embed  # noqa: E402

TOPICS = config.ROOT / "data" / "topics.txt"
EXTRA = config.ROOT / "data" / "kb_extra"
RAW = config.KB_DIR / "raw"
HEADERS = {"User-Agent": "Chanakya/1.0 (offline school-lesson generator; "
                         "https://github.com/signingoff-dubey/UNLOX-TEACHER)"}
SKIP_SECTIONS = {"references", "related pages", "other websites", "see also", "external links", "notes",
                 "further reading", "gallery", "sources", "bibliography", "footnotes", "citations"}
TARGET, MAX_CHARS = 700, 1100          # chunk size in characters
ENWIKI_LIMIT = 12000                   # English Wikipedia articles are long; keep the start


# ------------------------------------------------------------------ fetching

def _safe(title: str) -> str:
    return re.sub(r"[^\w\-]+", "_", title).strip("_")[:120]


class RateLimited(Exception):
    pass


def _get(session: requests.Session, url: str, params: dict) -> requests.Response:
    """GET that honours Wikimedia rate limits: backs off on HTTP 429 instead of giving up."""
    for attempt in range(6):
        r = session.get(url, params=params, headers=HEADERS, timeout=30)
        if r.status_code != 429:
            r.raise_for_status()
            return r
        wait = float(r.headers.get("Retry-After") or 0) or min(60, 5 * 2 ** attempt)
        print(f"  rate limited, waiting {wait:.0f}s…")
        time.sleep(wait)
    raise RateLimited(url)


def fetch(title: str, session: requests.Session) -> dict | None:
    for site, limit in (("simple", None), ("en", ENWIKI_LIMIT)):
        params = {"action": "query", "prop": "extracts|info", "explaintext": 1, "exsectionformat": "wiki",
                  "redirects": 1, "inprop": "url", "titles": title, "format": "json", "formatversion": 2}
        try:
            page = _get(session, f"https://{site}.wikipedia.org/w/api.php", params).json()["query"]["pages"][0]
        except (requests.RequestException, KeyError, IndexError, ValueError):
            continue
        text = page.get("extract") or ""
        if page.get("missing") or len(text) < 300 or "may refer to" in text[:300]:
            continue
        return {"title": page["title"], "url": page.get("fullurl", ""), "site": f"{site}.wikipedia.org",
                "text": text[:limit] if limit else text}
    return None


def fetch_all(titles: list[str]) -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    todo = [t for t in titles if not (RAW / f"{_safe(t)}.json").exists()]
    print(f"Articles: {len(titles)} listed, {len(titles) - len(todo)} cached, {len(todo)} to fetch")
    session = requests.Session()
    # One request at a time with a short pause: polite, and well under Wikimedia's limits.
    for title in todo:
        try:
            art = fetch(title, session)
        except RateLimited:
            print("  still rate limited; stopping. Rerun later — fetched articles are kept.")
            return
        if art:
            (RAW / f"{_safe(title)}.json").write_text(json.dumps(art, ensure_ascii=False), encoding="utf-8")
            print(f"  ok    {title} ({art['site']})")
        else:
            print(f"  skip  {title} (no article)")
        time.sleep(0.5)


# ------------------------------------------------------------------ chunking

def sections(text: str) -> list[tuple[str, str]]:
    """Split '== Heading ==' marked text into (section, body), dropping reference-type sections."""
    out, current, buf = [], "", []
    skipping = False
    for line in text.splitlines():
        m = re.match(r"^(=+)\s*(.*?)\s*=+\s*$", line)
        if m:
            if buf and not skipping:
                out.append((current, "\n".join(buf)))
            current, buf = m.group(2), []
            skipping = current.lower() in SKIP_SECTIONS or (len(m.group(1)) > 2 and skipping)
            continue
        buf.append(line)
    if buf and not skipping:
        out.append((current, "\n".join(buf)))
    return out


def chunk(body: str) -> list[str]:
    paras = [re.sub(r"\s+", " ", p).strip() for p in body.split("\n")]
    paras = [p for p in paras if len(p) > 40]
    chunks, cur = [], ""
    for p in paras:
        while len(p) > MAX_CHARS:                       # very long paragraph: split on sentences
            cut = p.rfind(". ", 0, MAX_CHARS)
            cut = cut + 1 if cut > TARGET // 2 else MAX_CHARS
            if cur:
                chunks.append(cur); cur = ""
            chunks.append(p[:cut].strip()); p = p[cut:].strip()
        if cur and len(cur) + len(p) + 1 > TARGET:
            chunks.append(cur); cur = p
        else:
            cur = f"{cur} {p}".strip()
    if cur:
        chunks.append(cur)
    return chunks


def collect_chunks() -> list[dict]:
    rows: list[dict] = []
    for f in sorted(RAW.glob("*.json")):
        art = json.loads(f.read_text(encoding="utf-8"))
        for sec, body in sections(art["text"]):
            for text in chunk(body):
                rows.append({"title": art["title"], "section": sec, "text": text,
                             "url": art["url"], "source": art["site"]})
    if EXTRA.exists():
        for f in sorted([*EXTRA.rglob("*.txt"), *EXTRA.rglob("*.md")]):
            body = f.read_text(encoding="utf-8", errors="replace")
            body = re.sub(r"^(#+)\s*(.*)$", lambda m: f"{'=' * (len(m.group(1)) + 1)} {m.group(2)} "
                          f"{'=' * (len(m.group(1)) + 1)}", body, flags=re.M)    # markdown headings
            for sec, part in sections(body):
                for text in chunk(part):
                    rows.append({"title": f.stem.replace("_", " "), "section": sec, "text": text,
                                 "url": "", "source": f"local:{f.name}"})
    # Drop exact duplicates (redirects can fetch the same article twice).
    seen, unique = set(), []
    for r in rows:
        key = (r["title"], r["text"][:200])
        if key not in seen:
            seen.add(key); unique.append(r)
    for i, r in enumerate(unique):
        r["id"] = i
    return unique


# ------------------------------------------------------------------ indexing

def build_index(rows: list[dict]) -> None:
    config.KB_DIR.mkdir(parents=True, exist_ok=True)
    texts = [f"{r['title']}" + (f" - {r['section']}" if r["section"] else "") + f": {r['text']}" for r in rows]
    print(f"Embedding {len(texts)} chunks with {config.EMBED_MODEL}…")
    vecs, t0 = [], time.perf_counter()
    for i in range(0, len(texts), 64):
        vecs.append(embed(texts[i:i + 64], DOC_PREFIX))
        print(f"  {min(i + 64, len(texts))}/{len(texts)}", end="\r")
    matrix = np.vstack(vecs).astype(np.float32)
    print(f"\nEmbedded in {time.perf_counter() - t0:.1f}s, dim {matrix.shape[1]}")

    np.save(config.KB_DIR / "embeddings.npy", matrix)
    with open(config.KB_DIR / "chunks.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    meta = {"embed_model": config.EMBED_MODEL, "dim": int(matrix.shape[1]), "count": len(rows),
            "articles": len({r["title"] for r in rows}), "built": time.strftime("%Y-%m-%d %H:%M")}
    (config.KB_DIR / "meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    KnowledgeBase.reload()
    print(f"Knowledge base ready: {meta['count']} chunks from {meta['articles']} articles -> {config.KB_DIR}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-fetch", action="store_true", help="skip downloading; index cached + local files only")
    ap.add_argument("--fetch-only", action="store_true", help="download articles without indexing")
    args = ap.parse_args()
    titles = [t.strip() for t in TOPICS.read_text(encoding="utf-8").splitlines()
              if t.strip() and not t.startswith("#")]
    if not args.no_fetch:
        fetch_all(list(dict.fromkeys(titles)))
    if args.fetch_only:
        return
    rows = collect_chunks()
    if not rows:
        sys.exit("No articles found. Run without --no-fetch while online, or add files to data/kb_extra/.")
    build_index(rows)


if __name__ == "__main__":
    main()
