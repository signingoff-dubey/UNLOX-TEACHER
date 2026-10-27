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


def retrieve(concept: str) -> list[Passage]:
    """Best-effort retrieval: returns [] if RAG is off, the index is missing, or embedding fails."""
    if not config.RAG_ENABLED:
        return []
    try:
        kb = KnowledgeBase.get()
        return kb.search(concept) if kb else []
    except (requests.RequestException, RuntimeError, KeyError, ValueError) as e:
        log.warning("Retrieval skipped: %s", e)
        return []


def status() -> dict:
    kb = None
    try:
        kb = KnowledgeBase.get()
    except Exception as e:  # reported, not raised
        return {"enabled": config.RAG_ENABLED, "ready": False, "error": str(e)}
    if not kb:
        return {"enabled": config.RAG_ENABLED, "ready": False, "chunks": 0, "articles": 0}
    return {"enabled": config.RAG_ENABLED, "ready": True, "chunks": len(kb.chunks), "articles": kb.articles,
            "embed_model": kb.meta.get("embed_model"), "built": kb.meta.get("built")}
