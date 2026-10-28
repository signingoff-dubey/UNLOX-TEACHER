"""Photos: llava (a vision model running in Ollama, on this computer) reads a photo of homework, a textbook page, a diagram or a
whiteboard, so a lesson can use what the photo shows. The reading is cached next to the image, so it is done once."""
from __future__ import annotations

import base64
import hashlib
import io
import logging
import re
import threading

import requests

from . import config

log = logging.getLogger(__name__)

IMAGES_DIR = config.MEDIA_DIR / "images"
IMAGES_DIR.mkdir(parents=True, exist_ok=True)
MAX_BYTES = 12 * 1024 * 1024
MAX_SIDE = 1024                                     # llava looks at about this many pixels anyway (1280 only made the read slower)
VISION_MODEL = config.VISION_MODEL

PROMPT = (
    "You are helping a student. Look at this photo and write plain text (no markdown) in this order:\n"
    "1. All text you can read, copied exactly, including question numbers, numbers and formulas. At most 15 lines, and never repeat a line.\n"
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


_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


def _lock_for(sha: str) -> threading.Lock:
    with _locks_guard:
        return _locks.setdefault(sha, threading.Lock())


def describe(sha: str, progress=lambda s, p: None) -> dict:
    """Read one stored photo. Returns {"id", "description", "topic"}. One reader per photo at a time: a lesson that starts while the photo is still
    being read waits for that read and uses its result instead of asking llava a second time."""
    with _lock_for(sha):
        return _describe(sha, progress)


def pending(images: list[str]) -> list[str]:
    """The photos that have not been read yet."""
    out = []
    for sha in images or []:
        try:
            if not (IMAGES_DIR / f"{sha}.txt").exists():
                path_of(sha)
                out.append(sha)
        except (ImageError, FileNotFoundError):
            continue
    return out


def ensure(images: list[str]) -> None:
    """Read every photo that is not read yet (waits for a read already in progress). A photo that cannot be read is simply left out."""
    for sha in pending(images):
        try:
            describe(sha)
        except Exception as e:  # noqa: BLE001
            log.warning("photo %s could not be read: %s", sha, e)


def _describe(sha: str, progress=lambda s, p: None) -> dict:
    path = path_of(sha)
    cache = IMAGES_DIR / f"{sha}.txt"
    if cache.exists():
        text = cache.read_text(encoding="utf-8")
    else:
        progress("Reading the photo", 0.2)
        body = {"model": VISION_MODEL, "stream": False, "keep_alive": "30s",       # let the language model have the GPU back soon
                "messages": [{"role": "user", "content": PROMPT, "images": [base64.b64encode(_small_jpeg(path)).decode()]}],
                "options": config.ollama_options({"temperature": 0.1, "num_predict": 380, "repeat_penalty": 1.2})}
        try:
            r = requests.post(f"{config.OLLAMA_URL}/api/chat", json=body, timeout=300)
            r.raise_for_status()
        except requests.RequestException as e:
            raise RuntimeError(f"The photo could not be read: is '{VISION_MODEL}' installed in Ollama? ({e})") from e
        text = clean_description(r.json()["message"]["content"])
        if not text:
            raise RuntimeError("The photo model returned nothing")
        cache.write_text(text, encoding="utf-8")
    progress("Ready", 1.0)
    return {"id": sha, "description": text, "topic": topic_of(text)}


def clean_description(text: str, max_lines: int = 15, max_chars: int = 900) -> str:
    """llava sometimes loops: one photo of a topic list came back as 104 lines drifting into unrelated subjects and repeating the same lines. Repeated
    lines are dropped and the reading is cut to what a photo can plausibly hold; the Topic line is kept."""
    out, seen, topic = [], set(), ""
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if re.match(r"^\s*topic\s*:", line, re.I):
            topic = line
            continue
        key = re.sub(r"^\d+[.)]\s*", "", line).lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(line)
    body = "\n".join(out[:max_lines])[:max_chars].rstrip()
    return (body + ("\n" + topic if topic else "")).strip()


def relevant(text: str, focus: str, limit: int = 6) -> str:
    """The lines of a photo's text that share words with what one video of a course is about (empty when none do: that video does not mention the photo)."""
    want = set(re.findall(r"[a-z0-9+#]{4,}", focus.lower()))
    hits = [ln for ln in text.splitlines() if ln.strip() and not re.match(r"^\s*topic\s*:", ln, re.I) and want & set(re.findall(r"[a-z0-9+#]{4,}", ln.lower()))]
    return "\n".join(hits[:limit])


def topic_of(text: str) -> str:
    m = re.search(r"^\s*topic\s*:\s*(.+)$", text, re.I | re.M)
    return m.group(1).strip(" .*")[:120] if m else ""


def cached(sha: str) -> str:
    f = IMAGES_DIR / f"{sha}.txt"
    return clean_description(f.read_text(encoding="utf-8")) if f.exists() else ""          # (a reading cached before the clean-up is cleaned here too)


def context(images: list[str], limit: int = 3500) -> str:
    """What the attached photos show, as one block for the planner. Photos that are not read yet are read now."""
    ensure(images)
    parts = []
    for i, sha in enumerate(images or [], 1):
        text = cached(sha)
        if text:
            parts.append(f"Photo {i}:\n{text}")
    return "\n\n".join(parts)[:limit]


def topics(images: list[str]) -> str:
    ensure(images)
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

