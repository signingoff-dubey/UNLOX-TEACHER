from app import llm, planner
from app.schema import LessonPlan


def build(concept):
    sp, drop = planner.system_prompt(concept)
    return sp, llm.with_schema(sp, LessonPlan, drop)


def test_a_general_topic_gets_a_prompt_without_graph_and_code_material():
    sp, full = build("The water cycle")
    assert "- graph:" not in sp and "- code:" not in sp and "Example graph scene" not in sp and "Example code scene" not in sp
    assert "curves" not in full and "highlights" not in full and "code_lang" not in full          # their fields are not in the example shape either
    assert "- cycle:" in sp and "- quiz:" in sp and "Rules:" in sp and "icon must be one of" in sp   # everything every lesson needs is still there
    assert "graph, " not in sp and "code, " not in sp                                              # even the variety sentence does not offer them
    assert len(full) < 0.5 * len(llm.with_schema(planner.SYSTEM_PROMPT, LessonPlan))               # about half the old prompt (measured: first scene 3.2 s -> 1.2 s)


def test_maths_and_programming_topics_keep_what_they_need():
    maths_sp, maths = build("Equation of a circle in maths")
    assert "- graph:" in maths_sp and "Example graph scene" in maths_sp and "curves" in maths and "- code:" not in maths_sp and "code_lang" not in maths
    code_sp, code = build("Teach me Python loops")
    assert "- code:" in code_sp and "Example code scene" in code_sp and "highlights" in code and "- graph:" not in code_sp and "curves" not in code


def test_an_unknown_subject_keeps_everything():
    for concept in ("", "the main ideas of chapter 4 from the textbook " + "x" * 120):                # a whole PDF, a photo: the planner has to be free to choose
        sp, full = build(concept)
        assert "- graph:" in sp and "- code:" in sp and "curves" in full and "highlights" in full


def test_the_planner_sends_the_subject_prompt(monkeypatch):
    seen = {}

    def fake_stream(messages, options=None, **kw):
        seen["system"] = messages[0]["content"]
        return "{}"

    monkeypatch.setattr(planner.llm, "stream_chat", fake_stream)
    planner._ollama_chat("How do vaccines work", "", duration_s=60)
    assert "curves" not in seen["system"] and "- cycle:" in seen["system"]
    planner._ollama_chat("circle and parabola graphs in maths", "", duration_s=60)
    assert "curves" in seen["system"]
