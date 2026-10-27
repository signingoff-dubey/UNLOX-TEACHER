from app import longplan
from app.schema import LessonPlan, ScenePlan


def _part(n: int) -> LessonPlan:
    return LessonPlan(title="x", scenes=[ScenePlan(template="bullets", heading=f"H{n}.{k}", narration="Some words here.", items=["a", "b"]) for k in range(3)])


def test_parts_for_scales_with_length():
    assert longplan.parts_for(120) == 3
    assert longplan.parts_for(240) == 6
    assert longplan.parts_for(999) == 6          # capped at 4 minutes


def test_long_video_joins_parts_in_order(monkeypatch):
    calls = []

    def fake_plan(topic, level, duration_s, upload, focus, wps, series, on_progress, extra="", mode="explain"):
        calls.append(series)
        on_progress(1.0)
        return _part(series["index"]), [{"title": "Book", "section": "Ch 1"}]

    monkeypatch.setattr(longplan, "plan_lesson", fake_plan)
    monkeypatch.setattr(longplan.config, "LLM_BACKEND", "mock")        # generic outline, no model call
    seen = []
    plan, sources = longplan.plan_long("Photosynthesis", "beginner", 160, None, "", 2.3, seen.append)
    assert len(calls) == 4 and len(plan.scenes) == 12
    assert [c["index"] for c in calls] == [1, 2, 3, 4] and calls[-1]["next"] == "" and calls[0]["previous"] == []
    assert len(calls[3]["previous"]) == 3                               # each part knows what was taught before
    assert sources == [{"title": "Book", "section": "Ch 1"}]            # duplicate sources collapse
    assert seen[-1] == 1.0 and seen == sorted(seen)
