import pytest

from app import concepts, config, homework, vision


def test_concepts_are_deduplicated_and_capped(monkeypatch):
    monkeypatch.setattr(config, "LLM_BACKEND", "ollama")
    many = [concepts.Concept(title=f"Idea {i % 10}", focus="x") for i in range(14)] + [concepts.Concept(title="  ", focus="no title")]
    monkeypatch.setattr(concepts.llm, "ask_json", lambda *a, **k: concepts.ConceptList(title="Course", concepts=many))
    title, got = concepts.plan_concepts("big topic")
    assert title == "Course" and len(got) == 3                       # ten distinct, capped at the maximum of three
    assert len({c.title for c in got}) == 3


def test_a_narrow_topic_can_be_one_video(monkeypatch):
    monkeypatch.setattr(config, "LLM_BACKEND", "ollama")
    monkeypatch.setattr(concepts.llm, "ask_json",
                        lambda *a, **k: concepts.ConceptList(title="Variables", concepts=[concepts.Concept(title="Variables", focus="A name for a value.")]))
    assert len(concepts.plan_concepts("what is a variable in Python")[1]) == 1


def test_planning_failure_still_gives_a_course(monkeypatch):
    monkeypatch.setattr(config, "LLM_BACKEND", "ollama")

    def boom(*a, **k):
        raise ValueError("no")

    monkeypatch.setattr(concepts.llm, "ask_json", boom)
    assert len(concepts.plan_concepts("anything")[1]) == 3
    assert len(concepts.plan_concepts("anything", source="a homework")[1]) == 4


def test_homework_markdown_grows_and_finishes(monkeypatch, tmp_path):
    monkeypatch.setattr(homework, "HW_DIR", tmp_path)
    monkeypatch.setattr(config, "LLM_BACKEND", "mock")
    monkeypatch.setattr(homework, "source_text", lambda docs, imgs, limit=0: "1. What is 2+2?\n2. Why is the sky blue?")
    meta = homework.start("Maths sheet", ["a" * 16], [])
    seen = []
    homework.build(meta["id"], lambda s, p: seen.append(p))
    got = homework.load(meta["id"])
    assert got["status"] == "done" and got["total"] == got["done"] == 2
    assert got["markdown"].startswith("# Homework answers: Maths sheet") and "## Question 2" in got["markdown"]
    assert seen[-1] == 1.0


def test_homework_without_readable_text_reports_why(monkeypatch, tmp_path):
    monkeypatch.setattr(homework, "HW_DIR", tmp_path)
    monkeypatch.setattr(homework, "source_text", lambda *a, **k: "")
    meta = homework.start("", [], ["b" * 16])
    with pytest.raises(ValueError):
        homework.build(meta["id"])
    assert homework.load(meta["id"])["status"] == "error"


def test_photos_are_checked_by_their_bytes(monkeypatch, tmp_path):
    monkeypatch.setattr(vision, "IMAGES_DIR", tmp_path)
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 20
    sha = vision.save(png)
    assert vision.save(png) == sha and vision.path_of(sha).suffix == ".png"
    with pytest.raises(vision.ImageError):
        vision.save(b"MZ not an image")
    assert vision.topic_of("Q1. x\nTopic: Maths, fractions.") == "Maths, fractions"
