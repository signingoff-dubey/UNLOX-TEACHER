"""Speech to text for the voice assistant: faster-whisper on the CPU, fully offline.

One model is loaded on first use and shared; requests wait their turn (the model is not thread safe). The CPU keeps the
GPU free for the planner/tutor LLM. The lesson language is passed as a hint, but the speaker may use English too, so a
wrong guess is avoided by letting Whisper detect between the hint and English.
"""
from __future__ import annotations

import logging
import os
import subprocess
import threading
from pathlib import Path

import hashlib
import json

from . import config, resources

log = logging.getLogger(__name__)

CACHE_DIR = config.MEDIA_DIR / "stt_cache"
CACHE_MAX = 300                                                       # recordings kept; the oldest go first
MAX_CLIP_BYTES = 8 * 1024 * 1024          # ~30 s of browser-recorded audio is far smaller
_model = None
_lock = threading.Lock()


class SttUnavailable(RuntimeError):
    pass


def _gpu_model(cls, source):
    """Whisper on the GPU: 0.2 s for a short question instead of 3.4 s on the CPU. The cuBLAS and cuDNN 9 DLLs it needs ship inside
    PyTorch's `lib` folder (this venv has a CUDA build of torch); Windows only finds them if that folder is added to the DLL search path.
    A warm-up run proves the GPU path works end to end (a missing library only shows up when the first audio is encoded)."""
    if config.STT_DEVICE == "cpu":
        return None
    try:
        import numpy as np
        import torch
        if not torch.cuda.is_available():
            return None
        free = config.gpu_free_gb()
        if free is not None and free < config.STT_MIN_FREE_GB:
            log.info("Only %.1f GB of VRAM free: speech recognition runs on the CPU", free)
            return None
        lib = Path(torch.__file__).parent / "lib"
        if hasattr(os, "add_dll_directory") and lib.exists():
            os.add_dll_directory(str(lib))
        model = cls(source, device="cuda", compute_type="int8_float16")
        list(model.transcribe(np.zeros(16000, dtype="float32"), beam_size=1)[0])
        log.info("STT runs on the GPU")
        return model
    except Exception as e:  # noqa: BLE001  no GPU, no cuBLAS, or the GPU is full: the CPU does it
        log.warning("STT on the GPU is not available (%s); using the CPU", str(e)[:160])
        return None


def _cpu_model(cls, source):
    try:
        return cls(source, device="cpu", compute_type="int8", cpu_threads=config.STT_THREADS)
    except Exception as e:  # noqa: BLE001  missing weights (offline) or a bad path
        raise SttUnavailable(f"Could not load the speech model '{source}': {e}") from e


def _unload() -> None:
    """Free the speech model (it reloads on the next question). Waits for a transcription in progress."""
    global _model
    with _lock:
        _model = None


def _load():
    global _model
    resources.touch("stt")
    if _model is None:
        try:
            from faster_whisper import WhisperModel
        except ImportError as e:
            raise SttUnavailable("Speech recognition is not installed (pip install faster-whisper)") from e
        source = config.STT_MODEL
        if not Path(source).exists() and "/" not in source and source not in ("tiny", "base", "small", "medium"):
            raise SttUnavailable(f"STT model '{source}' not found")
        small = str(config.MODELS_DIR / "whisper-small")
        for source in dict.fromkeys([source, small]):         # the default (medium) first; the small model if medium is not on disk
            try:
                _model = _gpu_model(WhisperModel, source) or _cpu_model(WhisperModel, source)
                log.info("STT model loaded: %s", source)
                resources.idle_release("stt", config.MODEL_IDLE_S, _unload)
                break
            except SttUnavailable as e:
                log.warning("%s", e)
        if _model is None:
            raise SttUnavailable("No speech model could be loaded")
    return _model


def available() -> bool:
    try:
        import faster_whisper  # noqa: F401
    except ImportError:
        return False
    p = Path(config.STT_MODEL)
    return p.exists() or "/" in config.STT_MODEL or config.STT_MODEL in ("tiny", "base", "small", "medium")


def _detect(model, samples) -> str:
    """Which of OUR languages is being spoken (Whisper knows 99; picking only among the nine we support avoids Urdu for Hindi and the like).
    One extra pass over the first 30 s of audio: about 0.1 s on the GPU."""
    from .languages import LANGUAGES
    try:
        _, _, probs = model.detect_language(samples)
        ours = [(p, c) for c, p in probs if c in LANGUAGES]
        if ours:
            return max(ours)[1]
    except Exception as e:  # noqa: BLE001
        log.warning("language detection failed (%s); letting Whisper decide", e)
    return None


def _cache_key(audio: bytes, lang_hint: str | None, vocabulary: str) -> str:
    h = hashlib.sha1(audio)
    h.update(f"|{config.STT_MODEL}|{lang_hint or 'auto'}|{vocabulary}".encode())
    return h.hexdigest()


def _cache_get(key: str) -> dict | None:
    try:
        return json.loads((CACHE_DIR / f"{key}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _cache_put(key: str, result: dict) -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        (CACHE_DIR / f"{key}.json").write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        files = sorted(CACHE_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime)
        for old in files[:max(0, len(files) - CACHE_MAX)]:
            old.unlink(missing_ok=True)
    except OSError:
        pass                                                         # a cache that cannot be written is just a cache that is not there


def warm_when_idle(delay_s: float = 45.0) -> None:
    """Load the speech model in the background once the computer has nothing else to do, so the first spoken question is not the slow one."""
    def run() -> None:
        import time as _t
        _t.sleep(delay_s)
        from . import jobs
        if jobs.active("lesson", "playlist", "langs") or not resources.has_headroom(min_ram=3.0, min_vram=0.8):
            return                                                   # busy or short of memory: it loads on the first question instead
        try:
            _load()
        except SttUnavailable as e:
            log.info("speech model not warmed: %s", e)
    threading.Thread(target=run, name="stt-warm", daemon=True).start()


def transcribe(audio: bytes, lang_hint: str | None = None, vocabulary: str = "") -> dict:
    """Returns {text, lang, duration_s}. Empty text means silence/noise (the UI says "I did not catch that")."""
    if not audio:
        raise ValueError("No audio received")
    if len(audio) > MAX_CLIP_BYTES:
        raise ValueError("That recording is too long. Keep questions under 30 seconds.")
    key = _cache_key(audio, lang_hint, vocabulary)
    hit = _cache_get(key)
    if hit is not None:
        return {**hit, "cached": True}                          # the same recording again (a replayed demo, a retry): instant
    samples = _decode(audio)
    if samples.size < 1600:                                  # under 0.1 s: nothing was said
        return {"text": "", "lang": lang_hint or "en", "duration_s": 0.0}
    with _lock:
        model = _load()
        lang = lang_hint if lang_hint and lang_hint != "auto" else _detect(model, samples)
        segments, info = model.transcribe(
            samples, language=lang, beam_size=1,
            vad_filter=True, vad_parameters={"min_silence_duration_ms": 400},
            temperature=0.0,                                  # no re-decoding at higher temperatures when the text looks odd: that took 10 s on Telugu
            max_new_tokens=int(samples.size / 16000 * 14) + 24,   # a runaway decode cannot go on past what the audio could hold
            initial_prompt=(vocabulary or None) if lang == "en" else None,      # an English hint pulls other languages into English condition_on_previous_text=False,
        )
        text = " ".join(s.text.strip() for s in segments).strip()
    result = {"text": text, "lang": lang, "duration_s": round(samples.size / 16000, 2)}
    if text:
        _cache_put(key, result)
    return result


def _decode_wav(audio: bytes):
    """16-bit PCM WAV -> 16 kHz mono float32 with the standard library; None for anything else (ffmpeg handles it)."""
    import io
    import wave

    import numpy as np
    try:
        with wave.open(io.BytesIO(audio)) as w:
            if w.getsampwidth() != 2:
                return None
            rate, ch = w.getframerate(), w.getnchannels()
            x = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32) / 32768.0
    except (wave.Error, EOFError):
        return None
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    if rate != 16000 and x.size:
        n = int(round(x.size * 16000 / rate))
        x = np.interp(np.linspace(0, x.size - 1, n), np.arange(x.size), x).astype(np.float32)
    return x


def _decode_av(audio: bytes):
    """Any container PyAV can open -> 16 kHz mono float32, or None (then ffmpeg is tried)."""
    import io

    import numpy as np
    try:
        import av
        out = []
        with av.open(io.BytesIO(audio)) as c:
            stream = c.streams.audio[0]
            rs = av.AudioResampler(format="flt", layout="mono", rate=16000)
            for frame in c.decode(stream):
                for f in rs.resample(frame):
                    out.append(f.to_ndarray().reshape(-1))
            for f in rs.resample(None):
                out.append(f.to_ndarray().reshape(-1))
        return np.concatenate(out).astype(np.float32) if out else None
    except Exception as e:  # noqa: BLE001
        log.debug("PyAV could not decode the recording (%s); using ffmpeg", e)
        return None


def _decode(audio: bytes):
    """Any browser container (webm/opus, ogg, wav, mp4) -> 16 kHz mono float32, using the ffmpeg already needed for export."""
    import numpy as np
    if audio[:4] == b"RIFF" and audio[8:12] == b"WAVE":
        wav = _decode_wav(audio)                      # no process to start: that alone cost 1-2 s on Windows
        if wav is not None:
            return wav
    got = _decode_av(audio)                           # webm/opus from the browser, in this process (PyAV is installed with faster-whisper)
    if got is not None:
        return got
    proc = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-probesize", "64k", "-analyzeduration", "0", "-threads", "1",
                           "-i", "pipe:0", "-f", "f32le", "-ac", "1", "-ar", "16000", "pipe:1"],
                          input=audio, capture_output=True)
    if proc.returncode != 0 or not proc.stdout:
        raise ValueError("That recording could not be read. Try again.")
    return np.frombuffer(proc.stdout, dtype=np.float32)


def preload() -> None:
    """Load the speech model now and run it once (the first real recording is then fast)."""
    _load()
