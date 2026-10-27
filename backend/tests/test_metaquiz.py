import pytest

from app import metaquiz, studio


def scene(template, heading, narration, items=(), **kw):
    return {"template": template, "heading": heading, "narration": narration, "items": list(items), "left": [], "right": [],
            "answer_index": kw.get("answer_index", 0), "code": kw.get("code", [])}


def lesson(lid, title, headings):
    scenes = [scene("title", title, f"Welcome to {title}.")]
    scenes += [scene("bullets", h, f"{h} is explained here with plain words about {h.lower()} and light.", [f"{h} idea", f"{h} fact"]) for h in headings]
    scenes.append(scene("quiz", f"What is {headings[0]}?", "Quick question.", [f"{headings[0]} idea", "Nothing", "Sand"], answer_index=0))
    scenes.append(scene("summary", "Remember", f"You learned {', '.join(headings)}."))
    return {"id": lid, "concept": title, "languages": {"en": {"title": title, "scenes": scenes}}, "plan": {"title": title, "scenes": scenes}}


TOOLS = {
    "quiz": [{"questions": [{"question": "Which gas do leaves release?", "options": ["Oxygen", "Neon", "Helium"], "answer_index": 0,
                             "explanation": "Leaves release oxygen as a by-product."}]}],
    "flashcards": [{"cards": [{"front": "What is chlorophyll?", "back": "The green pigment that absorbs light"},
                              {"front": "What are stomata?", "back": "Tiny pores in leaves"},
                              {"front": "Where does sugar form?", "back": "Inside the chloroplasts"},
                              {"front": "What do roots absorb?", "back": "Water from the soil"}]}],
    "glossary": [{"terms": [{"term": "Light", "meaning": "The energy that powers the process"}, {"term": "Water", "meaning": "Taken up by the roots"}]}],
    "faq": [{"items": [{"question": "Why are leaves green?", "answer": "Chlorophyll reflects green light."}]}],
    "studyguide": [{"overview": "Plants make food from light.", "key_points": ["Light is the energy source.", "Water comes from the roots."],
                    "terms": [], "review_questions": []}],
    "timeline": [{"events": [{"label": "Light is captured", "detail": "Leaves absorb sunlight."}]}],
    "mindmap": [{"root": "Photosynthesis", "branches": [{"label": "Inputs", "children": [{"label": "Light", "details": []}]}], "mermaid": ""}],
}


@pytest.fixture()
def single(monkeypatch):
    lessons = {"A": lesson("A", "Photosynthesis", ["Sunlight", "Water", "Leaves", "Sugar", "Oxygen"])}
    monkeypatch.setattr(metaquiz, "load_lesson", lambda i: lessons[i])
    monkeypatch.setattr(metaquiz, "tools_for", lambda i, lang: TOOLS)
    monkeypatch.setattr(studio, "ensure", lambda *a, **k: pytest.fail("everything exists, nothing should be generated"))
    return lessons


def test_world_has_four_stations_and_uses_every_tool(single):
    out = metaquiz.build_world(["A"], "A", "en", "Photosynthesis")
    w = out["world"]
    assert len(w["zones"]) == 4
    assert out["stats"]["tools"] == sorted(TOOLS) and out["stats"]["videos"] == 1
    for z in w["zones"]:
        assert z["quiz"]["options"][z["quiz"]["answer"]]                      # the right answer is one of the options
        assert z["info"]["body"] and z["info"]["terms"]
    assert out["stats"]["questions"] >= 5
    labels = {x["label"] for z in w["zones"] for x in z["info"]["extra"]}
    assert {"Key point", "Overview"} <= labels                                 # study guide
    assert any(lab.startswith("Step 1") for lab in labels) and any(lab.startswith("Map:") for lab in labels)
    assert any(x["label"] == "Why are leaves green?" for z in w["zones"] for x in z["info"]["extra"])
    assert any(q["why"] for z in w["zones"] for q in [z["quiz"], *z["more"]])  # explanations from the quiz tool reach the world


def test_no_question_is_repeated(single):
    zones = metaquiz.build_world(["A"], "A", "en", "")["world"]["zones"]
    qs = [q["q"].lower() for z in zones for q in [z["quiz"], *z["more"]]]
    assert len(qs) == len(set(qs))


def test_course_groups_videos_into_stations(monkeypatch):
    lessons = {c: lesson(c, f"Episode {c}", [f"Topic {c}", f"Detail {c}"]) for c in "ABCDEF"}
    monkeypatch.setattr(metaquiz, "load_lesson", lambda i: lessons[i])
    monkeypatch.setattr(metaquiz, "tools_for", lambda i, lang: {})
    monkeypatch.setattr(studio, "ensure", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("model offline")))   # generation fails: still works
    out = metaquiz.build_world(list("ABCDEF"), "A", "en", "My course")
    names = [z["name"] for z in out["world"]["zones"]]
    assert out["stats"]["videos"] == 6 and len(names) == 3 and names[0] == "Episode A"
    assert all(z["quiz"]["options"] for z in out["world"]["zones"])           # lesson quiz scenes and fallbacks fill the gates


def test_too_little_content_is_an_error(monkeypatch):
    tiny = {"id": "T", "concept": "x", "languages": {"en": {"title": "x", "scenes": [scene("title", "x", "hi")]}}}
    monkeypatch.setattr(metaquiz, "load_lesson", lambda i: tiny)
    monkeypatch.setattr(metaquiz, "tools_for", lambda i, lang: {"quiz": [], "flashcards": [], "glossary": []})
    with pytest.raises(ValueError):
        metaquiz.build_world(["T"], "T", "en", "x")
