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

    def fake_plan(topic, level, duration_s, upload, focus, wps, series, on_progress, extra="", mode="explain", on_text=None):
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
    assert sorted(streamed) == [(1, True), (2, False), (3, False)]                      # only part 1 is streamed token by token
    assert [h[0] for h in handed] == ["H2.0", "H3.0"]                                   # parts 2 and 3 whole, in order
