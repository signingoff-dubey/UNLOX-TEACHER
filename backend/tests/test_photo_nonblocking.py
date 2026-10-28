import io
import threading
import time

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import vision


@pytest.fixture()
def photo(monkeypatch, tmp_path):
    monkeypatch.setattr(vision, "IMAGES_DIR", tmp_path)
    monkeypatch.setattr(vision, "_locks", {})
    im = Image.new("RGB", (64, 64), "white")
    out = io.BytesIO()
    im.save(out, "PNG")
    return out.getvalue()


class SlowLlava:
    """Stands in for Ollama's llava: slow, and it counts how often it is asked."""

    def __init__(self):
        self.calls = 0

    def __call__(self, url, json=None, timeout=0):
        self.calls += 1
        time.sleep(0.2)

        class Resp:
            status_code = 200

            def raise_for_status(self):
                pass

            def json(self):
                return {"message": {"content": "Question 1: what is 2 + 2?\nTopic: Basic addition"}}

        return Resp()


def test_a_photo_being_read_is_read_once_even_when_a_lesson_asks_for_it_at_the_same_time(photo, monkeypatch):
    llava = SlowLlava()
    monkeypatch.setattr(vision.requests, "post", llava)
    sha = vision.save(photo)
    results = []
    threads = [threading.Thread(target=lambda: results.append(vision.describe(sha))) for _ in range(3)]      # the upload's own read and the lesson's
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert llava.calls == 1 and len(results) == 3 and all(r["topic"] == "Basic addition" for r in results)


def test_a_lesson_that_starts_before_the_photo_is_read_reads_it_itself(photo, monkeypatch):
    llava = SlowLlava()
    monkeypatch.setattr(vision.requests, "post", llava)
    sha = vision.save(photo)
    assert vision.pending([sha, "0123456789abcdef"]) == [sha]                  # unknown ids are ignored
    text = vision.context([sha])                                               # what the planner asks for: it waits for the read instead of getting nothing
    assert "what is 2 + 2" in text and vision.pending([sha]) == [] and llava.calls == 1
    assert vision.topics([sha]) == "Basic addition" and llava.calls == 1       # and the next one is free


def test_a_photo_that_cannot_be_read_does_not_stop_the_lesson(photo, monkeypatch):
    def broken(*a, **k):
        raise vision.requests.ConnectionError("ollama is down")

    monkeypatch.setattr(vision.requests, "post", broken)
    sha = vision.save(photo)
    assert vision.context([sha]) == ""                                         # left out, not an error


def test_the_upload_answers_with_the_photo_id_before_it_has_been_read(photo, monkeypatch):
    from app import main
    monkeypatch.setattr(main.jobs, "submit", lambda kind, fn, *a: {"id": "job1", "status": "queued"})      # the reading itself runs later
    res = TestClient(main.app).post("/api/images", files={"file": ("p.png", photo, "image/png")}).json()
    assert res["id"] == "job1" and res["image_id"] == vision.save(photo)       # the page can offer "Create" right now
