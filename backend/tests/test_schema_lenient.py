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


def test_common_mistakes_become_one_compare_scene_before_the_closing_quiz():
    from app.schema import LessonPlan, normalize
    plan = LessonPlan.model_validate({"title": "Seasons", "common_mistakes": [
        {"wrong": "Seasons come from distance to the sun", "right": "They come from the tilt of the Earth"}, {"wrong": "", "right": "x"}],
        "scenes": [{"template": "title", "heading": "Seasons", "narration": "Why do we have seasons?"},
                   {"template": "bullets", "heading": "Tilt", "narration": "The Earth is tilted.", "items": ["Tilt", "Orbit"]},
                   {"template": "flow", "heading": "Year", "narration": "It goes around the sun.", "items": ["Summer", "Autumn", "Winter"]},
                   {"template": "quiz", "heading": "Why?", "narration": "Pick one.", "items": ["Tilt", "Distance", "Moon"], "answer_index": 0}]})
    kinds = [s.template for s in normalize(plan).scenes]
    assert kinds == ["title", "bullets", "flow", "compare", "quiz"]                       # placed before the quiz, one scene
    scene = normalize(plan).scenes[3]
    assert scene.left == ["Seasons come from distance to the sun"] and scene.right == ["They come from the tilt of the Earth"]
    assert "common mistake" in scene.narration.lower()
    # nothing to add without the field
    plain = LessonPlan.model_validate({"title": "T", "scenes": [{"template": "title", "heading": "T", "narration": "Hello there."}, {"template": "bullets", "heading": "A", "narration": "Some words here.", "items": ["a", "b"]}, {"template": "bullets", "heading": "B", "narration": "More words here.", "items": ["a", "b"]}, {"template": "quiz", "heading": "Q", "narration": "Pick.", "items": ["a", "b", "c"]}]})
    assert "Common mistakes" not in [s.heading for s in normalize(plain).scenes]
