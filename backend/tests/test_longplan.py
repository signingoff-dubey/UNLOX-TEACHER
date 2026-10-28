from app import longplan
from app.schema import LessonPlan, ScenePlan


def _part(n: int) -> LessonPlan:
    return LessonPlan(title="x", scenes=[ScenePlan(template="bullets", heading=f"H{n}.{k}", narration=" ".join(f"word{n}{k}{j}" for j in range(20)), items=["a", "b"]) for k in range(3)])


def test_parts_for_scales_with_length():
    assert longplan.parts_for(120) == 3          # a 2 minute video is 3 parts of 40 s
    assert longplan.parts_for(100) == 2
    assert longplan.parts_for(240) == 3          # never more than 3: more parts make a less coherent video
    assert longplan.parts_for(999) == 3


def test_long_video_joins_parts_in_order(monkeypatch):
    calls = []

    def fake_plan(topic, level, duration_s, upload, focus, wps, series, on_progress, extra="", mode="explain", on_text=None, fast=False):
        calls.append(series)
        on_progress(1.0)
        return _part(series["index"]), [{"title": "Book", "section": "Ch 1"}]

    monkeypatch.setattr(longplan, "plan_lesson", fake_plan)
    monkeypatch.setattr(longplan.config, "LLM_BACKEND", "mock")        # generic outline, no model call
    seen = []
    plan, sources = longplan.plan_long("Photosynthesis", "beginner", 120, None, "", 2.3, seen.append)
    assert len(calls) == 3 and len(plan.scenes) == 9
    assert [c["index"] for c in calls] == [1, 2, 3] and calls[-1]["next"] == "" and calls[0]["previous"] == []
    assert len(calls[2]["previous"]) == 2                               # each part knows what was taught before
    assert "H1.0" in calls[1]["taught"] and "H2.0" in calls[2]["taught"] and calls[0]["taught"] == ""     # ... and what its headings and points really were
    assert sources == [{"title": "Book", "section": "Ch 1"}]            # duplicate sources collapse
    assert seen[-1] == 1.0 and seen == sorted(seen)


def test_every_part_streams_to_the_player_and_later_parts_hide_their_title_and_early_recaps(monkeypatch):
    streamed, fast_flags = [], []

    class Preview:
        def __init__(self):
            self.rejects = []

        def feed(self, text):
            streamed.append(("main", text))

        def stream(self, reject=None):
            self.rejects.append(reject)
            k = len(self.rejects)
            return lambda text: streamed.append((k, text))

    def fake_plan(topic, level, duration_s, upload, focus, wps, series, on_progress, extra="", mode="explain", on_text=None, fast=False):
        fast_flags.append(fast)
        on_text(f"part {series['index']}")
        return _part(series["index"]), []

    monkeypatch.setattr(longplan, "plan_lesson", fake_plan)
    monkeypatch.setattr(longplan.config, "LLM_BACKEND", "mock")
    pv = Preview()
    longplan.plan_long("Tides", "beginner", 120, None, "", 2.3, preview=pv)
    assert streamed == [("main", "part 1"), (1, "part 2"), (2, "part 3")]               # every part token by token, in order
    assert fast_flags == [True, True, True]                                             # Flash: no slow retries while the learner watches
    middle, last = pv.rejects
    assert middle({"template": "title"}) and middle({"template": "summary"}) and not middle({"template": "code"})
    assert last({"template": "title"}) and not last({"template": "summary"}) and not last({"template": "quiz"})
