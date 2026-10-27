from app.schema import LessonPlan, ScenePlan, normalize


def test_scene_objects_are_kept_when_a_plan_is_built_in_code():
    """The director builds a LessonPlan from ScenePlan objects; the validator that drops junk must not drop those."""
    plan = LessonPlan(title="T", scenes=[ScenePlan(template="title", heading="T", narration="x"),
                                          ScenePlan(template="flow", heading="Steps", narration="First this, then that.", items=["a", "b", "c"])])
    assert len(plan.scenes) == 2
    assert len(normalize(plan).scenes) == 2


def test_model_junk_is_repaired_or_dropped():
    raw = ('{"title": {"template": "title", "heading": "Hello"}, "scenes": [{}, "stray", '
           '{"template": "Graph", "heading": 5, "narration": "ok", "icon": "banana", "code": "a = 1", "x_range": "auto", "highlights": "0, 2"}]}')
    plan = LessonPlan.model_validate_json(raw)
    assert plan.title == "Hello"                                         # a nested first scene becomes the title
    assert len(plan.scenes) == 1                                         # the empty {} and the stray string are gone
    s = plan.scenes[0]
    assert (s.template, s.heading, s.icon, s.code, s.x_range, s.highlights) == ("graph", "5", "lightbulb", ["a = 1"], [], [0, 2])
