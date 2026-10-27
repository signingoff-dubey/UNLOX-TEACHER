"""Hybrid retrieval over the library and uploaded PDFs.

Per collection: FTS5 keyword top-50 + FAISS vector top-50, merged by reciprocal rank fusion, then
reranked by bge-reranker-v2-m3. Scopes:
  "library"       the offline library only
  "upload:<sha>"  one uploaded PDF only
  "both:<sha>"    the PDF first; the library adds at most 2 passages (background / analogy),
                  or fills in completely when the PDF has nothing relevant
"""
from __future__ import annotations

import threading
from dataclasses import dataclass

from .chunker import Chunk
from .paths import LIBRARY_DIR, UPLOADS_DIR
from .store import Collection

CANDIDATES = 50
RERANK_POOL = 40
RRF_K = 60
LIBRARY_EXTRA = 2
LOW_CONFIDENCE_WEIGHT = 0.8
MIN_RELEVANCE = 0.2

_cache: dict[str, Collection] = {}
_cache_lock = threading.Lock()


@dataclass
class Hit:
    chunk: Chunk
    score: float
    scope: str


def rrf(rankings: list[list[str]], k: int = RRF_K) -> list[tuple[str, float]]:
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, cid in enumerate(ranking):
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores.items(), key=lambda kv: -kv[1])


def collection_path(scope: str):
    if scope == "library":
        return LIBRARY_DIR / "index"
    if scope.startswith("upload:"):
        sha = scope.split(":", 1)[1]
        if not sha.isalnum():
            raise ValueError(f"bad upload id {sha!r}")
        return UPLOADS_DIR / sha / "index"
    raise ValueError(f"unknown scope {scope!r}")


def open_collection(scope: str, embedder) -> Collection | None:
    path = collection_path(scope)
    with _cache_lock:
        col = _cache.get(scope)
        if col is None:
            if not (path / "chunks.sqlite").exists():
                return None
            col = _cache[scope] = Collection(path, embedder)
        return col


def writable_collection(scope: str, embedder) -> Collection:
    """Open or create a collection, shared with readers so they see new chunks immediately
    (each Collection holds its FAISS index in memory)."""
    path = collection_path(scope)
    with _cache_lock:
        col = _cache.get(scope)
        if col is None:
            col = _cache[scope] = Collection(path, embedder)
        return col


def forget(scope: str) -> None:
    """Drop a cached collection (after an upload's index is rebuilt or deleted)."""
    with _cache_lock:
        col = _cache.pop(scope, None)
    if col:
        col.close()


def clear_cache() -> None:
    for scope in list(_cache):
        forget(scope)


def _search_one(query: str, scope: str, embedder, reranker) -> list[Hit]:
    col = open_collection(scope, embedder)
    if col is None or col.count() == 0:
        return []
    kw = [cid for cid, _ in col.keyword(query, CANDIDATES)]
    vec = [cid for cid, _ in col.vector(embedder.query(query), CANDIDATES)]
    ids = [cid for cid, _ in rrf([kw, vec])[:RERANK_POOL]]
    chunks = col.get(ids)
    hits = []
    for chunk, s in zip(chunks, reranker.score(query, [c.text for c in chunks])):
        s *= LOW_CONFIDENCE_WEIGHT if chunk.low_confidence else 1.0
        if s >= MIN_RELEVANCE:
            hits.append(Hit(chunk, round(s, 4), scope))
    return sorted(hits, key=lambda h: -h.score)


def search(query: str, scope: str = "library", k: int = 8, *, embedder=None, reranker=None) -> list[Hit]:
    if embedder is None:
        from .embed import shared_embedder
        embedder = shared_embedder()
    if reranker is None:
        from .rerank import shared_reranker
        reranker = shared_reranker()

    if scope.startswith("both:"):
        upload = f"upload:{scope.split(':', 1)[1]}"
        up = _search_one(query, upload, embedder, reranker)[:k]
        room = k - len(up) if not up else min(LIBRARY_EXTRA, k - len(up))
        lib = _search_one(query, "library", embedder, reranker)[:max(room, 0)]
        return up + lib
    collection_path(scope)          # validates the scope
    return _search_one(query, scope, embedder, reranker)[:k]
