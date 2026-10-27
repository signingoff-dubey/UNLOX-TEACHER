"""A searchable collection: chunk rows + FTS5 keyword index in SQLite, embeddings in FAISS.

Uploads use an exact flat index keyed by SQLite rowid, so a section can be deleted and re-added
when better OCR text arrives. The library uses a compressed IVF-PQ index written by
scripts/build_library.py and is read-only here.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import astuple, fields
from pathlib import Path

import faiss
import numpy as np

from ..words import INDIC_MARKS, words
from .chunker import Chunk

FIELDS = [f.name for f in fields(Chunk)]
NPROBE = 32          # IVF lists searched per query in the library index (recall vs speed)
MAX_QUERY_TERMS = 12

# unicode61 splits Indic words at vowel signs and viramas (प्रकाश -> प, रक, श). Declaring those combining
# marks as token characters keeps each word whole.
FTS_TOKENIZE = f"unicode61 remove_diacritics 0 tokenchars '{INDIC_MARKS}'"

# Very common words carry no topic and make BM25 scan most of a 1M-chunk index.
STOPWORDS = set("""
a an and are as at be been but by can could did do does doing for from had has have how i if in into is it
its me my not of on or our so than that the their them then there these they this to was we were what when
where which while who whom why will with would you your about explain tell describe define meaning
है हैं का की के में और से को पर यह वह एक भी तो ही था थी थे कि क्या क्यों कैसे होता होती होते
""".split())


class Collection:
    def __init__(self, path: Path, embedder) -> None:
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)
        self.embedder = embedder
        self._lock = threading.RLock()
        self.db = sqlite3.connect(self.path / "chunks.sqlite", check_same_thread=False)
        cols = ", ".join(f"{n} {'INTEGER' if n in ('section_idx', 'page_start', 'page_end', 'low_confidence') else 'TEXT'}"
                         for n in FIELDS)
        self.db.executescript(f"""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS chunks (rowid INTEGER PRIMARY KEY, {cols});
            CREATE UNIQUE INDEX IF NOT EXISTS chunks_id ON chunks(chunk_id);
            CREATE INDEX IF NOT EXISTS chunks_section ON chunks(doc_id, section_idx);
        """)
        self._create_fts()
        meta_file = self.path / "meta.json"
        self.meta = json.loads(meta_file.read_text(encoding="utf-8")) if meta_file.exists() else {
            "embed_model": getattr(embedder, "name", type(embedder).__name__), "dim": embedder.dim}
        self._save_meta()
        index_file = self.path / "vectors.faiss"
        self.index = faiss.read_index(str(index_file)) if index_file.exists() else \
            faiss.IndexIDMap2(faiss.IndexFlatIP(embedder.dim))
        self.read_only = not isinstance(self.index, faiss.IndexIDMap2)
        if self.read_only:
            try:
                faiss.extract_index_ivf(self.index).nprobe = NPROBE
            except RuntimeError:
                pass

    def _create_fts(self) -> None:
        self.db.execute(f'CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(text, title, tokenize="{FTS_TOKENIZE}")')
        self.db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts_vocab USING fts5vocab(chunks_fts, 'row')")
        self.db.commit()

    def rebuild_fts(self) -> None:
        """Recreate the keyword index with the current tokenizer (for collections built before it changed)."""
        with self._lock:
            self.db.execute("DROP TABLE IF EXISTS chunks_fts_vocab")
            self.db.execute("DROP TABLE IF EXISTS chunks_fts")
            self._create_fts()
            self.db.execute("INSERT INTO chunks_fts (rowid, text, title) "
                            "SELECT rowid, text, title || ' ' || section FROM chunks")
            self.db.commit()

    def _save_meta(self) -> None:
        (self.path / "meta.json").write_text(json.dumps(self.meta, indent=1), encoding="utf-8")

    def _save_index(self) -> None:
        faiss.write_index(self.index, str(self.path / "vectors.faiss"))

    def count(self) -> int:
        return self.db.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]

    def add(self, chunks: list[Chunk]) -> None:
        if not chunks:
            return
        if self.read_only:
            raise RuntimeError("This collection's index is read-only (library)")
        vecs = self.embedder.passages([c.text for c in chunks]).astype(np.float32)
        with self._lock:
            ids, stale = [], []
            for c in chunks:
                # Replacing a chunk: drop its old row, keyword entry and vector first.
                old = self.db.execute("SELECT rowid FROM chunks WHERE chunk_id = ?", (c.chunk_id,)).fetchone()
                if old:
                    stale.append(old[0])
                    self.db.execute("DELETE FROM chunks_fts WHERE rowid = ?", old)
                    self.db.execute("DELETE FROM chunks WHERE rowid = ?", old)
                row = astuple(c)[:-2] + (int(c.low_confidence), c.text)
                cur = self.db.execute(
                    f"INSERT INTO chunks ({', '.join(FIELDS)}) VALUES ({', '.join('?' * len(FIELDS))})", row)
                self.db.execute("INSERT INTO chunks_fts (rowid, text, title) VALUES (?, ?, ?)",
                                (cur.lastrowid, c.text, f"{c.title} {c.section}"))
                ids.append(cur.lastrowid)
            self.db.commit()
            if stale:
                self.index.remove_ids(np.asarray(stale, dtype=np.int64))
            self.index.add_with_ids(vecs, np.asarray(ids, dtype=np.int64))
            self._save_index()

    def delete_section(self, doc_id: str, section_idx: int) -> None:
        if self.read_only:
            raise RuntimeError("This collection's index is read-only (library)")
        with self._lock:
            rows = [r[0] for r in self.db.execute(
                "SELECT rowid FROM chunks WHERE doc_id = ? AND section_idx = ?", (doc_id, section_idx))]
            if not rows:
                return
            marks = ", ".join("?" * len(rows))
            self.db.execute(f"DELETE FROM chunks_fts WHERE rowid IN ({marks})", rows)
            self.db.execute(f"DELETE FROM chunks WHERE rowid IN ({marks})", rows)
            self.db.commit()
            self.index.remove_ids(np.asarray(rows, dtype=np.int64))
            self._save_index()

    def keyword(self, query: str, k: int) -> list[tuple[str, float]]:
        tokens = [t for t in dict.fromkeys(words(query.lower()))
                  if t not in STOPWORDS and (len(t) > 1 or t.isdigit())][:MAX_QUERY_TERMS]
        if not tokens:
            return []
        match = " OR ".join('"' + t.replace('"', "") + '"' for t in tokens)
        with self._lock:
            rows = self.db.execute(
                "SELECT c.chunk_id, -bm25(chunks_fts) FROM chunks_fts JOIN chunks c ON c.rowid = chunks_fts.rowid "
                "WHERE chunks_fts MATCH ? ORDER BY bm25(chunks_fts) LIMIT ?", (match, k)).fetchall()
        return [(cid, float(s)) for cid, s in rows]

    def vector(self, qvec: np.ndarray, k: int) -> list[tuple[str, float]]:
        with self._lock:
            if self.index.ntotal == 0:
                return []
            scores, ids = self.index.search(np.asarray(qvec, dtype=np.float32).reshape(1, -1), k)
            hits = [(int(i), float(s)) for i, s in zip(ids[0], scores[0]) if i != -1]
            if not hits:
                return []
            marks = ", ".join("?" * len(hits))
            by_row = dict(self.db.execute(f"SELECT rowid, chunk_id FROM chunks WHERE rowid IN ({marks})",
                                          [i for i, _ in hits]).fetchall())
        return [(by_row[i], s) for i, s in hits if i in by_row]

    def get(self, ids: list[str]) -> list[Chunk]:
        if not ids:
            return []
        marks = ", ".join("?" * len(ids))
        with self._lock:
            rows = self.db.execute(f"SELECT {', '.join(FIELDS)} FROM chunks WHERE chunk_id IN ({marks})", ids)
            by_id = {}
            for r in rows:
                d = dict(zip(FIELDS, r))
                d["low_confidence"] = bool(d["low_confidence"])
                by_id[d["chunk_id"]] = Chunk(**d)
        return [by_id[i] for i in ids if i in by_id]

    def section_chunks(self, doc_id: str, first_page: int, last_page: int) -> list[Chunk]:
        """Chunks overlapping a page range, in reading order (for 'explain chapter 4' lessons)."""
        with self._lock:
            ids = [r[0] for r in self.db.execute(
                "SELECT chunk_id FROM chunks WHERE doc_id = ? AND page_end >= ? AND page_start <= ? "
                "ORDER BY section_idx, page_start, rowid", (doc_id, first_page, last_page))]
        return self.get(ids)

    def close(self) -> None:
        self.db.close()
