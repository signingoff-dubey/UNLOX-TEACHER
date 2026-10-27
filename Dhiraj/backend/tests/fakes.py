"""Cheap stand-ins for the real models, so retrieval tests run in milliseconds without weights."""
from __future__ import annotations

import hashlib

import numpy as np

from app.words import WORD as _WORD


def _bucket(word: str, dim: int) -> int:
    return int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16) % dim


class FakeEmbedder:
    """Bag-of-words hashed into 384 dims: texts sharing words get similar vectors."""
    name = "fake-embedder"
    dim = 384

    def _vec(self, text: str) -> np.ndarray:
        v = np.zeros(self.dim, dtype=np.float32)
        for w in _WORD.findall(text.lower()):
            v[_bucket(w, self.dim)] += 1.0
        n = np.linalg.norm(v)
        return v / n if n else v

    def passages(self, texts: list[str]) -> np.ndarray:
        return np.stack([self._vec(t) for t in texts]) if texts else np.zeros((0, self.dim), np.float32)

    def query(self, text: str) -> np.ndarray:
        return self._vec(text)

    @staticmethod
    def count_tokens(text: str) -> int:
        return len(text.split())


class FakeReranker:
    """Score = share of the query's words found in the passage."""

    def score(self, query: str, texts: list[str]) -> list[float]:
        q = set(_WORD.findall(query.lower()))
        if not q:
            return [0.0] * len(texts)
        return [len(q & set(_WORD.findall(t.lower()))) / len(q) for t in texts]
