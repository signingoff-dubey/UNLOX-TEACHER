"""Narration. Each call returns a WAV file and its exact duration, which then sets the scene length."""
from __future__ import annotations

import hashlib
import logging
import os
import re
import threading
import wave
from dataclasses import dataclass
from pathlib import Path

from . import config, expression
from .languages import get as get_lang

log = logging.getLogger(__name__)

AUDIO_DIR = config.MEDIA_DIR / "audio"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)
PIPER_DIR = config.PIPER_DIR


@dataclass
class Speech:
    path: Path
    duration_s: float
    engine: str


class EngineUnavailable(Exception):
    pass


_tone = threading.local()          # the delivery of the clip being made (set by synthesize, read by the engine)


def synthesize(text: str, lang: str, tone: str | None = None) -> Speech:
    """Speak `text` in `lang`, trying TTS_ENGINE, then TTS_FALLBACK, then silence. `tone` is the delivery of the scene (see expression.py): warm, excited,
    curious, calm or serious; each sentence is then spoken the way its own punctuation and wording call for."""
    _tone.v = (tone or "warm") if expression.enabled() else None
    # "indic" (CPU ONNX) comes before the GPU-only Parler fallback so CPU-only laptops still get a voice.
    first = "indic" if lang in config.TTS_PREFER_INDIC else config.TTS_ENGINE
    chain = list(dict.fromkeys([first, config.TTS_ENGINE, "indic", config.TTS_FALLBACK, "silent"]))
    for engine in chain:
        out = AUDIO_DIR / f"{hashlib.sha1(f'{engine}|{lang}|{config.PARLER_DESCRIPTION}|{expression.key(tone)}|{text}'.encode()).hexdigest()}.wav"
        if out.exists():
            return Speech(out, wav_duration(out), engine)
        try:
            _ENGINES[engine](text, lang, out)
            return Speech(out, wav_duration(out), engine)
        except EngineUnavailable as e:
            log.info("TTS %s unavailable for %s: %s", engine, lang, e)
            out.unlink(missing_ok=True)
    raise RuntimeError("unreachable: silent engine always works")


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as wf:
        return wf.getnframes() / float(wf.getframerate())


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?।॥])\s+", text.strip())
    return [p for p in parts if p.strip()]


# ---------------------------------------------------------------- Piper (CPU, very fast)
_piper_voices: dict[str, object] = {}
_piper_locks: dict[str, threading.Lock] = {}
_piper_locks_guard = threading.Lock()


def _lock_for(table: dict, lang: str) -> threading.Lock:
    with _piper_locks_guard:
        return table.setdefault(lang, threading.Lock())


def _piper(text: str, lang: str, out: Path) -> None:
    voice_id = get_lang(lang).piper_voice
    if not voice_id:
        raise EngineUnavailable(f"no Piper voice for {lang}")
    model = PIPER_DIR / (Path(voice_id).name + ".onnx")
    if not model.exists():
        raise EngineUnavailable(f"{model} missing (run scripts/download_models.py)")
    try:
        from piper import PiperVoice
    except ImportError as e:
        raise EngineUnavailable("piper-tts not installed") from e
    with _lock_for(_piper_locks, lang):
        voice = _piper_voices.get(lang)
        if voice is None:
            voice = _piper_voices[lang] = PiperVoice.load(str(model), use_cuda=config.PIPER_CUDA and config.ort_providers()[0] == "CUDAExecutionProvider")
        tone = getattr(_tone, "v", None)
        if tone and _piper_expressive(voice, text, tone, out):
            return
        with wave.open(str(out), "wb") as wf:
            if hasattr(voice, "synthesize_wav"):      # piper-tts >= 1.3
                voice.synthesize_wav(text, wf)
            else:                                       # piper-tts 1.2
                voice.synthesize(text, wf)


def _piper_expressive(voice, text: str, tone: str, out: Path) -> bool:
    """One sentence at a time with its own speed, variability and volume, and a pause that fits it. False when this Piper cannot do it (the flat path is used)."""
    try:
        import numpy as np
        from piper import SynthesisConfig
        cfg = voice.config
        rate = cfg.sample_rate
        parts = []
        for sentence in split_sentences(text) or [text]:
            t = expression.sentence_tone(sentence, tone)
            p = expression.TONES[t]
            syn = SynthesisConfig(length_scale=(getattr(cfg, "length_scale", None) or 1.0) * p["length"], noise_scale=(getattr(cfg, "noise_scale", None) or 0.667) * p["noise"],
                                  noise_w_scale=(getattr(cfg, "noise_w_scale", None) or 0.8) * p["noise_w"], volume=p["volume"])
            pcm = b"".join(c.audio_int16_bytes for c in voice.synthesize(sentence, syn))
            if not pcm:
                continue
            parts += [np.frombuffer(pcm, dtype="<i2"), np.zeros(int(rate * expression.pause_after(sentence, t)), dtype="<i2")]
        if not parts:
            return False
        audio = np.concatenate(parts[:-1])                       # no silence after the last sentence: the scene adds its own padding
        with wave.open(str(out), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(rate)
            wf.writeframes(audio.astype("<i2").tobytes())
        return True
    except Exception as e:  # noqa: BLE001  an older Piper, an odd voice: speak it flat rather than not at all
        log.info("expressive Piper speech not available (%s); speaking flat", str(e)[:100])
        Path(out).unlink(missing_ok=True)
        return False


# ---------------------------------------------------------------- Indic Parler-TTS (AI4Bharat, GPU)
class _Parler:
    _instance: "_Parler | None" = None
    _lock = threading.Lock()

    @classmethod
    def get(cls) -> "_Parler":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def __init__(self) -> None:
        try:
            import torch
            from parler_tts import ParlerTTSForConditionalGeneration
            from transformers import AutoTokenizer
        except ImportError as e:
            raise EngineUnavailable("parler-tts not installed") from e
        self.torch = torch
        self.device = config.torch_device()
        log.info("Loading %s on %s", config.PARLER_MODEL, self.device)
        self.model = ParlerTTSForConditionalGeneration.from_pretrained(config.PARLER_MODEL).to(self.device).eval()
        self.tok = AutoTokenizer.from_pretrained(config.PARLER_MODEL)
        self.desc_tok = AutoTokenizer.from_pretrained(self.model.config.text_encoder._name_or_path)
        self.rate = self.model.config.sampling_rate

    def speak(self, text: str, out: Path) -> None:
        import numpy as np
        tone = getattr(_tone, "v", None)
        descs: dict[str, object] = {}
        chunks = []
        # Parler drifts on long inputs, so speak one sentence at a time. Parler follows a plain-language description of the delivery, so each sentence gets its own.
        for sentence in split_sentences(text):
            t = expression.sentence_tone(sentence, tone) if tone else None
            if t not in descs:
                text_desc = config.PARLER_DESCRIPTION + (f" The speaker sounds {expression.DESCRIPTIONS[t]}." if t else "")
                descs[t] = self.desc_tok(text_desc, return_tensors="pt").to(self.device)
            desc = descs[t]
            pause = np.zeros(int(self.rate * (expression.pause_after(sentence, t) if t else 0.25)), dtype=np.float32)
            prompt = self.tok(sentence, return_tensors="pt").to(self.device)
            with self.torch.inference_mode():
                gen = self.model.generate(
                    input_ids=desc.input_ids, attention_mask=desc.attention_mask,
                    prompt_input_ids=prompt.input_ids, prompt_attention_mask=prompt.attention_mask,
                )
            chunks += [gen.cpu().float().numpy().squeeze(), pause]
        _write_pcm16(out, np.concatenate(chunks), self.rate)


_parler_speak_lock = threading.Lock()   # one generation at a time on the GPU


def _parler(text: str, lang: str, out: Path) -> None:
    engine = _Parler.get()
    with _parler_speak_lock:
        engine.speak(text, out)


# ---------------------------------------------------------------- AI4Bharat Indic-TTS (CPU, int8 ONNX)
# FastPitch (tokens -> mel) + HiFi-GAN (mel -> audio), 22.05 kHz. Covers en, ta, kn, gu (and more if added).
INDIC_DIR = config.MODELS_DIR / "indic-tts"
_indic_models: dict[str, tuple] = {}
_indic_locks: dict[str, threading.Lock] = {}


def _indic_load(lang: str):
    d = INDIC_DIR / lang
    fp, hg, tk = d / f"fastpitch-{lang}.int8.onnx", d / f"hifigan-{lang}.int8.onnx", d / f"fastpitch-{lang}.tokens.json"
    if not (fp.exists() and hg.exists() and tk.exists()):
        raise EngineUnavailable(f"no Indic-TTS ONNX voice for {lang} in {d}")
    try:
        import onnxruntime as ort
    except ImportError as e:
        raise EngineUnavailable("onnxruntime not installed") from e
    import json
    tokens = json.loads(tk.read_text(encoding="utf-8"))
    ids = {t: i for i, t in enumerate(tokens) if t != "<PAD>"}
    opts = ort.SessionOptions()
    opts.intra_op_num_threads = max(1, (os.cpu_count() or 4) // 2)
    mk = lambda f: ort.InferenceSession(str(f), opts, providers=config.ort_providers())
    return mk(fp), mk(hg), ids, max(len(t) for t in ids)


def _indic_tokenize(text: str, ids: dict[str, int], longest: int) -> list[int]:
    out, i = [], 0
    while i < len(text):
        for n in range(min(longest, len(text) - i), 0, -1):
            tid = ids.get(text[i:i + n])
            if tid is not None:
                out.append(tid)
                i += n
                break
        else:
            i += 1          # character the voice cannot say: skip it
    return out


def _indic(text: str, lang: str, out: Path) -> None:
    import numpy as np
    with _lock_for(_indic_locks, lang):
        if lang not in _indic_models:
            _indic_models[lang] = _indic_load(lang)
        fastpitch, hifigan, ids, longest = _indic_models[lang]
        tone = getattr(_tone, "v", None)
        speed = {"excited": 1.05, "warm": 1.0, "curious": 0.98, "calm": 0.97, "serious": 0.96, "emphasis": 0.94}
        chunks = []
        for sentence in split_sentences(text):
            toks = _indic_tokenize(sentence, ids, longest)
            if not toks:
                continue
            mel = fastpitch.run(None, {"text": np.array([toks], dtype=np.int64)})[0]
            audio = hifigan.run(None, {"mel": mel})[0].reshape(-1)
            t = expression.sentence_tone(sentence, tone) if tone else None
            if t and speed[t] != 1.0 and len(audio) > 100:
                audio = np.interp(np.linspace(0, len(audio) - 1, int(len(audio) / speed[t])), np.arange(len(audio)), audio).astype(np.float32)
            chunks += [audio, np.zeros(int(22050 * (expression.pause_after(sentence, t) if t else 0.25)), dtype=np.float32)]
    if not chunks:
        raise EngineUnavailable(f"nothing speakable for {lang}")
    _write_pcm16(out, np.concatenate(chunks), 22050)


# ---------------------------------------------------------------- Silent placeholder (no model)
def _silent(text: str, lang: str, out: Path) -> None:
    """Timing-only stand-in so the pipeline runs before any voice model is installed."""
    import numpy as np
    seconds = max(1.5, len(text) / 14.0)
    _write_pcm16(out, np.zeros(int(22050 * seconds), dtype=np.float32), 22050)


def _write_pcm16(out: Path, audio, rate: int) -> None:
    import numpy as np
    pcm = (np.clip(audio, -1.0, 1.0) * 32767).astype("<i2")
    with wave.open(str(out), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(pcm.tobytes())


_ENGINES = {"piper": _piper, "indic": _indic, "parler": _parler, "silent": _silent}


def preload() -> None:
    """Load voice models now instead of on the first request."""
    from .languages import LANGUAGES
    for code in LANGUAGES:
        if "piper" in (config.TTS_ENGINE, config.TTS_FALLBACK):
            try:
                _piper("ok", code, AUDIO_DIR / "_warmup.wav")
            except EngineUnavailable:
                pass
    for code in LANGUAGES:                          # languages without a Piper voice use the Indic ONNX voices
        if code in config.TTS_PREFER_INDIC or not get_lang(code).piper_voice:
            try:
                _indic("ok", code, AUDIO_DIR / "_warmup.wav")
            except Exception as e:  # noqa: BLE001
                log.info("Indic voice for %s not warmed: %s", code, e)
    if "parler" in (config.TTS_ENGINE, config.TTS_FALLBACK):
        try:
            _Parler.get()
        except Exception as e:  # noqa: BLE001  EngineUnavailable, or the model is not downloaded and the machine is offline
            log.warning("Parler not loaded: %s", str(e)[:120])
    (AUDIO_DIR / "_warmup.wav").unlink(missing_ok=True)
