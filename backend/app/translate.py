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
        out, engine = _translate_with_fallbacks(todo, lang)
        if out is None:
            log.error("Translation to %s failed with every engine; keeping English text", lang)
            return list(texts), "untranslated"
        with _lock:
            for src, dst in zip(todo, out):
                _cache[_key(lang, src)] = dst
            _CACHE_FILE.write_text(json.dumps(_cache, ensure_ascii=False), encoding="utf-8")
    return [_cache.get(_key(lang, t), t) if t.strip() else t for t in texts], config.TRANSLATE_BACKEND


def _translate_with_fallbacks(todo: list[str], lang: str) -> tuple[list[str] | None, str]:
    """The configured model on the GPU; if that fails for any reason (the GPU is nearly full while the language model is
    loaded, a driver hiccup) the same model on the CPU; then the language model through Ollama. English is the last resort,
    never the first: a Hindi lesson that comes out in English is worse than one that takes a few seconds longer."""
    backend = config.TRANSLATE_BACKEND
    flores = get_lang(lang).flores
    attempts: list[tuple[str, object]] = []
    if backend in ("indictrans2", "nllb"):
        model = _IndicTrans2 if backend == "indictrans2" else _NLLB
        attempts.append((backend, lambda: model.get().translate(todo, flores)))
        if config.torch_device() != "cpu":
            attempts.append((f"{backend} on CPU", lambda: model.get("cpu").translate(todo, flores)))
    attempts.append(("ollama", lambda: _ollama_translate_batch(todo, lang)))
    for label, run in attempts:
        try:
            out = run()
            if len(out) == len(todo):
                if label != backend:
                    log.warning("Translation to %s used %s", lang, label)
                return out, label.split(" ")[0]
        except Exception as e:  # noqa: BLE001  any failure moves on to the next engine
            log.error("Translation to %s with %s failed: %s", lang, label, e, exc_info=True)
            _free_gpu()
    return None, "untranslated"


def _free_gpu() -> None:
    try:
        import gc
        import torch
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass


def preload() -> None:
    if config.TRANSLATE_BACKEND == "indictrans2":
        _IndicTrans2.get()
    elif config.TRANSLATE_BACKEND == "nllb":
        _NLLB.get()


def _ollama_translate(text: str, lang: str) -> str:
    from .planner import ollama_generate
    name = get_lang(lang).name
    return ollama_generate(
        f"Translate this English sentence for school students into simple {name}. "
        f"Reply with only the {name} translation.\n\n{text}",
        max_tokens=min(1024, 100 + 6 * len(text)),
    )


_BATCH_SCHEMA = {"type": "object", "properties": {"translations": {"type": "array", "items": {"type": "string"}}},
                 "required": ["translations"]}


def _ollama_translate_batch(texts: list[str], lang: str, size: int = 8) -> list[str]:
    """Translate many strings per LLM call (JSON in, JSON out). Falls back to one-by-one
    for any batch that times out or whose output does not match its input.
    Output length is capped: small models can loop forever on some scripts (seen with Telugu)."""
    name = get_lang(lang).name
    out: list[str] = []
    for i in range(0, len(texts), size):
        chunk = texts[i:i + size]
        prompt = (
            f"Translate each English string in this JSON list into simple {name} written in its native script, "
            f"for school students. Keep the same order and the same number of items ({len(chunk)}). "
            "Keep numbers as digits. Return JSON: {\"translations\": [...]}.\n\n"
            + json.dumps(chunk, ensure_ascii=False)
        )
        # Indic scripts cost several tokens per character; allow generously, but never unbounded.
        budget = min(3072, 200 + 6 * sum(len(t) for t in chunk))
        try:
            resp = requests.post(
                f"{config.OLLAMA_URL}/api/generate",
                json={"model": config.OLLAMA_MODEL, "prompt": prompt, "format": _BATCH_SCHEMA, "stream": False,
                      "keep_alive": "5m",
                      "options": {"temperature": 0.1, "num_ctx": 8192, "num_predict": budget, "repeat_penalty": 1.15}},
                timeout=120,
            )
            resp.raise_for_status()
            got = json.loads(resp.json()["response"])["translations"]
        except (requests.Timeout, KeyError, ValueError):
            got = []
        if len(got) == len(chunk) and all(isinstance(g, str) and g.strip() for g in got):
            out.extend(g.strip() for g in got)
        else:
            log.warning("Batch translation size mismatch for %s; translating one by one", lang)
            out.extend(_ollama_translate(t, lang) for t in chunk)
    return out


class _NLLB:
    """Meta NLLB-200 (distilled 600M): one model for 200 languages including all Indic ones here."""
    _instances: dict[str, "_NLLB"] = {}

    @classmethod
    def get(cls, device: str | None = None) -> "_NLLB":
        device = device or config.torch_device()
        with _lock:
            if device not in cls._instances:
                cls._instances[device] = cls(device)
            return cls._instances[device]

    def __init__(self, device: str) -> None:
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        self.torch = torch
        self.device = device
        log.info("Loading %s on %s", config.NLLB_MODEL, self.device)
        self.tok = AutoTokenizer.from_pretrained(config.NLLB_MODEL, src_lang="eng_Latn")
        self.model = AutoModelForSeq2SeqLM.from_pretrained(
            config.NLLB_MODEL, dtype=torch.float16 if self.device == "cuda" else torch.float32,
        ).to(self.device).eval()

    def translate(self, texts: list[str], tgt: str, batch_size: int = 16) -> list[str]:
        out: list[str] = []
        bos = self.tok.convert_tokens_to_ids(tgt)
        for i in range(0, len(texts), batch_size):
            inputs = self.tok(texts[i:i + batch_size], return_tensors="pt", padding=True,
                              truncation=True, max_length=256).to(self.device)
            with self.torch.inference_mode():
                gen = self.model.generate(**inputs, forced_bos_token_id=bos, num_beams=4,
                                          max_new_tokens=256, repetition_penalty=1.1)
            out.extend(t.strip() for t in self.tok.batch_decode(gen, skip_special_tokens=True))
        return out


class _IndicTrans2:
    """AI4Bharat IndicTrans2 (trained on BPCC). Loaded once, on first use."""
    _instances: dict[str, "_IndicTrans2"] = {}

    @classmethod
    def get(cls, device: str | None = None) -> "_IndicTrans2":
        device = device or config.torch_device()
        with _lock:
            if device not in cls._instances:
                cls._instances[device] = cls(device)
            return cls._instances[device]

    def __init__(self, device: str) -> None:
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        try:
            from IndicTransToolkit.processor import IndicProcessor
        except ImportError:
            from IndicTransToolkit import IndicProcessor

        self.torch = torch
        self.device = device
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
                # use_cache=False: IndicTrans2's remote model code predates the Cache classes of transformers >= 4.50 and
                # crashes with the cache on (Unlimited-OCR needs 4.57). Lesson sentences are short, so the cost is small.
                gen = self.model.generate(**inputs, use_cache=False, min_length=0,
                                          max_length=256, num_beams=4, num_return_sequences=1)
            decoded = self.tok.batch_decode(gen, skip_special_tokens=True,
                                            clean_up_tokenization_spaces=True)
            out.extend(self.ip.postprocess_batch(decoded, lang=tgt))
        return out
