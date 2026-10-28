import json

import pytest
import requests

from app import config, content, llm, longplan, memory, planner, selfcheck
from app.schema import LessonPlan, ScenePlan


def sc(template="bullets", heading="H", narration="A full sentence that explains the idea in enough detail, with a specific example and a reason, so the learner gains something.", **kw):
    return ScenePlan(template=template, heading=heading, narration=narration, items=kw.pop("items", [f"{heading} one", f"{heading} two", f"{heading} three"]), **kw)


# ------------------------------------------------------------------ memory: what already exists
def lesson(lid, concept, headings, code=None):
    scenes = [{"template": "title", "heading": concept, "narration": "Hook.", "items": []}]
    for h in headings:
        scenes.append({"template": "bullets", "heading": h, "narration": f"{h} explained in a sentence. More words follow here.", "items": [f"{h} point"], "code": code or []})
    return {"id": lid, "concept": concept, "created": 1, "plan": {"title": concept, "scenes": scenes}}


@pytest.fixture
def library(tmp_path, monkeypatch):
    from app import pipeline
    monkeypatch.setattr(pipeline, "LESSONS_DIR", tmp_path)
    memory.clear()

    def add(l):
        d = tmp_path / l["id"]
        d.mkdir()
        (d / "lesson.json").write_text(json.dumps(l), encoding="utf-8")
    yield add
    memory.clear()


def test_the_planner_is_told_what_the_learner_already_has(library):
    library(lesson("a1", "Binary search trees", ["Left is smaller", "Right is larger", "Searching a BST"], code=["struct Node *left;"]))
    library(lesson("b2", "How tides work", ["The moon pulls", "Spring tides"]))
    assert "Binary search trees" in memory.context("AVL trees")           # a BST video is related to an AVL request: AVL builds on it
    text = memory.context("binary search trees in C")
    assert "Binary search trees" in text and "Left is smaller" in text and "struct Node *left;" in text and "tides" not in text.lower()
    assert "Do NOT repeat" in text


def test_a_retry_of_the_same_request_is_not_treated_as_something_to_avoid(library):
    library(lesson("a1", "AVL trees", ["Balance factor", "Rotations"]))
    assert memory.context("avl trees") == ""
    assert memory.context("AVL trees in C")


def test_memory_never_breaks_a_lesson(monkeypatch):
    monkeypatch.setattr(memory, "library", lambda exclude=None: (_ for _ in ()).throw(RuntimeError("disk gone")))
    assert memory.context("anything") == ""


# ------------------------------------------------------------------ subjects, languages, networks
@pytest.mark.parametrize("text, code, net, lang", [
    ("teach me what avl trees are", True, True, ""),
    ("What is AVL Trees in DSA in C language", True, True, "c"),
    ("python loops", True, False, "python"),
    ("how does a refrigerator work", False, False, ""),
    ("linked lists in c", True, True, "c"),
    ("the letter c", False, False, ""),
    ("Dijkstra in Java", True, True, "java"),
])
def test_subjects_and_the_language_the_learner_named(text, code, net, lang):
    assert planner.subject_of(text)[1] is code and planner.network_subject(text) is net and planner.language_of(text) == lang


def test_a_tree_topic_gets_the_network_template_and_others_do_not():
    avl, drop = planner.system_prompt("AVL trees in C")
    assert "- network:" in avl and "Example network scene" in avl and "nodes" not in drop
    fridge, drop2 = planner.system_prompt("how does a refrigerator work")
    assert "- network:" not in fridge and {"nodes", "edges", "positions"} <= drop2


def test_a_technical_lesson_of_only_text_is_sent_back():
    text_only = LessonPlan(title="AVL", scenes=[sc("title", "Hook"), sc("bullets", "A"), sc("flow", "B"), sc("compare", "C"), sc("cycle", "D"), sc("summary", "E")])
    assert "show it" in planner.quality_issue(text_only, technical=True)
    assert planner.quality_issue(text_only, technical=False) is None
    drawn = LessonPlan(title="AVL", scenes=[sc("title", "Hook"), sc("bullets", "A"), sc("code", "B", code=["int x;"], code_lang="c"), sc("compare", "C"), sc("summary", "E")])
    assert planner.quality_issue(drawn, technical=True) is None


def test_a_lesson_built_on_one_everyday_comparison_is_sent_back():
    like = "An AVL tree is like a seesaw: if one side gets too heavy, it just like a seesaw tips over and needs balancing again now."
    p = LessonPlan(title="AVL", scenes=[sc("title", "Hook")] + [sc("bullets", f"Idea {i}", like) for i in range(4)] + [sc("summary", "End")])
    assert content.analogy_overload(p) and "everyday object" in planner.quality_issue(p)
    plain = LessonPlan(title="AVL", scenes=[sc("title", "Hook")] + [sc("bullets", f"Idea {i}") for i in range(4)] + [sc("summary", "End")])
    assert not content.analogy_overload(plain)


# ------------------------------------------------------------------ retries
def test_ollama_calls_are_repeated_when_the_server_is_busy(monkeypatch):
    calls = []

    class R:
        def __init__(self, code): self.status_code = code

    def fake_post(url, json=None, timeout=None, stream=False):
        calls.append(url)
        if len(calls) < 3:
            raise requests.ConnectionError("restarting")
        return R(200)

    monkeypatch.setattr(llm.requests, "post", fake_post)
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    assert llm.post("/api/chat", {}, timeout=5).status_code == 200 and len(calls) == 3
    calls.clear()
    monkeypatch.setattr(llm.requests, "post", lambda *a, **k: (_ for _ in ()).throw(requests.ConnectionError("down")))
    with pytest.raises(requests.ConnectionError):
        llm.post("/api/chat", {}, timeout=5)


def test_a_refused_request_is_not_repeated(monkeypatch):
    n = []

    class R:
        status_code = 404

    monkeypatch.setattr(llm.requests, "post", lambda *a, **k: n.append(1) or R())
    assert llm.post("/api/chat", {}, timeout=5).status_code == 404 and len(n) == 1


# ------------------------------------------------------------------ Pro: outline first, then write with everything in view
class FakeBeats(longplan.Beats):
    pass


def test_pro_outlines_every_scene_then_writes_in_calls_that_see_the_whole_outline(monkeypatch):
    n = longplan.scenes_for(180)
    beats = longplan.Beats(title="AVL trees", beats=[longplan.Beat(heading=f"Idea {i}", template="bullets", point=f"point {i}") for i in range(n)])
    monkeypatch.setattr(longplan, "beat_sheet", lambda *a, **k: beats)
    prompts = []

    def fake_plan(topic, **kw):
        s = kw["series"]
        prompts.append(s)
        k = s["scenes"]
        scenes = [sc("bullets", f"Written {s['index']}-{j}", f"Narration for scene {j} of call {s['index']} with enough words to count as teaching something real.") for j in range(k)]
        return LessonPlan(title="t", scenes=scenes), [{"title": "Src", "section": ""}]

    monkeypatch.setattr("app.planner.plan_lesson", fake_plan)
    plan, sources = longplan.plan_pro("AVL trees", "beginner", 180, None, "", 2.3)
    assert len(prompts) == 3 and sum(p["scenes"] for p in prompts) == n                       # 3 minutes: the first minute, then two minutes patched on
    assert prompts[0]["taught"] == "" and "Written 1-0" in prompts[1]["taught"]                 # the second call has the full text of the first
    assert "Idea 0" in prompts[0]["beats"] and prompts[1]["previous"][0] == "Idea 0"
    assert len(plan.scenes) <= n and sources == [{"title": "Src", "section": ""}]


def test_pro_without_an_outline_still_plans_the_video(monkeypatch):
    monkeypatch.setattr(longplan, "beat_sheet", lambda *a, **k: None)
    monkeypatch.setattr(longplan, "plan_long", lambda *a, **k: ("PLAN", []))
    assert longplan.plan_pro("x", "beginner", 120, None, "", 2.3) == ("PLAN", [])


def test_a_course_episode_in_pro_knows_the_other_episodes(monkeypatch):
    seen = {}

    def spy(concept, n, level, duration_s, library, technical, language):
        seen["library"] = library
    monkeypatch.setattr(longplan, "beat_sheet", lambda *a, **k: spy(*a) or None)
    monkeypatch.setattr(longplan, "plan_long", lambda *a, **k: ("PLAN", []))
    longplan.plan_pro("AVL trees: Rotations", "beginner", 60, None, "", 2.3,
                      course={"index": 2, "total": 3, "title": "AVL trees", "this": "rotations", "previous": ["Balance factor"], "taught": "- Balance factor: height difference"})
    assert "episode 2 of 3" in seen["library"] and "Balance factor" in seen["library"]


# ------------------------------------------------------------------ the self-check
def test_the_self_check_names_what_to_run(monkeypatch):
    monkeypatch.setattr(selfcheck.requests, "get", lambda *a, **k: (_ for _ in ()).throw(requests.ConnectionError("no")))
    rep = selfcheck.report()
    assert rep["status"] == "fail" and not rep["ready"] and "ollama serve" in rep["checks"][0]["fix"]

    class Tags:
        def json(self): return {"models": [{"name": config.OLLAMA_MODEL}]}
    monkeypatch.setattr(selfcheck.requests, "get", lambda *a, **k: Tags())
    assert selfcheck.report()["ready"] is True or all(c["status"] != "fail" for c in selfcheck.report()["checks"])


def test_only_the_first_everyday_comparison_of_a_technical_video_is_kept():
    p = LessonPlan(title="AVL", scenes=[
        sc("title", "Hook", "Have you wondered why trees tip over when you keep adding to one side?"),
        sc("flow", "A", "A balanced tree has nearly equal heights on both sides, just like a well-maintained seesaw."),
        sc("flow", "B", "AVL trees are self-balancing, so every node keeps its subtrees within one level of height, just like stacking books evenly on a shelf."),
        sc("flow", "C", "It's like finding a book in a library index. The balance factor of a node is the height of its left subtree minus the height of its right subtree."),
        sc("flow", "D", "Rotations restore order after an insert without ever changing the sorted order of the keys.")])
    notes = content.strip_analogies(p, keep=1)
    assert len(notes) == 2 and "seesaw" in p.scenes[1].narration                # the first comparison stays
    assert "books" not in p.scenes[2].narration and "library" not in p.scenes[3].narration and "balance factor" in p.scenes[3].narration
    assert p.scenes[4].narration.startswith("Rotations")                         # a sentence without a comparison is untouched


def test_a_comparison_is_not_removed_when_it_is_all_the_narration_says():
    p = LessonPlan(title="T", scenes=[sc("flow", "A", "A tree is like a seesaw, just like a seesaw."), sc("flow", "B", "It is like a book.")])
    content.strip_analogies(p, keep=0)
    assert p.scenes[1].narration == "It is like a book."
