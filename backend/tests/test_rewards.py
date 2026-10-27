from datetime import date, timedelta

import pytest

from app import rewards as R


@pytest.fixture(autouse=True)
def profile(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "PROFILE", tmp_path / "profile.json")
    yield


def day(offset=0):
    return (date.today() + timedelta(days=offset)).isoformat()


def ev(kind, d=None, **kw):
    return R.award({"type": kind, **kw}, d or day())


def test_finishing_a_lesson_pays_once_per_language_and_makes_the_day_count():
    a = ev("lesson_complete", lesson_id="L1", lang="en")
    assert a["gained"] == 30 and a["state"]["streak"]["current"] == 1 and a["state"]["streak"]["today_done"]
    assert ev("lesson_complete", lesson_id="L1", lang="en")["gained"] == 0          # replaying pays nothing
    assert ev("lesson_complete", lesson_id="L1", lang="hi")["gained"] == 30         # another language is new effort


def test_quiz_pays_more_for_first_tries_and_a_wrong_answer_breaks_the_run():
    assert ev("quiz_correct", first_try=True)["gained"] == 10
    assert ev("quiz_correct", first_try=False)["gained"] == 4
    for _ in range(5):
        ev("quiz_correct", first_try=True)
    s = R.load()
    assert s["counters"]["best_run"] == 5
    ev("quiz_wrong")
    assert R.load()["counters"]["run"] == 0


def test_the_same_quiz_question_pays_only_once_per_lesson():
    assert ev("quiz_correct", lesson_id="L", card_id="q1")["gained"] == 10
    assert ev("quiz_correct", lesson_id="L", card_id="q1")["gained"] == 0
    assert ev("quiz_correct", lesson_id="L", card_id="q2")["gained"] == 10
    assert ev("quiz_correct", lesson_id="M", card_id="q1")["gained"] == 10


def test_flashcards_pay_once_each_and_stop_at_the_daily_limit():
    assert ev("card_known", lesson_id="L", card_id="1")["gained"] == 2
    assert ev("card_known", lesson_id="L", card_id="1")["gained"] == 0
    total = sum(ev("card_known", lesson_id="L", card_id=str(i))["gained"] for i in range(2, 60))
    assert total + 2 == R.PER_DAY_LIMIT["card_known"]


def test_a_day_never_pays_more_than_the_cap():
    for i in range(30):
        ev("metaverse_points", points=1000)
    assert R.summary(None, day())["today"]["xp"] == R.DAY_CAP


def test_streak_grows_on_consecutive_days(monkeypatch):
    monkeypatch.setattr(R, "_valid_day", lambda d: d)                                 # let the test play several days
    for off in (-3, -2, -1, 0):
        ev("lesson_complete", d=day(off), lesson_id=f"L{off}")
    s = R.summary(None, day())["streak"]
    assert s["current"] == 4 and s["best"] == 4
    ev("lesson_complete", d=day(1), lesson_id="tomorrow")
    assert R.summary(None, day(1))["streak"]["current"] == 5


def test_a_day_below_the_qualifying_xp_does_not_count():
    ev("tutor_question")                                                              # 3 XP only
    assert R.summary(None, day())["streak"]["current"] == 0


def test_streak_resets_after_two_missed_days_without_a_shield():
    p = R._fresh()
    p["streak"] = {"current": 6, "best": 6, "last_day": day(-3), "shields": 0}
    R._save(p)
    assert R.summary(None, day())["streak"]["current"] == 0                          # no longer shown as alive
    a = ev("lesson_complete", lesson_id="x")
    assert a["state"]["streak"]["current"] == 1 and a["state"]["streak"]["best"] == 6


def test_a_shield_covers_one_missed_day_and_one_is_earned_every_seven_days():
    p = R._fresh()
    p["streak"] = {"current": 3, "best": 3, "last_day": day(-2), "shields": 1}
    R._save(p)
    assert R.summary(None, day())["streak"]["current"] == 3                           # still alive thanks to the shield
    a = ev("lesson_complete", lesson_id="y")
    assert a["state"]["streak"]["current"] == 4 and a["state"]["streak"]["shields"] == 0
    p = R.load()
    p["streak"].update(current=6, last_day=day(-1), shields=0)
    R._save(p)
    ev("lesson_complete", lesson_id="z")
    assert R.load()["streak"]["current"] == 7 and R.load()["streak"]["shields"] == 1


def test_badges_unlock_once_and_are_reported_when_new():
    a = ev("lesson_complete", lesson_id="L1")
    assert [b["id"] for b in a["new_badges"]] == ["first_lesson"]
    b = ev("lesson_complete", lesson_id="L2")
    assert b["new_badges"] == []
    names = {x["id"]: x for x in b["state"]["badges"]}
    assert names["first_lesson"]["earned"] and not names["quiz_10"]["earned"] and names["quiz_10"]["progress"] == 0


def test_level_comes_from_total_xp():
    assert R.level_of(0) == 1 and R.level_of(49) == 1 and R.level_of(50) == 2 and R.level_of(200) == 3
    ev("course_complete", course_id="c1")
    assert R.load()["xp"] == 60


def test_goal_must_be_one_of_the_choices_and_bad_days_fall_back_to_today():
    assert R.set_goal(100)["today"]["goal"] == 100
    with pytest.raises(ValueError):
        R.set_goal(77)
    a = R.award({"type": "tutor_question"}, "2001-01-01")
    assert a["state"]["today"]["xp"] == 3                                              # counted on today's date, not a made-up one


def test_unknown_events_are_rejected():
    with pytest.raises(ValueError):
        R.award({"type": "free_xp"}, day())


def test_history_lists_every_day_oldest_first_with_what_was_done():
    ev("lesson_complete", lesson_id="L1", lang="en")
    h = R.history(day(), 10)
    assert len(h) == 10 and h[-1]["day"] == day() and h[0]["day"] == day(-9)
    assert h[-1]["lessons"] == 1 and h[-1]["xp"] == 30 and all(d["xp"] == 0 for d in h[:-1])
    assert len(R.history(day(), 9999)) == 400                                       # capped


def test_profile_keeps_name_and_age_and_the_age_hint_follows(tmp_path):
    from app import learner
    assert R.profile()["age"] == 0 and learner.age_hint() == ""
    assert R.set_profile("  Priya  Sharma ", 12) == {"name": "Priya Sharma", "age": 12}
    assert "12 years old" in learner.age_hint() and "child" in learner.age_hint()
    assert R.set_profile(age=40)["age"] == 40 and "adult" in learner.age_hint()
    assert R.set_profile(age=999)["age"] == 120 and R.summary()["age"] == 120
