"""Where the offline library and the per-upload collections are stored."""
from .. import config

LIBRARY_DIR = config.ROOT / "data" / "library"
UPLOADS_DIR = config.ROOT / "data" / "uploads"
EMBED_DIR = config.MODELS_DIR / "multilingual-e5-small"
RERANK_DIR = config.MODELS_DIR / "bge-reranker-v2-m3"
