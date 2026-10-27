"""Runtime settings. Everything is read from environment variables (or backend/.env)."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # visual-teacher/
BACKEND = ROOT / "backend"
WEB_DIR = ROOT / "web"
MODELS_DIR = Path(os.getenv("MODELS_DIR", ROOT / "models"))
MEDIA_DIR = Path(os.getenv("MEDIA_DIR", ROOT / "media"))
FONTS_DIR = WEB_DIR / "public" / "fonts"


def _load_dotenv() -> None:
    env = BACKEND / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.split(" #", 1)[0].strip())


_load_dotenv()

# Lesson planner: "ollama" (local LLM) or "mock" (built-in sample lesson, no model needed)
LLM_BACKEND = os.getenv("LLM_BACKEND", "ollama")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct-q4_K_M")
# "0" unloads the LLM from the GPU right after planning, freeing VRAM for TTS.
OLLAMA_KEEP_ALIVE = os.getenv("OLLAMA_KEEP_ALIVE", "0")

# Retrieval (RAG): ground lessons in the offline knowledge base built by scripts/build_knowledge.py
RAG_ENABLED = os.getenv("RAG_ENABLED", "1") == "1"
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")
KB_DIR = Path(os.getenv("KB_DIR", ROOT / "data" / "kb"))
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "6"))
# nomic-embed-text: on-topic school passages score >= ~0.73, loosely related ones ~0.6.
RAG_MIN_SCORE = float(os.getenv("RAG_MIN_SCORE", "0.68"))

# Translation: "indictrans2", "ollama" (LLM translates) or "none" (copy English)
TRANSLATE_BACKEND = os.getenv("TRANSLATE_BACKEND", "indictrans2")
INDICTRANS2_MODEL = os.getenv("INDICTRANS2_MODEL", "ai4bharat/indictrans2-en-indic-dist-200M")  # gated on HF
# Not gated: works without a Hugging Face login. Same FLORES language codes as IndicTrans2.
NLLB_MODEL = os.getenv("NLLB_MODEL", "facebook/nllb-200-distilled-600M")

# Narration: "piper", "parler" (AI4Bharat Indic Parler-TTS, GPU) or "silent" (timing-only placeholder)
TTS_ENGINE = os.getenv("TTS_ENGINE", "piper")
# Used for languages the main engine cannot speak (e.g. Piper has no Kannada/Tamil voice).
TTS_FALLBACK = os.getenv("TTS_FALLBACK", "parler")
PARLER_MODEL = os.getenv("PARLER_MODEL", "ai4bharat/indic-parler-tts")
PARLER_DESCRIPTION = os.getenv(
    "PARLER_DESCRIPTION",
    "A friendly female teacher speaks clearly at a moderate pace in a quiet room "
    "with very clear audio and no background noise.",
)

# Model locations. INDICTRANS2_MODEL / PARLER_MODEL may also be local folder paths.
PIPER_DIR = Path(os.getenv("PIPER_DIR", MODELS_DIR / "piper"))

DEVICE = os.getenv("DEVICE", "auto")                 # auto | cuda | cpu
# Load translation + TTS models at startup so the first lesson is fast.
PRELOAD = os.getenv("PRELOAD", "0") == "1"
# Origins allowed to call the API from another device/port ("*" = any).
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]
SCENE_PADDING_S = float(os.getenv("SCENE_PADDING_S", "0.5"))
NODE_BIN = os.getenv("NODE_BIN", "node")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:8000")
RENDER_CONCURRENCY = os.getenv("RENDER_CONCURRENCY", "")  # empty = Remotion default

for d in (MEDIA_DIR, MODELS_DIR):
    d.mkdir(parents=True, exist_ok=True)


def torch_device() -> str:
    if DEVICE != "auto":
        return DEVICE
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"
