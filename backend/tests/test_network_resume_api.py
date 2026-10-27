import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app import jobs, layout, resume
from app.schema import LessonPlan, normalize


# ------------------------------------------------------------------ network scenes
def test_layers_follow_the_arrows_and_a_cycle_does_not_hang():
    assert layout.layers_of(4, [(0, 1), (1, 2), (0, 2), (2, 3)]) == [0, 1, 2, 3]        # a node sits after everything that points to it
    cyc = layout.layers_of(3, [(0, 1), (1, 2), (2, 0)])                                    # the edge that closes the cycle is ignored
    assert cyc == [0, 1, 2]
    assert layout.layers_of(3, []) == [0, 0, 0]


def test_layout_is_deterministic_inside_the_box_and_separates_a_layer():
    edges = [(0, 1), (0, 2), (1, 3), (2, 3)]
    a, b = layout.layered(4, edges), layout.layered(4, edges)
    assert a == b                                                                         # the same picture every time
    assert all(0 <= x <= 1000 and 0 <= y <= 420 for x, y in a)
    assert a[0][0] < a[1][0] == a[2][0] < a[3][0] and a[1][1] != a[2][1]                  # left to right, the two middle nodes above and below
    assert layout.layered(0, []) == [] and layout.layered(1, []) == [[500.0, 210.0]]


def scene(**kw):
    return {"template": "network", "heading": "Food web", "narration": "Grass feeds rabbits, and rabbits feed foxes.", **kw}


def test_a_network_scene_gets_clean_nodes_arrows_and_positions():
    plan = LessonPlan.model_validate({"title": "Food web", "scenes": [
        {"template": "title", "heading": "Food web", "narration": "Who eats whom?"},
        scene(nodes=["Grass", "Rabbit", "Fox", "grass", "  "], edges=[{"from": 0, "to": 1}, [1, 2], {"src": 1, "dst": 1}, {"src": 0, "dst": 9}, [1, 2]])]})
    s = normalize(plan).scenes[1]
    assert s.template == "network" and s.nodes == ["Grass", "Rabbit", "Fox"]              # the repeated and the empty label are dropped
    assert [(e.src, e.dst) for e in s.edges] == [(0, 1), (1, 2)]                           # self-loops, unknown nodes and repeats are dropped
    assert len(s.positions) == 3 and s.positions[0][0] < s.positions[2][0]


def test_a_network_that_cannot_be_drawn_becomes_a_flow_of_its_boxes():
    plan = LessonPlan.model_validate({"title": "T", "scenes": [{"template": "title", "heading": "T", "narration": "Hello."},
                                                               scene(nodes=["A", "B", "C"], edges=[])]})
    s = normalize(plan).scenes[1]
    assert s.template == "flow" and s.items == ["A", "B", "C"] and s.nodes == [] and s.positions == []


# ------------------------------------------------------------------ resumable jobs
@pytest.fixture()
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(resume, "DB_PATH", tmp_path / "jobs.db")
    return tmp_path


def test_jobs_are_written_to_sqlite_and_a_restart_marks_unfinished_ones(db):
    resume.record({"id": "j1", "kind": "lesson", "status": "running", "stage": "Planning", "progress": 0.4, "error": None})
    resume.record({"id": "j2", "kind": "lesson", "status": "done", "stage": "Ready", "progress": 1.0, "error": None})
    resume.record({"id": "j1", "kind": "lesson", "status": "running", "stage": "Narrating", "progress": 0.7, "error": None, "lesson_id": "abc"})
    rows = {r["id"]: r for r in resume.recent()}
    assert rows["j1"]["progress"] == 0.7 and rows["j1"]["lesson_id"] == "abc"
    assert resume.mark_interrupted() == 1
    rows = {r["id"]: r for r in resume.recent()}
    assert rows["j1"]["status"] == "interrupted" and rows["j2"]["status"] == "done"
    assert sqlite3.connect(resume.DB_PATH).execute("select count(*) from jobs").fetchone()[0] == 2


def test_submitting_a_job_records_it(db):
    job = jobs.submit("export", lambda progress: progress("Half", 0.5) or {"ok": True})
    import time
    for _ in range(50):
        if jobs.get(job["id"])["status"] == "done":
            break
        time.sleep(0.05)
    assert {r["id"]: r for r in resume.recent()}[job["id"]]["status"] == "done"


def write_lesson(root, name, **extra):
    d = root / name
    d.mkdir(parents=True)
    (d / "lesson.json").write_text(json.dumps({"id": name, "concept": "X", "languages": {"en": {"scenes": []}}, **extra}), encoding="utf-8")
    return d


def test_startup_resumes_pending_languages_and_closes_cut_off_lessons(db, tmp_path):
    root = tmp_path / "lessons"
    write_lesson(root, "done1")
    write_lesson(root, "half2", pending=[{"code": "hi", "name": "Hindi", "native": "हिन्दी"}], plan={"title": "X", "scenes": []})
    write_lesson(root, "cut3", building=True, pending=[{"code": "hi"}])
    submitted = []
    out = resume.on_startup(submit=lambda kind, fn, *a: submitted.append((kind, fn.__name__, a)), lessons_dir=root)
    assert out["resumed_lessons"] == ["half2"] and out["cut_short_lessons"] == ["cut3"]
    assert submitted == [("langs", "resume_languages", ("half2",))]                       # resumed on its own worker, from the saved plan
    cut = json.loads((root / "cut3" / "lesson.json").read_text(encoding="utf-8"))
    assert "building" not in cut and cut["pending"] == [] and cut["interrupted"] is True   # it stops being "in progress"
    assert resume.on_startup(submit=lambda *a: submitted.append(a), lessons_dir=root)["cut_short_lessons"] == []     # and is not touched twice


# ------------------------------------------------------------------ the new routes
@pytest.fixture()
def client(tmp_path, monkeypatch):
    from app import main, pipeline, srs
    monkeypatch.setattr(srs, "DB_PATH", tmp_path / "learning.db")
    monkeypatch.setattr(resume, "DB_PATH", tmp_path / "jobs.db")
    lesson = {"id": "L1", "concept": "Seasons", "languages": {"en": {"title": "Seasons", "scenes": [
        {"heading": "Tilt", "narration": "The Earth is tilted.", "start_s": 0, "duration_s": 2, "captions": [{"start": 0, "end": 1, "text": "The Earth"}]}], "duration_s": 2}}}
    monkeypatch.setattr(main, "load_lesson", lambda i: lesson if i == "L1" else (_ for _ in ()).throw(FileNotFoundError(i)))
    monkeypatch.setattr(pipeline, "LESSONS_DIR", tmp_path / "lessons")
    from app import exports
    monkeypatch.setattr(exports, "load_lesson", lambda i: lesson)
    monkeypatch.setattr(exports, "LESSONS_DIR", tmp_path / "lessons")
    from app import teachback
    monkeypatch.setattr(teachback, "load_lesson", lambda i: lesson)
    return TestClient(main.app)


def test_subtitles_download_and_unknown_language(client):
    r = client.get("/api/lessons/L1/subtitles?lang=en&fmt=vtt")
    assert r.status_code == 200 and r.text.startswith("WEBVTT") and "attachment" in r.headers["content-disposition"]
    assert client.get("/api/lessons/L1/subtitles?lang=hi").status_code == 404
    assert client.get("/api/lessons/NOPE/subtitles").status_code == 404


def test_review_weak_and_profile_routes(client):
    assert client.get("/api/review/due?day=2026-10-27").json()["due"] >= 0
    assert client.post("/api/review/answer", json={"card_id": "missing", "quality": 4}).status_code == 404
    assert client.post("/api/weak/answer", json={"lesson_id": "L1", "question": "Why?", "correct": False}).json()["weak"][0]["topic"] == "Seasons"
    assert client.get("/api/weak").json()["weak"][0]["wrong"] == 1
    assert client.post("/api/weak/answer", json={"lesson_id": "L1", "question": "Why?", "correct": True}).status_code == 200
    r = client.post("/api/profile", json={"name": "Priya", "age": 12})
    assert r.status_code == 200 and client.get("/api/profile").json()["age"] == 12
    assert client.post("/api/profile", json={"age": 500}).status_code == 422                # out of range is refused, not clamped silently


def test_teachback_route_refuses_empty_explanations(client):
    assert client.post("/api/lessons/L1/teachback", json={"text": "no"}).status_code == 400


def test_a_lesson_still_being_made_cannot_be_bundled(client, tmp_path, monkeypatch):
    from app import bundle
    monkeypatch.setattr(bundle, "export_bundle", lambda i: (_ for _ in ()).throw(bundle.BundleError("still being made")))
    assert client.get("/api/lessons/L1/bundle").status_code == 409
