"""Runtime settings. Everything is read from environment variables (or backend/.env)."""
from __future__ import annotations

import os

# The maths libraries (torch, numpy, OpenMP) may use every core by default and leave nothing for the desktop. Half of them is plenty.
_cores = os.cpu_count() or 4
for _var in ("OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_var, str(max(2, _cores // 2)))
# PyTorch's GPU allocator caches freed blocks and, with many different sizes, reserved 10 GB while only 1 GB was in use (measured on the translator):
# more than the 8 GB card, so Windows pushed the rest into system RAM and the whole computer froze. Smaller blocks and early release stop that.
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "garbage_collection_threshold:0.6,max_split_size_mb:128")
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # chanakya/
BACKEND = ROOT / "backend"
WEB_DIR = ROOT / "web"
if os.getenv("CHANAKYA_ONLINE", "0") != "1":
    os.environ.setdefault("HF_HUB_OFFLINE", "1")            # the project is offline: models come from disk, a missing one is an error, never a download or a hang without Wi-Fi
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
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
VISION_MODEL = os.getenv("VISION_MODEL", "llava:7b")        # reads photos (see vision.py)
PDF_FIGURES = os.getenv("PDF_FIGURES", "1") == "1"            # describe the pictures inside an uploaded PDF with the vision model (see ocr/figures.py)
# "0" unloads the LLM from the GPU right after planning, freeing VRAM for TTS.
# How long the LLM stays loaded after planning. Keeping it loaded makes repeat lessons fast; "0" frees VRAM at once.
# The model stays loaded between lessons (a cold load is ~24 s). One context size for EVERY call: Ollama reloads the model
# whenever num_ctx changes between requests, which used to happen between the planner (8192/4096) and the other agents.
OLLAMA_KEEP_ALIVE = os.getenv("OLLAMA_KEEP_ALIVE", "15m")
LLM_RETRIES = int(os.getenv("LLM_RETRIES", "2"))                 # extra tries when Ollama is busy, restarting or slow to answer

NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "6144"))
# LLM layers on the GPU: "auto" = Ollama offloads as many layers as fit in VRAM (rest run on CPU),
# a number = exactly that many layers, 0 = CPU only. DEVICE=cpu forces 0.
OLLAMA_NUM_GPU = os.getenv("OLLAMA_NUM_GPU", "auto")

# Retrieval (RAG): ground lessons in the offline knowledge base built by scripts/build_knowledge.py
RAG_ENABLED = os.getenv("RAG_ENABLED", "1") == "1"
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")
KB_DIR = Path(os.getenv("KB_DIR", ROOT / "data" / "kb"))
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "6"))
# nomic-embed-text: on-topic school passages score >= ~0.73, loosely related ones ~0.6.
RAG_MIN_SCORE = float(os.getenv("RAG_MIN_SCORE", "0.68"))
# Fact checker (app/facts.py): compares the lesson with the sources and the model's own knowledge before it is recorded
FACTCHECK = os.getenv("FACTCHECK", "1") == "1"
FACTCHECK_BUDGET_S = float(os.getenv("FACTCHECK_BUDGET_S", "50"))      # the most time it may take; what is not checked by then is reported as unconfirmed

# Translation: "nllb" (Meta NLLB-200, GPU), "indictrans2" (AI4Bharat, gated), "ollama" (LLM) or "none"
TRANSLATE_BACKEND = os.getenv("TRANSLATE_BACKEND", "nllb")
BACKCHECK = os.getenv("BACKCHECK", "1") == "1"        # translate narration back to English and compare (needs the NLLB model; about 1 s per scene on the GPU)
INDICTRANS2_MODEL = os.getenv("INDICTRANS2_MODEL", "ai4bharat/indictrans2-en-indic-dist-200M")  # gated on HF
# Not gated: works without a Hugging Face login. Same FLORES language codes as IndicTrans2.
NLLB_MODEL = os.getenv("NLLB_MODEL", "facebook/nllb-200-distilled-600M")

# Narration: "piper", "parler" (AI4Bharat Indic Parler-TTS, GPU) or "silent" (timing-only placeholder)
TTS_ENGINE = os.getenv("TTS_ENGINE", "piper")
TTS_EXPRESSIVE = os.getenv("TTS_EXPRESSIVE", "1") == "1"        # each sentence is spoken with the delivery that fits it (see expression.py)
# Languages whose Piper voice is weak: use the Indic-TTS (CPU ONNX) voice first. Checked by round-tripping speech
# through Whisper: Marathi and Bengali Piper voices were unintelligible, the Indic-TTS ones are not.
TTS_PREFER_INDIC = [c.strip() for c in os.getenv("TTS_PREFER_INDIC", "bn,mr").split(",") if c.strip()]
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
# Speech to text for the voice assistant (faster-whisper, CPU). A folder under models/ or a size name like "small".
# "medium" hears Hindi and the other Indian languages clearly better than "small" for ~1 GB more VRAM; it comes from the Hugging Face cache
STT_MODEL = os.getenv("STT_MODEL", "medium")
STT_THREADS = int(os.getenv("STT_THREADS", "4"))
STT_DEVICE = os.getenv("STT_DEVICE", "auto")      # "cpu" to keep speech recognition off the GPU
STT_MIN_FREE_GB = float(os.getenv("STT_MIN_FREE_GB", "2.2"))   # the speech model goes to the GPU only when this much VRAM is free, else the CPU
PRELOAD_STT = os.getenv("PRELOAD_STT", "0") == "1"           # off: it loads on the first spoken question and is released after MODEL_IDLE_S
MODEL_IDLE_S = float(os.getenv("MODEL_IDLE_S", "600"))       # seconds of quiet after which speech recognition and the translator are released
PIPER_CUDA = os.getenv("PIPER_CUDA", "0") == "1"             # Piper voices run on the CPU (fast enough); the GPU is for the language model

DEVICE = os.getenv("DEVICE", "auto")                 # auto | cuda | cpu
# Load translation + TTS models at startup so the first lesson is fast.
PRELOAD = os.getenv("PRELOAD", "1") == "1"        # warm the models in the background at start-up (the first question is not slow)
# Origins allowed to call the API from another device/port ("*" = any).
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]
SCENE_PADDING_S = float(os.getenv("SCENE_PADDING_S", "0.5"))
NODE_BIN = os.getenv("NODE_BIN", "node")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:8000")
RENDER_CONCURRENCY = os.getenv("RENDER_CONCURRENCY", "")  # empty = Remotion default

for d in (MEDIA_DIR, MODELS_DIR):
    d.mkdir(parents=True, exist_ok=True)


_cuda_broken = False
TORCH_VRAM_FRACTION = float(os.getenv("TORCH_VRAM_FRACTION", "0.35"))      # torch in this process may hold at most this share of the card (the language model needs the rest)
_vram_limited = False


def limit_torch_vram() -> None:
    """Cap what torch may take from the card, so it fails (and falls back to the CPU) instead of spilling into system RAM. Once per process."""
    global _vram_limited
    if _vram_limited or _cuda_broken:
        return
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.set_per_process_memory_fraction(TORCH_VRAM_FRACTION)
            _vram_limited = True
    except Exception:  # noqa: BLE001
        pass


def mark_cuda_broken(reason: str = "") -> None:
    """After "CUDA error: out of memory" (a sticky error, not the catchable OutOfMemoryError) the GPU cannot be used by torch again in this
    process: every later call raises the same error. From here on torch models go to the CPU instead of failing every lesson."""
    global _cuda_broken
    if not _cuda_broken:
        import logging
        logging.getLogger(__name__).error("The GPU is unusable for torch after a CUDA error (%s); using the CPU from now on. Restart the backend to get it back.", reason[:120])
    _cuda_broken = True


def is_cuda_error(e: BaseException) -> bool:
    """True for the sticky CUDA failures (AcceleratorError, 'CUDA error: ...') and for a plain GPU out-of-memory."""
    text = f"{type(e).__name__} {e}".lower()
    return "cuda error" in text or "acceleratorerror" in text or "cuda out of memory" in text or "outofmemoryerror" in text


def gpu_free_gb() -> float | None:
    """Free VRAM in GB as torch sees it (None without a usable GPU)."""
    if _cuda_broken:
        return None
    try:
        import torch
        if torch.cuda.is_available():
            return torch.cuda.mem_get_info()[0] / 2 ** 30
    except Exception:  # noqa: BLE001
        pass
    return None


def torch_device() -> str:
    if _cuda_broken:
        return "cpu"
    if DEVICE != "auto":
        return DEVICE
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


def ollama_options(base: dict) -> dict:
    """Add the GPU-layer and context settings to an Ollama `options` dict (the same num_ctx for every call, see NUM_CTX)."""
    opts = dict(base)
    opts["num_ctx"] = NUM_CTX
    if DEVICE == "cpu":
        opts["num_gpu"] = 0
    elif OLLAMA_NUM_GPU != "auto":
        opts["num_gpu"] = int(OLLAMA_NUM_GPU)
    return opts


def ort_providers() -> list[str]:
    """ONNX Runtime providers: CUDA first when installed and allowed, CPU always as the fallback."""
    try:
        import onnxruntime as ort
        have = ort.get_available_providers()
    except ImportError:
        return ["CPUExecutionProvider"]
    if DEVICE != "cpu" and "CUDAExecutionProvider" in have:
        return ["CUDAExecutionProvider", "CPUExecutionProvider"]
    return ["CPUExecutionProvider"]
