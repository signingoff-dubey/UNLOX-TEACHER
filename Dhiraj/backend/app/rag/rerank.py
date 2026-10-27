"""bge-reranker-v2-m3 cross-encoder: reads (query, passage) pairs and scores relevance 0..1.
Multilingual, so it can judge a Hindi passage against an English concept."""
from __future__ import annotations

import threading
from pathlib import Path

from .paths import RERANK_DIR


class Reranker:
    def __init__(self, model_dir: Path = RERANK_DIR, device: str | None = None) -> None:
        import torch
        from sentence_transformers import CrossEncoder
        device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        kwargs = {"model_kwargs": {"torch_dtype": torch.float16}} if device == "cuda" else {}
        self.model = CrossEncoder(str(model_dir), device=device, max_length=512, **kwargs)
        self._sigmoid = torch.nn.Sigmoid()
        self._lock = threading.Lock()

    def score(self, query: str, texts: list[str]) -> list[float]:
        if not texts:
            return []
        with self._lock:
            scores = self.model.predict([(query, t) for t in texts], batch_size=16,
                                        activation_fn=self._sigmoid, convert_to_numpy=True)
        return [float(s) for s in scores]


_shared: Reranker | None = None
_shared_lock = threading.Lock()


def shared_reranker() -> Reranker:
    global _shared
    with _shared_lock:
        if _shared is None:
            _shared = Reranker()
        return _shared
