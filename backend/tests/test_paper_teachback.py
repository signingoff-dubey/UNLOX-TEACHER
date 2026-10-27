import json

import numpy as np
import pytest

from app import config, paper, teachback

LESSON = {"id": "L1", "concept": "Photosynthesis", "languages": {"en": {}}, "plan": {"title": "Photosynthesis", "scenes": [
    {"template": "title", "heading": "Photosynthesis", "narration": "Let's learn about photosynthesis.", "items": []},
    {"template": "flow", "heading": "How it works", "narration": "Plants take in sunlight, water and carbon dioxide. They turn them into sugar and oxygen.", "items": ["Light in", "Sugar out"]},
    {"template": "bullets", "heading": "Where", "narration": "It happens inside the green chloroplasts of the leaf. Chlorophyll absorbs the light.", "items": ["Chloroplast"]},
    {"template": "quiz", "heading": "Which gas is used?", "narration": "Pick the gas the plant takes in.", "items": ["CO2", "O2", "N2"]}]}}


@pytest.fixture()
def lesson(monkeypatch, tmp_path):
    for mod in (paper, teachback):
        monkeypatch.setattr(mod, "load_lesson", lambda i: LESSON)
    monkeypatch.setattr(paper, "PAPERS_DIR", tmp_path / "papers")
    monkeypatch.setattr(config, "LLM_BACKEND", "mock")


# ------------------------------------------------------------------ question paper
def test_clean_keeps_usable_questions_in_section_order_and_caps_them():
    doc = paper.PaperDoc(questions=[
        paper.PaperQ(kind="long", question="Describe the whole process in detail.", answer="Light, water, CO2."),
        paper.PaperQ(kind="mcq", question="Which gas do plants take in?", options=["O2", "CO2", "N2", "H2"], answer_index=1),
        paper.PaperQ(kind="mcq", question="Only three options here?", options=["a", "b", "c"], answer_index=0),            # dropped: not 4 options
        paper.PaperQ(kind="mcq", question="Right index is out of range", options=["a", "b", "c", "d"], answer_index=7),     # dropped
        paper.PaperQ(kind="mcq", question="Which pigment absorbs light?", options=["Chlorophyll", "Keratin", "Insulin", "Melanin"], answer_index=0),
        paper.PaperQ(kind="short", question="x", answer="too short a question"),                                              # dropped
        paper.PaperQ(kind="short", question="What is made in photosynthesis?", answer="Sugar and oxygen."),
    ])
    out = paper.clean(doc, {"mcq": 1, "short": 5, "long": 1})
    assert [q.kind for q in out] == ["mcq", "short", "long"]                          # sections in order, MCQ capped at the 1 asked for
    assert out[0].question.startswith("Which gas")


def test_generate_makes_a_saved_paper_with_fixed_marks(lesson):
    p = paper.generate("L1", {"mcq": 2, "short": 1, "long": 1})
    assert p["total_marks"] == 2 * 1 + 1 * 3 + 1 * 8 and p["counts"] == {"mcq": 2, "short": 1, "long": 1}
    assert [q["marks"] for q in p["questions"]] == [1, 1, 3, 8]
    assert json.loads((paper.PAPERS_DIR / f"{p['id']}.json").read_text(encoding="utf-8"))["title"] == p["title"]
    assert paper.load(p["id"])["total_marks"] == 13
    with pytest.raises(ValueError):
        paper.generate("L1", {"mcq": 0, "short": 0, "long": 0})
    with pytest.raises(ValueError):
        paper.load("../etc")


def test_rendered_page_hides_answers_for_students_and_shows_them_for_the_teacher(lesson):
    p = paper.generate("L1", {"mcq": 1, "short": 1, "long": 0})
    p["questions"][0]["options"] = ["<b>x</b>", "right one", "c", "d"]
    p["questions"][0]["answer_index"] = 1
    student, teacher = paper.render_html(p), paper.render_html(p, key=True)
    assert "Section A" in student and "Section B" in student and "&lt;b&gt;x&lt;/b&gt;" in student     # text is escaped
    assert "Answer:" not in student and 'class="ok"' not in student
    assert "Answer:" in teacher and '<li class="ok">right one</li>' in teacher and "Teacher's copy" in teacher
    assert "NotoSansDevanagari" in student and "window.print()" in student and "@media print" in student


# ------------------------------------------------------------------ teach-back
def fake_embed(texts):
    """A tiny stand-in for the embedding model: each text becomes a vector of how many of these topic words it has."""
    topics = [["sunlight", "light"], ["water"], ["sugar", "oxygen"], ["chloroplasts", "chlorophyll", "leaf"], ["football", "cricket"]]
    v = np.array([[sum(w in t.lower() for w in group) for group in topics] + [0.05] for t in texts], dtype=np.float32)
    return v / np.maximum(np.linalg.norm(v, axis=1, keepdims=True), 1e-8)


def test_key_points_are_the_lesson_sentences_without_title_and_quiz():
    pts = teachback.key_points(LESSON)
    assert [p["scene"] for p in pts] == [1, 1, 2, 2]
    assert pts[0]["point"].startswith("Plants take in sunlight")


def test_teachback_scores_covered_points_and_lists_the_missed(lesson):
    said = "Plants use sunlight and water to make sugar and oxygen. I love playing football and cricket after school."
    res = teachback.check("L1", said, embed_fn=fake_embed)
    covered = {c["point"][:12] for c in res["covered"]}
    assert "Plants take " in covered and any("sugar" in c["point"] for c in res["covered"])
    assert any("chloroplasts" in m["point"] for m in res["missed"])                      # the leaf and chlorophyll were never mentioned
    assert 0 < res["score"] < 100 and res["points"] == 4 and res["method"] == "embeddings"
    full = teachback.check("L1", "It happens in the leaf chloroplasts where chlorophyll takes light. Sunlight and water become sugar and oxygen.", embed_fn=fake_embed)
    assert full["score"] > res["score"] and not full["missed"] or full["score"] >= 75


def test_teachback_falls_back_to_shared_words_and_rejects_empty_answers(lesson, monkeypatch):
    monkeypatch.setattr(teachback, "_vectors", lambda texts: None)
    res = teachback.check("L1", "Plants take in sunlight, water and carbon dioxide and turn them into sugar and oxygen.")
    assert res["method"] == "words" and res["covered"] and res["covered"][0]["scene"] == 1
    with pytest.raises(ValueError):
        teachback.check("L1", "ok")
    with pytest.raises(ValueError):
        teachback.check("L1", "")


def test_option_letters_the_model_wrote_are_removed():
    doc = paper.PaperDoc(questions=[paper.PaperQ(kind="mcq", question="Which gas do plants take in?", options=["a) O2", "B. CO2", "(c) N2", "4: H2"], answer_index=1)])
    assert paper.clean(doc, {"mcq": 1})[0].options == ["O2", "CO2", "N2", "H2"]                            # "a)" "B." "(c)" "4:" markers go
