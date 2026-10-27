"""Offline retrieval over the knowledge base (data/kb), used to ground lesson plans in real facts.

Index layout (written by scripts/build_knowledge.py):
  chunks.jsonl     one {"id", "title", "section", "text", "url", "source"} per line
  embeddings.npy   float32 [n_chunks, dim], L2-normalised, same order as chunks.jsonl
  meta.json        {"embed_model", "dim", "count", ...}

Search = embedding cosine similarity (one matrix-vector product, ~1 ms for thousands of
chunks) + a small boost when the query names the article title + per-article dedupe.
"""
from __future__ import annotations

import json
import os
import logging
import re
import threading
from dataclasses import dataclass

import numpy as np
import requests

from . import config

log = logging.getLogger(__name__)

# nomic-embed-text is trained with these task prefixes; other models ignore them harmlessly.
DOC_PREFIX = "search_document: "
QUERY_PREFIX = "search_query: "


@dataclass
class Passage:
    title: str
    section: str
    text: str
    url: str
    source: str
    score: float


def embed(texts: list[str], prefix: str) -> np.ndarray:
    """Embed with the local Ollama embedding model. Returns L2-normalised float32 rows."""
    resp = requests.post(
        f"{config.OLLAMA_URL}/api/embed",
        json={"model": config.EMBED_MODEL, "input": [prefix + t for t in texts], "keep_alive": "30m"},
        timeout=300,
    )
    resp.raise_for_status()
    vecs = np.asarray(resp.json()["embeddings"], dtype=np.float32)
    return vecs / np.maximum(np.linalg.norm(vecs, axis=1, keepdims=True), 1e-8)


class KnowledgeBase:
    _instance: "KnowledgeBase | None" = None
    _lock = threading.Lock()

    @classmethod
    def get(cls) -> "KnowledgeBase | None":
        """The loaded index, or None if it has not been built."""
        with cls._lock:
            if cls._instance is None:
                if not (config.KB_DIR / "embeddings.npy").exists():
                    return None
                cls._instance = cls()
            return cls._instance

    @classmethod
    def reload(cls) -> None:
        with cls._lock:
            cls._instance = None

    def __init__(self) -> None:
        self.meta = json.loads((config.KB_DIR / "meta.json").read_text(encoding="utf-8"))
        with open(config.KB_DIR / "chunks.jsonl", encoding="utf-8") as f:
            self.chunks = [json.loads(line) for line in f]
        self.vectors = np.load(config.KB_DIR / "embeddings.npy")
        if len(self.chunks) != len(self.vectors):
            raise RuntimeError("Knowledge base is inconsistent; rebuild it with scripts/build_knowledge.py")
        self.titles = [c["title"].lower() for c in self.chunks]
        self.articles = len({c["title"] for c in self.chunks})
        log.info("Knowledge base: %d chunks from %d articles", len(self.chunks), self.articles)

    def search(self, query: str, k: int | None = None, per_article: int = 2) -> list[Passage]:
        k = k or config.RAG_TOP_K
        q = embed([query], QUERY_PREFIX)[0]
        scores = self.vectors @ q
        # Boost passages whose article title appears in the query (e.g. "photosynthesis").
        words = set(re.findall(r"[a-z0-9']+", query.lower()))
        if words:
            for i, title in enumerate(self.titles):
                tw = set(re.findall(r"[a-z0-9']+", re.sub(r"\(.*?\)", "", title)))
                if tw and tw <= words:
                    scores[i] += 0.08
        order = np.argsort(-scores)
        best = float(scores[order[0]]) if len(order) else 0.0
        out: list[Passage] = []
        seen: dict[str, int] = {}
        for i in order[: k * 6]:
            s = float(scores[i])
            if s < config.RAG_MIN_SCORE or s < best - 0.15:
                break
            c = self.chunks[i]
            if seen.get(c["title"], 0) >= per_article:
                continue
            seen[c["title"]] = seen.get(c["title"], 0) + 1
            out.append(Passage(c["title"], c.get("section", ""), c["text"], c.get("url", ""),
                               c.get("source", ""), round(s, 3)))
            if len(out) >= k:
                break
        return out


def retrieve(concept: str, upload: str | None = None) -> list[Passage]:
    """Best-effort retrieval: returns [] if RAG is off, the index is missing, or embedding fails.

    With the offline library (data/library/index) or an uploaded PDF (upload=<sha>), uses hybrid search
    + reranking (app/rag); the uploaded PDF's passages come first. Falls back to the data/kb index."""
    if not config.RAG_ENABLED:
        return []
    try:
        if _new_search_available(upload):
            from .rag import search as rag_search
            if not upload:
                scope = "library"
            else:
                scope = f"both:{upload}" if os.getenv("RAG_LIBRARY", "1") != "0" else f"upload:{upload}"
            hits = rag_search.search(concept, scope, k=config.RAG_TOP_K)
            if hits:
                return [_to_passage(h.chunk, h.score) for h in hits]
        kb = KnowledgeBase.get()
        return kb.search(concept) if kb else []
    except Exception as e:  # retrieval must never break lesson generation
        log.warning("Retrieval skipped: %s", e)
        return []


MAX_PAGE_PASSAGES = 80


def pages_passages(upload: str, focus: str) -> list[Passage]:
    """Passages for "explain chapter 4" / "pages 120-135" requests, in reading order. An empty focus
    picks the book's longest chapter (overview lesson). The planner condenses long ranges itself."""
    try:
        from .ocr.ingest import read_info, resolve_focus
        from .ocr.types import TocEntry
        from .rag import search as rag_search
        from .rag.chunker import sections_from_toc

        info = read_info(upload) if upload.isalnum() else None
        if not info:
            return []
        toc = [TocEntry(**t) for t in info["toc"]]
        n = info["pages"]
        if focus.strip():
            pages = resolve_focus(toc, n, focus)
        else:
            chapters = [s for s in sections_from_toc(n, toc) if s[1] != "Front matter"]
            longest = max(chapters, key=lambda s: s[3] - s[2])
            pages = list(range(longest[2], longest[3] + 1))
        col = rag_search.open_collection(f"upload:{upload}")
        if not pages or col is None:
            return []
        chunks = col.section_chunks(upload, pages[0], pages[-1])[:MAX_PAGE_PASSAGES]
        return [_to_passage(c, 1.0) for c in chunks]
    except Exception as e:
        log.warning("Page retrieval skipped: %s", e)
        return []


def _new_search_available(upload: str | None) -> bool:
    """RAG_LIBRARY=0 (read on every call, no restart needed) switches the library off and falls back
    to data/kb for concept-only lessons; uploaded PDFs keep working."""
    from .rag.search import collection_path
    library_on = os.getenv("RAG_LIBRARY", "1") != "0"
    if library_on and (collection_path("library") / "chunks.sqlite").exists():
        return True
    return bool(upload) and upload.isalnum() and (collection_path(f"upload:{upload}") / "chunks.sqlite").exists()


def _to_passage(chunk, score: float) -> Passage:
    """Map a rag Chunk onto the Passage the planner already understands. Uploaded PDFs cite pages."""
    if chunk.page_start:
        pages = f"p. {chunk.page_start}" if chunk.page_start == chunk.page_end else \
            f"pp. {chunk.page_start}–{chunk.page_end}"
    else:
        pages = ""
    section = ", ".join(x for x in (chunk.section if chunk.section != chunk.title else "", pages) if x)
    url = f"upload:{chunk.doc_id}#page={chunk.page_start}" if chunk.source == "upload" else chunk.url
    return Passage(chunk.title, section, chunk.text, url, chunk.source, round(float(score), 3))


def status() -> dict:
    out = _kb_status()
    out.update(_library_status())
    return out


def _kb_status() -> dict:
    kb = None
    try:
        kb = KnowledgeBase.get()
    except Exception as e:  # reported, not raised
        return {"enabled": config.RAG_ENABLED, "ready": False, "error": str(e)}
    if not kb:
        return {"enabled": config.RAG_ENABLED, "ready": False, "chunks": 0, "articles": 0}
    return {"enabled": config.RAG_ENABLED, "ready": True, "chunks": len(kb.chunks), "articles": kb.articles,
            "embed_model": kb.meta.get("embed_model"), "built": kb.meta.get("built")}


def _library_status() -> dict:
    """The offline library and uploaded PDFs (app/rag), read from their meta files without loading models."""
    try:
        from .rag.paths import LIBRARY_DIR, UPLOADS_DIR
        meta_file = LIBRARY_DIR / "index" / "meta.json"
        library = None
        if meta_file.exists():
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            library = {k: meta.get(k) for k in ("count", "sources", "built", "embed_model", "index")}
        uploads = sum(1 for d in UPLOADS_DIR.glob("*/info.json")) if UPLOADS_DIR.exists() else 0
        return {"library": library, "uploads": uploads}
    except Exception as e:
        return {"library": None, "uploads": 0, "library_error": str(e)}
