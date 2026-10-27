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
        if device == "cuda":
            self.model.half()
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


def gpu_embedder(min_free_gb: float = 1.5) -> Embedder | None:
    """A half-precision embedder on the GPU, or None if there is no GPU or not enough free memory. Used while Tesseract has
    every CPU core busy: embedding on the CPU at the same time roughly halved OCR speed."""
    try:
        import torch
        if not torch.cuda.is_available() or torch.cuda.mem_get_info()[0] < min_free_gb * 2 ** 30:
            return None
        return Embedder(device="cuda", batch_size=128)
    except Exception:  # noqa: BLE001  any GPU trouble just means "use the CPU"
        return None


def release_gpu() -> None:
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:  # noqa: BLE001
        pass


_shared: Embedder | None = None
_shared_lock = threading.Lock()


def shared_embedder() -> Embedder:
    """One CPU embedder per process (the model is ~470 MB)."""
    global _shared
    with _shared_lock:
        if _shared is None:
            _shared = Embedder()
        return _shared
