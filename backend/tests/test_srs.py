import json
from datetime import date, timedelta

import pytest

from app import srs


@pytest.fixture()
def lessons(tmp_path, monkeypatch):
    monkeypatch.setattr(srs, "DB_PATH", tmp_path / "learning.db")
    d = tmp_path / "lessons" / "L1"
    d.mkdir(parents=True)
    (d / "lesson.json").write_text(json.dumps({"concept": "Photosynthesis"}), encoding="utf-8")
    (d / "studio2_flashcards_en_standard_medium.json").write_text(json.dumps({"data": {"cards": [
        {"front": "What do plants make?", "back": "Sugar"}, {"front": "Where?", "back": "Chloroplasts"}]}}), encoding="utf-8")
    (d / "studio2_quiz_en_standard_medium.json").write_text(json.dumps({"data": {"questions": [
        {"question": "Which gas is used?", "options": ["O2", "CO2", "N2", "H2"], "answer_index": 1, "explanation": "Plants take in CO2."}]}}), encoding="utf-8")
    return tmp_path / "lessons"


def test_sm2_intervals_grow_and_a_lapse_resets():
    ease, interval, reps, lapsed = srs.sm2(2.5, 0, 0, 4)
    assert (interval, reps, lapsed) == (1, 1, False)
    ease, interval, reps, _ = srs.sm2(ease, interval, reps, 4)
    assert (interval, reps) == (6, 2)
    ease2, interval2, reps2, _ = srs.sm2(ease, interval, reps, 5)
    assert interval2 == round(6 * ease2) and ease2 > ease                       # easy answers push the ease and the gap up
    ease3, interval3, reps3, lapsed3 = srs.sm2(ease2, interval2, reps2, 1)
    assert (interval3, reps3, lapsed3) == (1, 0, True) and ease3 < ease2
    assert srs.sm2(1.3, 6, 2, 0)[0] == 1.3                                      # the ease never drops below 1.3


def test_cards_come_from_the_study_files_once(lessons):
    assert srs.ingest(lessons, "2026-10-27") == 3
    assert srs.ingest(lessons, "2026-10-27") == 0                               # running again adds nothing
    res = srs.due("2026-10-27", lessons_dir=lessons)
    assert res["due"] == 3 and {c["kind"] for c in res["cards"]} == {"flashcard", "quiz"}
    assert "CO2" in next(c for c in res["cards"] if c["kind"] == "quiz")["back"]


def test_reviewing_moves_the_due_date_and_empties_today(lessons):
    res = srs.due("2026-10-27", lessons_dir=lessons)
    for c in res["cards"]:
        r = srs.review(c["id"], 4, "2026-10-27")
        assert r["interval"] == 1 and r["due"] == "2026-10-28"
    assert srs.due("2026-10-27", lessons_dir=lessons)["due"] == 0
    assert srs.due("2026-10-28", lessons_dir=lessons)["due"] == 3                 # back tomorrow
    forgot = srs.review(res["cards"][0]["id"], 0, "2026-10-28")
    assert forgot["forgot"] and forgot["due"] == "2026-10-29"
    s = srs.stats("2026-10-28")
    assert s["total"] == 3 and s["reviewed_today"] == 1
    with pytest.raises(KeyError):
        srs.review("nope", 3)


def test_weak_spots_are_logged_ranked_and_cleared(lessons):
    srs.log_wrong("L1", "Which gas is used?", "Photosynthesis", "2026-10-27")
    srs.log_wrong("L1", "Which gas is used?", "Photosynthesis", "2026-10-28")
    srs.log_wrong("L2", "What is a verb?", "Grammar", "2026-10-28")
    spots = srs.weak_spots()
    assert [s["topic"] for s in spots] == ["Photosynthesis", "Grammar"] and spots[0]["wrong"] == 2
    focus = srs.weak_focus()
    assert "Photosynthesis" in focus and "Which gas is used?" in focus
    srs.log_right("L1", "Which gas is used?")
    assert "Photosynthesis" in srs.weak_focus()                                   # one right answer is not enough
    srs.log_right("L1", "Which gas is used?")
    assert [s["topic"] for s in srs.weak_spots()] == ["Grammar"]
    assert srs.weak_focus().count("Photosynthesis") == 0
    srs.log_wrong("L1", "Which gas is used?", "Photosynthesis", "2026-10-29")       # a new mistake brings it back
    assert "Photosynthesis" in [s["topic"] for s in srs.weak_spots()]
