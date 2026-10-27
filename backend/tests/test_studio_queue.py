import threading
import time

import pytest

from app import config, jobs, studio
from tests.test_studio import LESSON


@pytest.fixture()
def lesson_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(studio, "LESSONS_DIR", tmp_path)
    (tmp_path / "L1").mkdir()
    lesson = {**LESSON, "id": "L1", "concept": "Photosynthesis", "languages": {"en": {}}}
    monkeypatch.setattr(studio, "load_lesson", lambda i: lesson)
    monkeypatch.setattr(config, "LLM_BACKEND", "mock")
    studio._state.clear()
    studio._heap.clear()
    studio._prebuilt.clear()
    yield tmp_path


def wait_for(cond, secs=10):
    end = time.time() + secs
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.05)
    return False


def test_request_builds_and_status_turns_ready(lesson_dir):
    assert studio.status("L1", "en")["quiz"]["state"] == "none"
    studio.request("L1", "quiz")
    assert wait_for(lambda: studio.status("L1", "en")["quiz"]["state"] == "ready")
    assert studio.cached("L1", "quiz", "en")["data"]["questions"]
    assert studio.request("L1", "quiz")["state"] == "ready"           # asking again is free


def test_prebuild_queues_everything_once(lesson_dir):
    studio.prebuild("L1")
    studio.prebuild("L1")
    assert wait_for(lambda: all(t["state"] == "ready" for t in studio.status("L1", "en").values()))
    assert set(studio.status("L1", "en")) == set(studio.KINDS)


def test_ensure_waits_for_the_tool(lesson_dir):
    assert studio.ensure("L1", "glossary")["data"]["terms"]


def test_urgent_request_jumps_ahead_of_background(lesson_dir, monkeypatch):
    order: list[str] = []
    gate = threading.Event()
    real = studio._mock

    def slow_mock(kind, lesson, size):
        order.append(kind)
        gate.wait(5)                                                  # hold the worker on the first tool
        return real(kind, lesson, size)

    monkeypatch.setattr(studio, "_mock", slow_mock)
    studio.prebuild("L1")                                             # background: flashcards first
    assert wait_for(lambda: order == ["flashcards"])
    studio.request("L1", "timeline")                                  # last in the background order, but the learner clicked it
    gate.set()
    assert wait_for(lambda: len(order) >= 2)
    assert order[1] == "timeline"


def test_background_work_waits_while_a_lesson_is_being_made(lesson_dir, monkeypatch):
    monkeypatch.setattr(jobs, "active", lambda *kinds: True)
    studio.request("L1", "faq", priority=studio.BACKGROUND)
    time.sleep(0.6)
    assert studio.status("L1", "en")["faq"]["state"] == "queued"
    studio.request("L1", "faq")                                       # urgent ignores the wait
    assert wait_for(lambda: studio.status("L1", "en")["faq"]["state"] == "ready")
