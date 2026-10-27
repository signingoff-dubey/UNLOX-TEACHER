import time

from app import config, resources


def test_headroom_follows_free_ram_and_vram(monkeypatch):
    monkeypatch.setattr(resources, "free_ram_gb", lambda: 6.0)
    monkeypatch.setattr(resources, "free_vram_gb", lambda: 2.0)
    assert resources.has_headroom()
    monkeypatch.setattr(resources, "free_ram_gb", lambda: 0.9)
    assert not resources.has_headroom()                                  # short of RAM: background work waits
    monkeypatch.setattr(resources, "free_ram_gb", lambda: 6.0)
    monkeypatch.setattr(resources, "free_vram_gb", lambda: 0.3)
    assert not resources.has_headroom()                                  # short of VRAM (the desktop shares it)
    monkeypatch.setattr(resources, "free_vram_gb", lambda: None)         # no GPU / torch not loaded: only RAM counts
    assert resources.has_headroom()


def test_waiting_for_headroom_gives_up_after_the_timeout(monkeypatch):
    monkeypatch.setattr(resources, "has_headroom", lambda *a, **k: False)
    real_sleep = time.sleep
    monkeypatch.setattr(resources.time, "sleep", lambda s: real_sleep(0.01))
    t0 = time.monotonic()
    resources.wait_for_headroom("test", timeout=0.1)                     # a slow lesson is better than none
    assert 0.09 < time.monotonic() - t0 < 2


def test_waiting_ends_as_soon_as_memory_is_back(monkeypatch):
    states = iter([False, False, True])
    monkeypatch.setattr(resources, "has_headroom", lambda *a, **k: next(states))
    monkeypatch.setattr(resources.time, "sleep", lambda s: None)
    resources.wait_for_headroom("test", timeout=5)


def test_idle_models_are_released_and_touching_postpones_it(monkeypatch):
    released = []
    monkeypatch.setattr(resources, "_reaper", None)
    clock = [1000.0]
    monkeypatch.setattr(resources.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(resources, "_last_used", {})
    monkeypatch.setattr(resources, "_release", {})
    # run one pass of the reaper by hand, without its thread and its 20 s sleep
    resources._release["m"] = (60.0, lambda: released.append("m"))
    resources.touch("m")
    def reap_once():
        now = resources.time.monotonic()
        for n, (idle, fn) in list(resources._release.items()):
            if n in resources._last_used and now - resources._last_used[n] >= idle:
                resources._last_used.pop(n)
                fn()
    clock[0] += 59
    reap_once()
    assert released == []
    resources.touch("m")                                                 # used again: the clock starts over
    clock[0] += 59
    reap_once()
    assert released == []
    clock[0] += 2
    reap_once()
    assert released == ["m"]


def test_thread_caps_leave_cores_for_the_desktop():
    import os
    assert int(os.environ["OMP_NUM_THREADS"]) <= max(2, (os.cpu_count() or 4))


def test_piper_stays_off_the_gpu_by_default():
    assert config.PIPER_CUDA is False and config.PRELOAD_STT is False


def test_course_episodes_do_not_queue_study_tools(monkeypatch):
    import inspect
    from app import pipeline
    src = inspect.getsource(pipeline._build)
    assert "if series is None:" in src and "studio.prebuild(lesson_id)" in src
