import pytest

from app import config, playlist, translate
from app.streaming import ScenePreview


@pytest.fixture(autouse=True)
def _gpu_state(monkeypatch):
    monkeypatch.setattr(config, "_cuda_broken", False)


class AcceleratorError(RuntimeError):
    """Stand-in for torch's sticky error: its class name and message are what the code recognises."""


def test_sticky_cuda_errors_are_recognised():
    assert config.is_cuda_error(AcceleratorError("CUDA error: out of memory"))
    assert config.is_cuda_error(RuntimeError("CUDA out of memory. Tried to allocate 20.00 MiB"))
    assert not config.is_cuda_error(ValueError("bad json"))


def test_a_cuda_error_moves_translation_to_the_cpu_instead_of_failing(monkeypatch):
    monkeypatch.setattr(config, "TRANSLATE_BACKEND", "nllb")

    class GpuModel:
        def translate(self, texts, flores, beams=4, **kw):
            raise AcceleratorError("CUDA error: out of memory")

    class CpuModel:
        def translate(self, texts, flores, beams=4, **kw):
            return [f"hi:{t}" for t in texts]

    monkeypatch.setattr(translate._NLLB, "get", classmethod(lambda cls, device=None: GpuModel() if device is None else CpuModel()))
    monkeypatch.setattr(translate, "_ollama_translate_batch", lambda texts, lang: pytest.fail("the CPU model should have answered"))
    out, engine = translate._translate_with_fallbacks(["one", "two"], "hi")
    assert out == ["hi:one", "hi:two"] and engine == "nllb"
    assert config.torch_device() == "cpu"                                   # every later torch model goes to the CPU


def test_cleaning_up_after_a_broken_gpu_never_raises(monkeypatch):
    import sys
    import types

    def boom():
        raise AcceleratorError("CUDA error")

    fake = types.SimpleNamespace(cuda=types.SimpleNamespace(is_available=lambda: True, empty_cache=boom))
    monkeypatch.setitem(sys.modules, "torch", fake)
    monkeypatch.setattr(config, "DEVICE", "cuda")
    translate._free_gpu()                                                   # used to raise and sink the whole episode


def test_translator_goes_to_the_cpu_when_little_vram_is_free(monkeypatch):
    monkeypatch.setattr(config, "DEVICE", "cuda")
    monkeypatch.setattr(config, "gpu_free_gb", lambda: 0.6)
    monkeypatch.setattr(translate._NLLB, "_instances", {})
    monkeypatch.setattr(translate._IndicTrans2, "_instances", {})
    assert translate._pick_device() == "cpu"
    monkeypatch.setattr(config, "gpu_free_gb", lambda: 5.0)
    assert translate._pick_device() == "cuda"


def test_preview_accepts_whole_scenes_after_the_streamed_ones(tmp_path, monkeypatch):
    made = []
    monkeypatch.setattr(ScenePreview, "_one", lambda self, gen, obj: made.append(obj["heading"]))
    p = ScenePreview("x", "Tides", "en", [], ["en"], 8, tmp_path / "lesson.json")
    p.feed('{"title": "T", "scenes": [{"heading": "A", "narration": "n"}, {"heading": "B", "narration": "n"}, {"hea')
    p.add_scenes([{"heading": "C", "narration": "n"}, {"heading": "D", "narration": "n"}])
    import time
    for _ in range(100):                                                    # let the worker make them before closing (close drops what is still queued)
        if len(made) == 4:
            break
        time.sleep(0.02)
    p.close()
    assert made == ["A", "B", "C", "D"] and p._seen == 4


def test_a_course_episode_with_a_cuda_error_is_retried_and_the_first_episode_opens_early(monkeypatch):
    calls = []
    saved = []

    def fake_build(concept, languages, level, duration_s, documents, series=None, images=None, mode="explain", progressive=False, quality="flash", progress=None):
        calls.append(progressive)
        if len(calls) == 1:
            progress("Planning", 0.1, lesson_id="early123")                 # the first scenes exist
            raise AcceleratorError("CUDA error: out of memory")
        return {"id": "early123", "languages": {"en": {"duration_s": 61.0}}}

    pl = {"id": "p1", "topic": "Pacman", "title": "", "languages": ["en"], "level": "beginner", "duration_s": 60, "documents": [], "images": [],
          "mode": "explain", "requested": 1, "episodes": [], "status": "planning"}
    cur = playlist.Curriculum(title="Pacman", episodes=[playlist.Episode(title="Ghosts", focus="Move a ghost")])
    monkeypatch.setattr(playlist, "load", lambda pid: pl)
    monkeypatch.setattr(playlist, "save", lambda p: saved.append([dict(e) for e in p["episodes"]]))
    monkeypatch.setattr(playlist, "design_curriculum", lambda *a, **k: cur)
    monkeypatch.setattr(playlist, "build_lesson", fake_build)
    out = playlist.build("p1")
    ep = out["episodes"][0]
    assert ep["status"] == "ready" and ep["lesson_id"] == "early123" and "preview" not in ep and ep["error"] is None
    assert calls == [True, True]                                            # episode 1 streams its scenes; the retry ran after the GPU broke
    assert any(e[0].get("preview") and e[0]["lesson_id"] == "early123" for e in saved)      # the course page could open it while it was made
    assert config.torch_device() == "cpu"


def test_every_course_episode_streams_its_scenes(monkeypatch):
    seen = []

    def fake_build(concept, languages, level, duration_s, documents, series=None, images=None, mode="explain", progressive=False, quality="flash", progress=None):
        seen.append((concept, progressive))
        progress("Planning", 0.7, lesson_id=f"early-{len(seen)}")             # past planning: the next episode may start
        return {"id": f"early-{len(seen)}", "languages": {"en": {"duration_s": 40.0}}}

    pl = {"id": "p2", "topic": "Tides", "title": "", "languages": ["en"], "level": "beginner", "duration_s": 60, "documents": [], "images": [],
          "mode": "explain", "requested": 3, "episodes": [], "status": "planning"}
    cur = playlist.Curriculum(title="Tides", episodes=[playlist.Episode(title=f"Part {k}", focus="x") for k in range(3)])
    monkeypatch.setattr(playlist, "load", lambda pid: pl)
    monkeypatch.setattr(playlist, "save", lambda p: None)
    monkeypatch.setattr(playlist, "design_curriculum", lambda *a, **k: cur)
    monkeypatch.setattr(playlist, "build_lesson", fake_build)
    monkeypatch.setattr(playlist.resources, "wait_for_headroom", lambda *a, **k: None)
    out = playlist.build("p2")
    assert [p for _, p in seen] == [True, True, True]                         # episodes 2 and 3 stream too, not only episode 1
    assert [e["status"] for e in out["episodes"]] == ["ready"] * 3
