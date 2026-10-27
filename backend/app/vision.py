"""Photos: llava (a vision model running in Ollama, on this computer) reads a photo of homework, a textbook page, a diagram or a
whiteboard, so a lesson can use what the photo shows. The reading is cached next to the image, so it is done once."""
from __future__ import annotations

import base64
import hashlib
import io
import logging
import re

import requests

from . import config

log = logging.getLogger(__name__)

IMAGES_DIR = config.MEDIA_DIR / "images"
IMAGES_DIR.mkdir(parents=True, exist_ok=True)
MAX_BYTES = 12 * 1024 * 1024
MAX_SIDE = 1280                                     # llava looks at about this many pixels anyway
VISION_MODEL = config.VISION_MODEL

PROMPT = (
    "You are helping a student. Look at this photo and write plain text (no markdown) in this order:\n"
    "1. All text you can read, copied exactly, including question numbers, numbers and formulas.\n"
    "2. A short description of any diagram, graph, figure or object.\n"
    "3. A last line that starts with 'Topic:' and names the school subject and topic in at most 8 words."
)


FIGURE_PROMPT = (
    "This is a figure from a textbook or worksheet. In two or three plain sentences say what it shows. "
    "Copy every label, title, axis name, number and unit exactly as written. Mention only what you can actually see: if something is unclear, "
    "say it is unclear instead of guessing. Do not use markdown."
)


class ImageError(ValueError):
    pass


class VisionUnavailable(RuntimeError):
    """The vision model is not installed or Ollama is not running: stop asking, the rest would fail the same way."""


def _kind(data: bytes) -> str:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    raise ImageError("Use a PNG, JPEG or WebP photo")


def save(data: bytes) -> str:
    """Store an uploaded photo; the id is a hash of its bytes (the same photo is stored and read once)."""
    if len(data) > MAX_BYTES:
        raise ImageError("That photo is larger than 12 MB")
    ext = _kind(data)
    sha = hashlib.sha256(data).hexdigest()[:16]
    path = IMAGES_DIR / f"{sha}.{ext}"
    if not path.exists():
        path.write_bytes(data)
    return sha


def path_of(sha: str):
    if not re.fullmatch(r"[0-9a-f]{16}", sha):
        raise ImageError("bad image id")
    found = [p for p in IMAGES_DIR.glob(f"{sha}.*") if p.suffix != ".txt"]
    if not found:
        raise FileNotFoundError(sha)
    return found[0]


def _small_jpeg(path) -> bytes:
    from PIL import Image, ImageOps
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        im.thumbnail((MAX_SIDE, MAX_SIDE))
        out = io.BytesIO()
        im.save(out, "JPEG", quality=88)
        return out.getvalue()


def describe(sha: str, progress=lambda s, p: None) -> dict:
    """Read one stored photo. Returns {"id", "description", "topic"}."""
    path = path_of(sha)
    cache = IMAGES_DIR / f"{sha}.txt"
    if cache.exists():
        text = cache.read_text(encoding="utf-8")
    else:
        progress("Reading the photo", 0.2)
        body = {"model": VISION_MODEL, "stream": False, "keep_alive": "30s",       # let the language model have the GPU back soon
                "messages": [{"role": "user", "content": PROMPT, "images": [base64.b64encode(_small_jpeg(path)).decode()]}],
                "options": config.ollama_options({"temperature": 0.1, "num_predict": 700})}
        try:
            r = requests.post(f"{config.OLLAMA_URL}/api/chat", json=body, timeout=300)
            r.raise_for_status()
        except requests.RequestException as e:
            raise RuntimeError(f"The photo could not be read: is '{VISION_MODEL}' installed in Ollama? ({e})") from e
        text = r.json()["message"]["content"].strip()
        if not text:
            raise RuntimeError("The photo model returned nothing")
        cache.write_text(text, encoding="utf-8")
    progress("Ready", 1.0)
    return {"id": sha, "description": text, "topic": topic_of(text)}


def topic_of(text: str) -> str:
    m = re.search(r"^\s*topic\s*:\s*(.+)$", text, re.I | re.M)
    return m.group(1).strip(" .*")[:120] if m else ""


def cached(sha: str) -> str:
    f = IMAGES_DIR / f"{sha}.txt"
    return f.read_text(encoding="utf-8") if f.exists() else ""


def context(images: list[str], limit: int = 3500) -> str:
    """What the attached photos show, as one block for the planner."""
    parts = []
    for i, sha in enumerate(images or [], 1):
        text = cached(sha)
        if text:
            parts.append(f"Photo {i}:\n{text}")
    return "\n\n".join(parts)[:limit]


def topics(images: list[str]) -> str:
    return "; ".join(t for t in (topic_of(cached(s)) for s in images or []) if t)


def describe_figure(data: bytes) -> str:
    """What one picture cut out of a PDF shows, in two or three sentences (cached by the picture's hash, so it is read once ever)."""
    sha = hashlib.sha256(data).hexdigest()[:16]
    cache = IMAGES_DIR / f"fig_{sha}.txt"
    if cache.exists():
        return cache.read_text(encoding="utf-8")
    from PIL import Image, ImageOps
    with Image.open(io.BytesIO(data)) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        im.thumbnail((MAX_SIDE, MAX_SIDE))
        out = io.BytesIO()
        im.save(out, "JPEG", quality=88)
    body = {"model": VISION_MODEL, "stream": False, "keep_alive": "30s",
            "messages": [{"role": "user", "content": FIGURE_PROMPT, "images": [base64.b64encode(out.getvalue()).decode()]}],
            "options": config.ollama_options({"temperature": 0.1, "num_predict": 260})}
    try:
        r = requests.post(f"{config.OLLAMA_URL}/api/chat", json=body, timeout=300)
        if r.status_code == 404:
            raise VisionUnavailable(f"'{VISION_MODEL}' is not installed in Ollama (ollama pull {VISION_MODEL})")
        r.raise_for_status()
    except requests.ConnectionError as e:
        raise VisionUnavailable(f"Ollama is not running: {e}") from e
    except requests.RequestException as e:
        raise RuntimeError(f"The figure could not be read: {e}") from e
    text = " ".join(r.json()["message"]["content"].split())
    if text:
        cache.write_text(text, encoding="utf-8")
    return text

