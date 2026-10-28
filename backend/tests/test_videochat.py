import pytest

from app import jobs, playlist, videochat


@pytest.mark.parametrize("message, topic, seconds", [
    ("generate one more video on black holes", "black holes", None),
    ("Generate another video about the French Revolution", "the French Revolution", None),
    ("can you make a video on photosynthesis for 2 minutes", "photosynthesis", 120),
    ("please create one more lesson about tides, 90 seconds", "tides", 90),
    ("make another one on volcanoes", "volcanoes", None),
    ("generate one more", "", None),
    ("make another video", "", None),
    ("I want you to make a new video explaining how vaccines work", "how vaccines work", None),
    ("another video on the water cycle please", "the water cycle", None),
    ("Create a short video about Newton's third law", "Newton's third law", None),
    ("make me a 3 minute video on recursion", "recursion", 180),
    ("generate a video that explains inflation", "inflation", None),
    ("let's make one more video about gravity", "gravity", None),
])
def test_requests_for_another_video_are_recognised(message, topic, seconds):
    got = videochat.detect(message)
    assert got is not None, message
    assert got["topic"].lower() == topic.lower() and got["duration_s"] == seconds, got


@pytest.mark.parametrize("message", [
    "how do I make a video?",
    "what is this video about",
    "explain this part again",
    "give me another example",
    "give me one more example of a tide",
    "make it simpler",
    "can you make this shorter",
    "why does the moon pull the water",
    "quiz me",
    "generate a quiz",
    "is this video long",
    "the video was made well",
])
def test_normal_questions_are_left_to_the_tutor(message):
    assert videochat.detect(message) is None, message


LESSON = {"id": "L1", "concept": "Tides", "order": ["en", "hi"], "documents": [],
          "languages": {"en": {"title": "How tides work", "duration_s": 62.0}, "hi": {"title": "x", "duration_s": 90.0}}}


@pytest.fixture()
def store(monkeypatch, tmp_path):
    monkeypatch.setattr(playlist, "PLAYLISTS_DIR", tmp_path / "playlists")
    monkeypatch.setattr(videochat, "load_lesson", lambda i: LESSON)
    started = []
    monkeypatch.setattr(jobs, "submit", lambda kind, fn, *args: started.append((kind, fn.__name__, args)) or {"id": "job1"})
    return started


def test_a_lesson_on_its_own_is_wrapped_into_a_playlist_with_the_new_video_added(store):
    res = videochat.handle("L1", {"topic": "Black holes", "duration_s": 120})
    v = res["video"]
    assert v["new_playlist"] and v["index"] == 1 and v["job_id"] == "job1" and v["title"] == "Black holes" and v["seconds"] == 120
    assert "Black holes" in res["reply"] and "play button" in res["reply"]
    assert store == [("lesson", "build_extra", (v["playlist_id"], 1))]               # started at once, on the lesson queue (not behind a course)
    pl = playlist.load(v["playlist_id"])
    assert [e["status"] for e in pl["episodes"]] == ["ready", "pending"] and pl["episodes"][0]["lesson_id"] == "L1" and pl["status"] == "building"
    assert pl["episodes"][1]["extra"] and pl["episodes"][1]["target_s"] == 120 and not pl["episodes"][1]["continues"]


def test_a_second_request_joins_the_same_playlist(store):
    first = videochat.handle("L1", {"topic": "Black holes", "duration_s": None})["video"]
    second = videochat.handle("L1", {"topic": "", "duration_s": None})["video"]
    assert second["playlist_id"] == first["playlist_id"] and second["index"] == 2 and not second["new_playlist"]
    ep = playlist.load(first["playlist_id"])["episodes"][2]
    assert ep["continues"] and ep["title"] == "More on Tides"                       # no topic: more of the same, from a new angle


def test_the_playlist_is_capped_and_a_course_in_progress_is_not_disturbed(store):
    v = videochat.handle("L1", {"topic": "A", "duration_s": None})["video"]
    for k in range(playlist.MAX_TOTAL):
        res = videochat.handle("L1", {"topic": f"T{k}", "duration_s": None})
    assert "already has" in res["reply"] and "video" not in res
    pl = playlist.load(v["playlist_id"])
    pl["episodes"] = [{"index": 0, "title": "x", "focus": "x", "lesson_id": "L1", "status": "building", "error": None}]       # a course still being made
    pl["status"] = "building"
    playlist.save(pl)
    with pytest.raises(ValueError):
        playlist.append_episode(pl["id"], "More", "More", 60)


def test_the_extra_video_is_built_scene_by_scene_and_marked_ready(store, monkeypatch):
    v = videochat.handle("L1", {"topic": "Black holes", "duration_s": 60})["video"]
    seen = []

    def fake_build(concept, languages, level, duration_s, documents, series=None, images=None, mode="explain", progressive=False, quality="flash", progress=None):
        seen.append((concept, languages, duration_s, series, progressive))
        progress("Planning", 0.1, lesson_id="NEW1")                                   # scene 1 exists
        mid = playlist.load(v["playlist_id"])["episodes"][1]
        seen.append((mid["status"], mid["lesson_id"], mid["preview"]))              # the page can open it already
        return {"id": "NEW1", "languages": {"en": {"duration_s": 61.0}, "hi": {"duration_s": 90.0}}}

    monkeypatch.setattr(playlist, "build_lesson", fake_build)
    reported = []
    out = playlist.build_extra(v["playlist_id"], v["index"], lambda s, p, **kw: reported.append(kw))
    assert out["lesson_id"] == "NEW1" and reported == [{"lesson_id": "NEW1"}]
    assert seen[0] == ("Black holes", ["en", "hi"], 60, None, True) and seen[1] == ("building", "NEW1", True)
    pl = playlist.load(v["playlist_id"])
    ep = pl["episodes"][1]
    assert ep["status"] == "ready" and ep["lesson_id"] == "NEW1" and ep["duration_s"] == 90.0 and ep["preview"] is False and pl["status"] == "ready"


def test_a_failed_extra_video_is_marked_failed_and_the_playlist_stays_usable(store, monkeypatch):
    v = videochat.handle("L1", {"topic": "Black holes", "duration_s": 60})["video"]
    monkeypatch.setattr(playlist, "build_lesson", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("model down")))
    with pytest.raises(RuntimeError):
        playlist.build_extra(v["playlist_id"], v["index"])
    pl = playlist.load(v["playlist_id"])
    assert pl["episodes"][1]["status"] == "failed" and "model down" in pl["episodes"][1]["error"] and pl["status"] == "partial"
