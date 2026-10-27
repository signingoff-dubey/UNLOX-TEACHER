"""Speech to text for the voice assistant: faster-whisper on the CPU, fully offline.

One model is loaded on first use and shared; requests wait their turn (the model is not thread safe). The CPU keeps the
GPU free for the planner/tutor LLM. The lesson language is passed as a hint, but the speaker may use English too, so a
wrong guess is avoided by letting Whisper detect between the hint and English.
"""
from __future__ import annotations

import logging
import subprocess
import threading
from pathlib import Path

from . import config

log = logging.getLogger(__name__)

MAX_CLIP_BYTES = 8 * 1024 * 1024          # ~30 s of browser-recorded audio is far smaller
_model = None
_lock = threading.Lock()


class SttUnavailable(RuntimeError):
    pass


def _load():
    global _model
    if _model is None:
        try:
            from faster_whisper import WhisperModel
        except ImportError as e:
            raise SttUnavailable("Speech recognition is not installed (pip install faster-whisper)") from e
        source = config.STT_MODEL
        if not Path(source).exists() and "/" not in source and source not in ("tiny", "base", "small", "medium"):
            raise SttUnavailable(f"STT model '{source}' not found")
        try:
            _model = WhisperModel(source, device="cpu", compute_type="int8", cpu_threads=config.STT_THREADS)
        except Exception as e:  # noqa: BLE001  missing weights (offline) or a bad path
            raise SttUnavailable(f"Could not load the speech model '{source}': {e}") from e
        log.info("STT model loaded: %s", source)
    return _model


def available() -> bool:
    try:
        import faster_whisper  # noqa: F401
    except ImportError:
        return False
    p = Path(config.STT_MODEL)
    return p.exists() or "/" in config.STT_MODEL or config.STT_MODEL in ("tiny", "base", "small", "medium")


def transcribe(audio: bytes, lang_hint: str | None = None, vocabulary: str = "") -> dict:
    """Returns {text, lang, duration_s}. Empty text means silence/noise (the UI says "I did not catch that")."""
    if not audio:
        raise ValueError("No audio received")
    if len(audio) > MAX_CLIP_BYTES:
        raise ValueError("That recording is too long. Keep questions under 30 seconds.")
    samples = _decode(audio)
    if samples.size < 1600:                                  # under 0.1 s: nothing was said
        return {"text": "", "lang": lang_hint or "en", "duration_s": 0.0}
    with _lock:
        model = _load()
        segments, info = model.transcribe(
            samples, language=lang_hint if lang_hint and lang_hint != "auto" else None, beam_size=1,
            vad_filter=True, vad_parameters={"min_silence_duration_ms": 400},
            initial_prompt=vocabulary or None, condition_on_previous_text=False,
        )
        text = " ".join(s.text.strip() for s in segments).strip()
    return {"text": text, "lang": info.language, "duration_s": round(samples.size / 16000, 2)}


def _decode(audio: bytes):
    """Any browser container (webm/opus, ogg, wav, mp4) -> 16 kHz mono float32, using the ffmpeg already needed for export."""
    import numpy as np
    proc = subprocess.run(["ffmpeg", "-v", "error", "-i", "pipe:0", "-f", "f32le", "-ac", "1", "-ar", "16000", "pipe:1"],
                          input=audio, capture_output=True)
    if proc.returncode != 0 or not proc.stdout:
        raise ValueError("That recording could not be read. Try again.")
    return np.frombuffer(proc.stdout, dtype=np.float32)
