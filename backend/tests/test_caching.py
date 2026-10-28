import time
import types

import numpy as np
import pytest

from app import config, resources, stt, translate
from app.schema import ScenePlan
from app.streaming import ScenePreview


# ------------------------------------------------------------------ translation
@pytest.fixture()
def fresh_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(translate, "_cache", {})
    monkeypatch.setattr(translate, "_CACHE_FILE", tmp_path / "translation_cache.json")
    monkeypatch.setattr(config, "TRANSLATE_BACKEND", "nllb")


def test_batches_group_sentences_of_similar_length_and_results_keep_their_order(fresh_cache, monkeypatch):
    seen = []

    def fake(todo, lang, beams=4):
        seen.append(list(todo))
        return [f"hi:{t}" for t in todo], "nllb"

    monkeypatch.setattr(translate, "_translate_with_fallbacks", fake)
    texts = ["A much longer sentence about the moon and the tides.", "Moon", "Tides pull water.", "Moon"]
    out, _ = translate.translate_batch(texts, "hi")
    assert [len(t) for t in seen[0]] == sorted(len(t) for t in seen[0])        # shortest first: less padding in every batch
    assert out == ["hi:" + t for t in texts]                                  # the caller still gets its own order, duplicates included
    assert translate.translate_batch(texts, "hi")[0] == out and len(seen) == 1   # the second time everything is cached


def test_the_translation_cache_is_written_atomically(fresh_cache):
    translate._cache["k"] = "v"
    translate._save_cache()
    assert translate._CACHE_FILE.exists() and not translate._CACHE_FILE.with_suffix(".tmp").exists()
    assert '"k"' in translate._CACHE_FILE.read_text(encoding="utf-8")


def test_precache_only_runs_when_it_costs_nothing_visible(fresh_cache, monkeypatch):
    monkeypatch.setattr(translate, "_translate_with_fallbacks", lambda todo, lang, beams=4: ([f"hi:{t}" for t in todo], "nllb"))
    texts = ["One idea.", "Another idea."]
    monkeypatch.setattr(translate, "_pick_device", lambda: "cpu")
    assert translate.precache(texts, "hi") == 0                                # the translator would have to load on the CPU: not now
    monkeypatch.setattr(translate, "_pick_device", lambda: "cuda")
    monkeypatch.setattr(resources, "has_headroom", lambda *a, **k: False)
    assert translate.precache(texts, "hi") == 0                                # memory is short: not now
    monkeypatch.setattr(resources, "has_headroom", lambda *a, **k: True)
    assert translate.precache(texts, "hi") == 2 and translate.precache(texts, "hi") == 0     # translated once, then nothing new
    assert translate.precache(texts, "en") == 0


def test_the_other_languages_are_drafted_scene_by_scene_while_the_planner_writes(tmp_path, monkeypatch):
    import json
    from app import pipeline
    made = []

    def fake_translate(plan, code):
        made.append(code)
        return (f"{plan.title} [{code}]", [{**s.model_dump(), "heading": f"{s.heading} [{code}]"} for s in plan.scenes]), "indictrans2"

    monkeypatch.setattr(pipeline, "_translated_scenes", fake_translate)
    monkeypatch.setattr(pipeline, "_narrate", lambda tr, lang, on_progress=None, voice_lang=None: {
        "title": tr[0], "duration_s": 3.0, "tts_engines": ["piper"],
        "scenes": [{**s, "audio_url": "", "speech_s": 2.5, "duration_s": 3.0, "start_s": 0.0, "captions": []} for s in tr[1]]})
    monkeypatch.setattr(ScenePreview, "_one", lambda self, gen, obj: None)
    path = tmp_path / "lesson.json"
    p = ScenePreview("x", "Tides", "en", ["hi", "te"], ["en", "hi", "te"], 5, path)
    scene = ScenePlan(template="bullets", heading="Why tides happen", narration="The moon pulls on the sea.", items=["Moon", "Gravity"])
    p._pre_q.put([scene])
    p._pre_q.put([scene.model_copy(update={"heading": "Spring tides"})])
    for _ in range(150):
        if all(len(t["scenes"]) == 2 for t in p.drafts().values()) and len(p.drafts()) == 2:
            break
        time.sleep(0.02)
    drafts = p.drafts()
    p.close()
    assert made == ["hi", "te", "hi", "te"]                                                      # every scene, every other language, in order
    assert [s["heading"] for s in drafts["hi"]["scenes"]] == ["Why tides happen [hi]", "Spring tides [hi]"]
    assert drafts["te"]["scenes"][1]["start_s"] == 3.0 and drafts["te"]["duration_s"] == 6.0 and drafts["hi"]["draft"]
    assert set(json.loads(path.read_text(encoding="utf-8"))["languages"]) == {"hi", "te"}     # the tabs appear while the video is made


# ------------------------------------------------------------------ speech recognition
class FakeModel:
    def __init__(self):
        self.calls = 0

    def transcribe(self, samples, **kw):
        self.calls += 1
        return [types.SimpleNamespace(text=" why is the sky blue ")], types.SimpleNamespace()

    def detect_language(self, samples):
        return None, None, [("en", 0.99)]


@pytest.fixture()
def fake_stt(monkeypatch, tmp_path):
    model = FakeModel()
    monkeypatch.setattr(stt, "CACHE_DIR", tmp_path / "stt_cache")
    monkeypatch.setattr(stt, "_load", lambda: model)
    monkeypatch.setattr(stt, "_decode", lambda audio: np.zeros(32000, dtype="float32"))
    return model


def test_the_same_recording_is_not_transcribed_twice(fake_stt):
    first = stt.transcribe(b"recording-1", "en")
    assert first["text"] == "why is the sky blue" and fake_stt.calls == 1 and "cached" not in first
    again = stt.transcribe(b"recording-1", "en")
    assert again["text"] == first["text"] and again["cached"] is True and fake_stt.calls == 1          # instant, the model was not touched
    stt.transcribe(b"recording-2", "en")
    stt.transcribe(b"recording-1", "hi")                                                               # another language hint is another question
    assert fake_stt.calls == 3


def test_silence_is_not_cached_and_the_cache_is_capped(fake_stt, monkeypatch):
    monkeypatch.setattr(stt, "CACHE_MAX", 3)
    monkeypatch.setattr(fake_stt, "transcribe", lambda s, **kw: ([], None))
    stt.transcribe(b"quiet", "en")
    assert not list(stt.CACHE_DIR.glob("*.json"))                                                      # nothing said: nothing worth keeping
    monkeypatch.setattr(fake_stt, "transcribe", lambda s, **kw: ([types.SimpleNamespace(text="hello")], None))
    for k in range(6):
        stt.transcribe(f"clip-{k}".encode(), "en")
        time.sleep(0.01)
    assert len(list(stt.CACHE_DIR.glob("*.json"))) == 3


def test_the_speech_model_does_not_warm_up_while_a_lesson_is_being_made(monkeypatch):
    from app import jobs
    loaded = []
    monkeypatch.setattr(stt, "_load", lambda: loaded.append(1))
    monkeypatch.setattr(jobs, "active", lambda *kinds: True)
    monkeypatch.setattr(resources, "has_headroom", lambda *a, **k: True)
    stt.warm_when_idle(delay_s=0.0)
    time.sleep(0.3)
    assert loaded == []
    monkeypatch.setattr(jobs, "active", lambda *kinds: False)
    stt.warm_when_idle(delay_s=0.0)
    time.sleep(0.3)
    assert loaded == [1]
