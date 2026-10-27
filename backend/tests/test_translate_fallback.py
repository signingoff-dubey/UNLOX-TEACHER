from app import translate


class _Boom:
    @classmethod
    def get(cls, device=None):
        raise RuntimeError("CUDA out of memory")


class _Cpu:
    @classmethod
    def get(cls, device=None):
        if device != "cpu":
            raise RuntimeError("CUDA out of memory")
        return cls()

    def translate(self, texts, tgt, **kw):
        return [f"hi:{t}" for t in texts]


def _setup(monkeypatch, model):
    monkeypatch.setattr(translate.config, "TRANSLATE_BACKEND", "indictrans2")
    monkeypatch.setattr(translate.config, "torch_device", lambda: "cuda")
    monkeypatch.setattr(translate, "_IndicTrans2", model)
    monkeypatch.setattr(translate, "_cache", {})
    monkeypatch.setattr(translate, "_CACHE_FILE", translate.config.MEDIA_DIR / "test_translation_cache.json")


def test_a_full_gpu_falls_back_to_the_cpu(monkeypatch, tmp_path):
    _setup(monkeypatch, _Cpu)
    monkeypatch.setattr(translate, "_CACHE_FILE", tmp_path / "c.json")
    out, engine = translate.translate_batch(["Magnets pull iron."], "hi")
    assert out == ["hi:Magnets pull iron."] and engine == "indictrans2"


def test_every_model_failing_goes_to_the_language_model_then_to_english(monkeypatch, tmp_path):
    _setup(monkeypatch, _Boom)
    monkeypatch.setattr(translate, "_CACHE_FILE", tmp_path / "c.json")
    monkeypatch.setattr(translate, "_ollama_translate_batch", lambda texts, lang: [f"ollama:{t}" for t in texts])
    out, _ = translate.translate_batch(["Hello there."], "hi")
    assert out == ["ollama:Hello there."]

    monkeypatch.setattr(translate, "_cache", {})

    def down(texts, lang):
        raise ConnectionError("ollama is down")

    monkeypatch.setattr(translate, "_ollama_translate_batch", down)
    out, engine = translate.translate_batch(["Hello there."], "hi")
    assert out == ["Hello there."] and engine == "untranslated"
