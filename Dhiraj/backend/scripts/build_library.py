"""Chunk, embed and index the offline library: data/library/raw/*.jsonl -> data/library/index/.

    python scripts/build_library.py [--sources vital simple indic ncert openstax archive] [--device cuda]

Builds into data/library/index.new and swaps it in at the end, so a running server never sees a
half-built index. Large builds use a compressed IVF-PQ index (nlist 4096, 48 x 8-bit codes, trained on
200k vectors); small ones use an exact flat index. Also writes lexicon_<lang>.txt (top words per
language) for the OCR arbiter.
"""
from __future__ import annotations

import argparse
import json
import random
import re
import shutil
import sqlite3
import sys
import time
from collections import Counter
from pathlib import Path

import faiss
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.rag.chunker import chunk_section  # noqa: E402
from app.rag.paths import LIBRARY_DIR  # noqa: E402
from app.rag.store import FIELDS, Collection  # noqa: E402

SOURCES = ["vital", "simple", "indic", "ncert", "openstax", "archive"]
NLIST, PQ_M, PQ_BITS, TRAIN = 4096, 48, 8, 200_000
FLAT_BELOW = 39 * NLIST                 # faiss needs >= 39 training points per list
EMBED_BATCH = 4096
LEXICON_SIZE = 200_000
_WORD = re.compile(r"\w+", re.UNICODE)


def records(raw_dir: Path, sources: list[str]):
    for src in sources:
        path = raw_dir / f"{src}.jsonl"
        if not path.exists():
            print(f"skip {src}: {path} not found")
            continue
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    yield json.loads(line)


def build(raw_dir: Path, out_dir: Path, sources: list[str], embedder, log=print) -> int:
    new = out_dir.parent / f"{out_dir.name}.new"
    if new.exists():
        shutil.rmtree(new)
    col = Collection(new, embedder)                     # creates the schema; vectors handled below
    db: sqlite3.Connection = col.db
    insert = f"INSERT INTO chunks ({', '.join(FIELDS)}) VALUES ({', '.join('?' * len(FIELDS))})"
    vec_file = new / "vectors.f32"
    lexicons: dict[str, Counter] = {}
    total, t0 = 0, time.perf_counter()
    pending: list = []

    with open(vec_file, "wb") as vf:
        def flush() -> None:
            nonlocal total
            if not pending:
                return
            vecs = embedder.passages([c.text for c in pending]).astype(np.float32)
            for c in pending:
                cur = db.execute(insert, (*[getattr(c, f) for f in FIELDS[:-2]], int(c.low_confidence), c.text))
                db.execute("INSERT INTO chunks_fts (rowid, text, title) VALUES (?, ?, ?)",
                           (cur.lastrowid, c.text, c.title))
                assert cur.lastrowid == total + 1          # rowids are 1..N, matching vector order
                total += 1
            db.commit()
            vf.write(vecs.tobytes())
            pending.clear()
            log(f"{total:,} chunks, {total / (time.perf_counter() - t0):.0f}/s")

        for rec in records(raw_dir, sources):
            meta = {k: rec.get(k, "") for k in ("doc_id", "title", "lang", "source", "license", "url")}
            pending += chunk_section(meta, (0, rec["title"], 0, 0), [(0, rec["text"], False)],
                                     embedder.count_tokens)
            lex = lexicons.setdefault(rec.get("lang") or "en", Counter())
            lex.update(w.lower() for w in _WORD.findall(rec["text"][:100_000]) if not w.isdigit())
            if len(pending) >= EMBED_BATCH:
                flush()
        flush()

    vecs = np.memmap(vec_file, dtype=np.float32, mode="r", shape=(total, embedder.dim)) if total else \
        np.zeros((0, embedder.dim), np.float32)
    ids = np.arange(1, total + 1, dtype=np.int64)
    if total < FLAT_BELOW:
        index = faiss.IndexIDMap2(faiss.IndexFlatIP(embedder.dim))
    else:
        quantizer = faiss.IndexFlatIP(embedder.dim)
        index = faiss.IndexIVFPQ(quantizer, embedder.dim, NLIST, PQ_M, PQ_BITS, faiss.METRIC_INNER_PRODUCT)
        sample = np.asarray(vecs[sorted(random.Random(0).sample(range(total), min(TRAIN, total)))])
        log(f"training IVF-PQ on {len(sample):,} vectors")
        index.train(sample)
    for a in range(0, total, 100_000):
        index.add_with_ids(np.asarray(vecs[a:a + 100_000]), ids[a:a + 100_000])
    faiss.write_index(index, str(new / "vectors.faiss"))
    del vecs
    vec_file.unlink()
    col.meta.update(count=total, sources=sources, built=time.strftime("%Y-%m-%d %H:%M"),
                    index="flat" if total < FLAT_BELOW else f"ivfpq{NLIST},{PQ_M}x{PQ_BITS}")
    col._save_meta()
    col.close()

    for lang, counts in lexicons.items():
        (out_dir.parent / f"lexicon_{lang}.txt").write_text(
            "\n".join(w for w, _ in counts.most_common(LEXICON_SIZE)), encoding="utf-8")

    old = out_dir.parent / f"{out_dir.name}.old"
    if old.exists():
        shutil.rmtree(old)
    if out_dir.exists():
        out_dir.rename(old)            # fails on Windows if a server has it open: stop the server first
    new.rename(out_dir)
    if old.exists():
        shutil.rmtree(old, ignore_errors=True)
    log(f"library ready: {total:,} chunks in {out_dir}")
    return total


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sources", nargs="*", default=SOURCES, choices=SOURCES)
    ap.add_argument("--device", default="cuda")
    args = ap.parse_args()
    from app.rag.embed import Embedder
    build(LIBRARY_DIR / "raw", LIBRARY_DIR / "index", args.sources, Embedder(device=args.device, batch_size=256))


if __name__ == "__main__":
    main()
