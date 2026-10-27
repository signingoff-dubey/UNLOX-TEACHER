"""English -> Indian language translation, fully offline."""
from __future__ import annotations

import hashlib
import json
import logging
import threading

import requests

from . import config
from .languages import get as get_lang

log = logging.getLogger(__name__)

_CACHE_FILE = config.MEDIA_DIR / "translation_cache.json"
_lock = threading.Lock()
_cache: dict[str, str] = {}
if _CACHE_FILE.exists():
    try:
        _cache = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        _cache = {}


def _key(lang: str, text: str) -> str:
    return hashlib.sha1(f"{config.TRANSLATE_BACKEND}|{lang}|{text}".encode()).hexdigest()


def translate_batch(texts: list[str], lang: str) -> tuple[list[str], str]:
    """Translate English strings. Returns (translations, engine used). Results are cached on disk.
    If the configured model cannot load, the English text is kept so the lesson still builds
    (engine "untranslated" is reported back to the UI)."""
    if lang == "en" or config.TRANSLATE_BACKEND == "none":
        return list(texts), "none"
    todo = sorted({t for t in texts if t.strip() and _key(lang, t) not in _cache})
    if todo:
        try:
            if config.TRANSLATE_BACKEND == "indictrans2":
                out = _IndicTrans2.get().translate(todo, get_lang(lang).flores)
            elif config.TRANSLATE_BACKEND == "ollama":
                out = [_ollama_translate(t, lang) for t in todo]
            else:
                raise ValueError(f"Unknown TRANSLATE_BACKEND {config.TRANSLATE_BACKEND}")
        except (ImportError, OSError, RuntimeError, requests.RequestException) as e:
            log.error("Translation to %s failed (%s); keeping English text", lang, e)
            return list(texts), "untranslated"
        with _lock:
            for src, dst in zip(todo, out):
                _cache[_key(lang, src)] = dst
            _CACHE_FILE.write_text(json.dumps(_cache, ensure_ascii=False), encoding="utf-8")
    return [_cache.get(_key(lang, t), t) if t.strip() else t for t in texts], config.TRANSLATE_BACKEND


def preload() -> None:
    if config.TRANSLATE_BACKEND == "indictrans2":
        _IndicTrans2.get()


def _ollama_translate(text: str, lang: str) -> str:
    from .planner import ollama_generate
    name = get_lang(lang).name
    return ollama_generate(
        f"Translate this English sentence for school students into simple {name}. "
        f"Reply with only the {name} translation.\n\n{text}"
    )


class _IndicTrans2:
    """AI4Bharat IndicTrans2 (trained on BPCC). Loaded once, on first use."""
    _instance: "_IndicTrans2 | None" = None

    @classmethod
    def get(cls) -> "_IndicTrans2":
        with _lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def __init__(self) -> None:
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        try:
            from IndicTransToolkit.processor import IndicProcessor
        except ImportError:
            from IndicTransToolkit import IndicProcessor

        self.torch = torch
        self.device = config.torch_device()
        name = config.INDICTRANS2_MODEL
        log.info("Loading %s on %s", name, self.device)
        self.tok = AutoTokenizer.from_pretrained(name, trust_remote_code=True)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(
            name, trust_remote_code=True,
            torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
        ).to(self.device).eval()
        self.ip = IndicProcessor(inference=True)

    _gen_lock = threading.Lock()                 # episodes of a playlist are built concurrently; the model is shared

    def translate(self, texts: list[str], tgt: str, batch_size: int = 16) -> list[str]:
        with self._gen_lock:
            return self._translate(texts, tgt, batch_size)

    def _translate(self, texts: list[str], tgt: str, batch_size: int = 16) -> list[str]:
        out: list[str] = []
        for i in range(0, len(texts), batch_size):
            chunk = texts[i:i + batch_size]
            batch = self.ip.preprocess_batch(chunk, src_lang="eng_Latn", tgt_lang=tgt)
            inputs = self.tok(batch, truncation=True, padding="longest",
                              return_tensors="pt", return_attention_mask=True).to(self.device)
            with self.torch.inference_mode():
                gen = self.model.generate(**inputs, use_cache=True, min_length=0,
                                          max_length=256, num_beams=4, num_return_sequences=1)
            decoded = self.tok.batch_decode(gen, skip_special_tokens=True,
                                            clean_up_tokenization_spaces=True)
            out.extend(self.ip.postprocess_batch(decoded, lang=tgt))
        return out
