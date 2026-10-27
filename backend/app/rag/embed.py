"""multilingual-e5-small embeddings (384-d). Works across English and Indian scripts, so an English
concept can find a Hindi passage and vice versa. Runs on the CPU for uploads (keeps the GPU for OCR)."""
from __future__ import annotations

import threading
from pathlib import Path

import numpy as np

from .paths import EMBED_DIR


class Embedder:
    name = "intfloat/multilingual-e5-small"
    dim = 384

    def __init__(self, model_dir: Path = EMBED_DIR, device: str = "cpu", batch_size: int = 64) -> None:
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(str(model_dir), device=device)
        self.batch_size = batch_size
        self._lock = threading.Lock()

    def passages(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        with self._lock:
            return self.model.encode([f"passage: {t}" for t in texts], batch_size=self.batch_size,
                                     normalize_embeddings=True, convert_to_numpy=True).astype(np.float32)

    def query(self, text: str) -> np.ndarray:
        with self._lock:
            return self.model.encode([f"query: {text}"], normalize_embeddings=True,
                                     convert_to_numpy=True)[0].astype(np.float32)

    def count_tokens(self, text: str) -> int:
        return len(self.model.tokenizer(text, add_special_tokens=False)["input_ids"])


_shared: Embedder | None = None
_shared_lock = threading.Lock()


def shared_embedder() -> Embedder:
    """One CPU embedder per process (the model is ~470 MB)."""
    global _shared
    with _shared_lock:
        if _shared is None:
            _shared = Embedder()
        return _shared
