from app import longplan
from app.schema import LessonPlan, ScenePlan


def _part(n: int) -> LessonPlan:
    return LessonPlan(title="x", scenes=[ScenePlan(template="bullets", heading=f"H{n}.{k}", narration="Some words here.", items=["a", "b"]) for k in range(3)])


def test_parts_for_scales_with_length():
    assert longplan.parts_for(120) == 4          # a 2 minute video is 4 parts of 30 s
    assert longplan.parts_for(240) == 8
    assert longplan.parts_for(999) == 8          # capped at 4 minutes


def test_long_video_joins_parts_in_order(monkeypatch):
    calls = []

    def fake_plan(topic, level, duration_s, upload, focus, wps, series, on_progress, extra="", mode="explain", on_text=None):
        calls.append(series)
        on_progress(1.0)
        return _part(series["index"]), [{"title": "Book", "section": "Ch 1"}]

    monkeypatch.setattr(longplan, "plan_lesson", fake_plan)
    monkeypatch.setattr(longplan.config, "LLM_BACKEND", "mock")        # generic outline, no model call
    seen = []
    plan, sources = longplan.plan_long("Photosynthesis", "beginner", 120, None, "", 2.3, seen.append)
    assert len(calls) == 4 and len(plan.scenes) == 12
    assert [c["index"] for c in calls] == [1, 2, 3, 4] and calls[-1]["next"] == "" and calls[0]["previous"] == []
    assert len(calls[3]["previous"]) == 3                               # each part knows what was taught before
    assert sources == [{"title": "Book", "section": "Ch 1"}]            # duplicate sources collapse
    assert seen[-1] == 1.0 and seen == sorted(seen)


def test_parts_reach_the_player_in_order_and_only_the_first_part_streams(monkeypatch):
    import time
    streamed, handed = [], []

    class Preview:
        feed = staticmethod(lambda text: None)

        def add_scenes(self, objs):
            handed.append([o["heading"] for o in objs])

    def fake_plan(topic, level, duration_s, upload, focus, wps, series, on_progress, extra="", mode="explain", on_text=None):
        streamed.append((series["index"], on_text is not None))
        if series["index"] == 1:
            time.sleep(0.15)                                            # part 1 is the slowest: part 2 must still wait for it
        return _part(series["index"]), []

    monkeypatch.setattr(longplan, "plan_lesson", fake_plan)
    monkeypatch.setattr(longplan.config, "LLM_BACKEND", "mock")
    longplan.plan_long("Tides", "beginner", 120, None, "", 2.3, preview=Preview())
    assert sorted(streamed) == [(1, True), (2, False), (3, False), (4, False)]          # only part 1 is streamed token by token
    assert [h[0] for h in handed] == ["H2.0", "H3.0", "H4.0"]                           # parts 2, 3, 4 whole, in order
