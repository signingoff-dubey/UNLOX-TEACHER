import pytest

from app import studio

LESSON = {"plan": {"title": "Photosynthesis", "scenes": [
    {"template": "title", "heading": "How plants eat", "narration": "Plants make their own food using light.", "items": [], "left": [], "right": []},
    {"template": "diagram", "heading": "The leaf", "narration": "A leaf takes in light, water and air.", "items": ["Light", "Water", "Air"], "left": [], "right": []},
    {"template": "flow", "heading": "The recipe", "narration": "Light is captured, then sugar is made.", "items": ["Capture", "Split", "Build"], "left": [], "right": []},
    {"template": "summary", "heading": "Remember", "narration": "Plants need light to make sugar and oxygen.", "items": ["Light", "Sugar"], "left": [], "right": []},
]}}


def test_quiz_is_repaired_and_answer_follows_shuffle():
    raw = {"questions": [
        {"question": "What do leaves take in?", "options": ["Light", "Sand", "Metal", "Light"], "answer_index": 0, "explanation": "They need light."},
        {"question": "Bad index", "options": ["a", "b", "c", "d"], "answer_index": 9, "explanation": "x"},
        {"question": "Too few options", "options": ["a", "b"], "answer_index": 0, "explanation": "x"},
    ]}
    out = studio.clean("quiz", raw)["questions"]
    assert len(out) == 1                                   # the broken ones are dropped
    q = out[0]
    assert len(q["options"]) == 3 and q["options"][q["answer_index"]] == "Light"


def test_flashcards_deduplicated_and_limited():
    cards = [{"front": f"Q{i % 3}", "back": f"A{i}"} for i in range(9)]
    out = studio.clean("flashcards", {"cards": cards}, "few")["cards"]
    assert [c["front"] for c in out] == ["Q0", "Q1", "Q2"]


CODE = """mindmap
  root((Graphs))
    Plotting points
      x and y
        Right then up
    The plane
      Four quadrants
      Origin
    Lines
      Slope
"""


def test_mindmap_text_becomes_a_tree_and_clean_mermaid():
    out = studio.clean("mindmap", {"code": CODE})
    assert out["root"] == "Graphs"
    assert [b["label"] for b in out["branches"]] == ["Plotting points", "The plane", "Lines"]
    assert out["branches"][0]["children"][0] == {"label": "x and y", "details": ["Right then up"]}
    assert out["mermaid"].splitlines()[:2] == ["mindmap", "  root((Graphs))"]
    assert studio.parse_mindmap(out["mermaid"])["branches"] == out["branches"]      # round trip


def test_mindmap_cannot_smuggle_mermaid_syntax():
    evil = CODE + "      click Origin href \"javascript:alert(1)\"\n  %%{init: {'securityLevel':'loose'}}%%\n    <img src=x onerror=alert(1)>\n"
    mermaid = studio.clean("mindmap", {"code": evil})["mermaid"]
    assert "%%" not in mermaid and "<" not in mermaid and '"' not in mermaid and "(" not in mermaid.replace("root((Graphs))", "")


def test_mindmap_needs_two_branches_with_children():
    with pytest.raises(ValueError):
        studio.clean("mindmap", {"code": "mindmap\n  Topic\n    Only one\n      child"})


def test_empty_result_is_an_error():
    with pytest.raises(ValueError):
        studio.clean("glossary", {"terms": []})


@pytest.mark.parametrize("kind", studio.KINDS)
def test_mock_output_is_valid_for_every_kind(kind):
    data = studio._mock(kind, LESSON, "standard")
    assert studio.clean(kind, data)                        # valid after cleaning, and not empty


def test_translate_keeps_shape_and_answer_index(monkeypatch):
    monkeypatch.setattr(studio, "translate_batch", lambda texts, lang: ([f"{lang}:{t}" for t in texts], "fake"))
    data = {"questions": [{"question": "Q", "options": ["a", "b", "c"], "answer_index": 2, "explanation": "E"}]}
    out, engine = studio._translate(data, "hi")
    q = out["questions"][0]
    assert q["question"] == "hi:Q" and q["options"] == ["hi:a", "hi:b", "hi:c"] and q["answer_index"] == 2 and engine == "fake"
