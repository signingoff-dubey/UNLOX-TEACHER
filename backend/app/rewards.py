"""Rewards: score (XP), daily streak, level, daily goal and badges. Built to keep a student coming back and focused.

Design rules (so the rewards push learning, not grinding):
- XP is paid for effort that shows learning: finishing a lesson, getting quiz answers right (more for the first try), knowing a
  flashcard, asking the tutor a question, opening a study tool, and the points won in the metaverse. Each of these is paid once
  per thing (a lesson once per language, a card once) or capped per day, and a day stops paying at DAY_CAP XP.
- A day counts for the streak when it reaches QUALIFY XP, which a single finished lesson already does.
- A streak shield is earned every 7 days of streak (max 2) and quietly covers one missed day, so one bad day is not a reset.
- The level comes from total XP and always grows; the daily goal (30 / 50 / 100 XP) is what the student sets for themselves.
The profile is one JSON file on this laptop (single learner, fully offline). The browser sends its own local date with each event.
"""
from __future__ import annotations

import json
import logging
import math
import threading
import time
from datetime import date, timedelta
from pathlib import Path

from . import config

log = logging.getLogger(__name__)
PROFILE = Path(config.ROOT / "data" / "profile.json")
_lock = threading.RLock()

DAY_CAP = 300
QUALIFY = 20                 # XP that makes a day count for the streak
GOALS = (30, 50, 100)
MAX_SHIELDS = 2

XP = {"lesson_complete": 30, "course_complete": 60, "card_known": 2, "tutor_question": 3, "study_tool_open": 2}
PER_DAY_LIMIT = {"card_known": 40, "tutor_question": 15, "study_tool_open": 10}          # most XP these can pay in one day

BADGES: list[dict] = [
    {"id": "first_lesson", "name": "First lesson", "desc": "Finish your first lesson", "icon": "book", "goal": 1, "stat": "lessons_completed"},
    {"id": "streak_3", "name": "On a roll", "desc": "Learn 3 days in a row", "icon": "bolt", "goal": 3, "stat": "best_streak"},
    {"id": "streak_7", "name": "One week", "desc": "Learn 7 days in a row", "icon": "bolt", "goal": 7, "stat": "best_streak"},
    {"id": "streak_30", "name": "Unstoppable", "desc": "Learn 30 days in a row", "icon": "bolt", "goal": 30, "stat": "best_streak"},
    {"id": "quiz_10", "name": "Quiz ace", "desc": "Answer 10 quiz questions right", "icon": "pie", "goal": 10, "stat": "quiz_correct"},
    {"id": "sharp_5", "name": "Sharp mind", "desc": "5 right first tries in a row", "icon": "sparkle", "goal": 5, "stat": "best_run"},
    {"id": "cards_25", "name": "Card collector", "desc": "Know 25 flashcards", "icon": "folder", "goal": 25, "stat": "cards_known"},
    {"id": "curious_10", "name": "Curious", "desc": "Ask the tutor 10 questions", "icon": "sparkle", "goal": 10, "stat": "questions"},
    {"id": "polyglot", "name": "Polyglot", "desc": "Finish lessons in 2 languages", "icon": "globe", "goal": 2, "stat": "languages"},
    {"id": "explorer", "name": "Explorer", "desc": "Play the metaverse quiz world", "icon": "cube", "goal": 1, "stat": "metaverse_runs"},
    {"id": "scholar", "name": "Scholar", "desc": "Finish a whole course", "icon": "leaf", "goal": 1, "stat": "courses_completed"},
    {"id": "goal_getter", "name": "Goal getter", "desc": "Reach your daily goal 5 times", "icon": "trend", "goal": 5, "stat": "goals_hit"},
    {"id": "level_5", "name": "Level 5", "desc": "Reach level 5", "icon": "rainbow", "goal": 5, "stat": "level"},
]


# ------------------------------------------------------------------ levels
def level_of(xp: int) -> int:
    return 1 + int(math.sqrt(max(xp, 0) / 50))


def level_floor(level: int) -> int:
    return 50 * (level - 1) ** 2


# ------------------------------------------------------------------ storage
def _fresh() -> dict:
    return {"name": "Learner", "xp": 0, "goal": 50, "created": int(time.time()), "days": {}, "badges": {}, "seen": {}, "events": [],
            "streak": {"current": 0, "best": 0, "last_day": "", "shields": 0},
            "counters": {"lessons_completed": 0, "quiz_correct": 0, "cards_known": 0, "questions": 0, "metaverse_runs": 0,
                         "courses_completed": 0, "goals_hit": 0, "run": 0, "best_run": 0, "languages": []}}


def load() -> dict:
    with _lock:
        try:
            return json.loads(PROFILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return _fresh()


def _save(p: dict) -> None:
    PROFILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = PROFILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(p, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(PROFILE)


def _day(p: dict, day: str) -> dict:
    return p["days"].setdefault(day, {"xp": 0, "lessons": 0, "quiz": 0, "cards": 0, "ask": 0, "paid": {}})


def _valid_day(day: str) -> str:
    """The client's local date, if it is a real date within a day of ours; otherwise our own."""
    today = date.today()
    try:
        d = date.fromisoformat(day)
        if abs((d - today).days) <= 1:
            return d.isoformat()
    except (TypeError, ValueError):
        pass
    return today.isoformat()


# ------------------------------------------------------------------ the event
def award(event: dict, day: str | None = None) -> dict:
    """Apply one learning event. Returns {gained, level_up, streak_changed, new_badges, state}."""
    with _lock:
        p = load()
        day = _valid_day(day or event.get("day", ""))
        kind = event.get("type", "")
        today = _day(p, day)
        c = p["counters"]
        level_before = level_of(p["xp"])
        streak_before = p["streak"]["current"]
        gained = 0

        if kind == "lesson_complete":
            key = f"lesson:{event.get('lesson_id', '?')}:{event.get('lang', 'en')}"
            if key not in p["seen"]:
                p["seen"][key] = day
                gained = XP[kind]
                c["lessons_completed"] += 1
                today["lessons"] += 1
                lang = event.get("lang", "en")
                if lang not in c["languages"]:
                    c["languages"].append(lang)
        elif kind == "course_complete":
            key = f"course:{event.get('course_id', '?')}"
            if key not in p["seen"]:
                p["seen"][key] = day
                gained = XP[kind]
                c["courses_completed"] += 1
        elif kind == "quiz_correct":
            first = bool(event.get("first_try", True))
            key = f"quiz:{event.get('lesson_id', '')}:{event.get('card_id', '')}" if event.get("card_id") else ""
            if key and key in p["seen"]:
                gained = 0                                       # the same question again pays nothing: restarting is not learning
            else:
                if key:
                    p["seen"][key] = day
                gained = 10 if first else 4
                c["quiz_correct"] += 1
                today["quiz"] += 1
            c["run"] = c["run"] + 1 if first else 0
            c["best_run"] = max(c["best_run"], c["run"])
        elif kind == "quiz_wrong":
            c["run"] = 0
        elif kind == "card_known":
            key = f"card:{event.get('lesson_id', '?')}:{event.get('card_id', '?')}"
            if key not in p["seen"]:
                p["seen"][key] = day
                gained = _limited(today, "card_known", XP[kind])
                c["cards_known"] += 1
                today["cards"] += 1
        elif kind == "tutor_question":
            gained = _limited(today, "tutor_question", XP[kind])
            c["questions"] += 1
            today["ask"] += 1
        elif kind == "study_tool_open":
            key = f"tool:{event.get('lesson_id', '?')}:{event.get('tool', '?')}:{day}"
            if key not in p["seen"]:
                p["seen"][key] = day
                gained = _limited(today, "study_tool_open", XP[kind])
        elif kind == "metaverse_points":
            gained = min(max(int(event.get("points", 0)) // 5, 0), 40)
            c["metaverse_runs"] += 1
        else:
            raise ValueError(f"Unknown reward event '{kind}'")

        gained = max(0, min(gained, DAY_CAP - today["xp"]))
        was_below_goal = today["xp"] < p["goal"]
        today["xp"] += gained
        p["xp"] += gained
        if was_below_goal and today["xp"] >= p["goal"]:
            c["goals_hit"] += 1
        _update_streak(p, day, today["xp"])
        level = level_of(p["xp"])
        new_badges = _earn_badges(p)
        if gained:
            p["events"] = (p["events"] + [{"t": int(time.time()), "type": kind, "xp": gained, "day": day}])[-60:]
        _save(p)
        return {"gained": gained, "level_up": level > level_before, "level": level,
                "streak_changed": p["streak"]["current"] != streak_before, "new_badges": new_badges, "state": summary(p, day)}


def _limited(today: dict, kind: str, xp: int) -> int:
    paid = today["paid"].get(kind, 0)
    room = max(PER_DAY_LIMIT[kind] - paid, 0)
    pay = min(xp, room)
    today["paid"][kind] = paid + pay
    return pay


def _update_streak(p: dict, day: str, day_xp: int) -> None:
    s = p["streak"]
    if day_xp < QUALIFY or s["last_day"] == day:
        return
    today = date.fromisoformat(day)
    last = date.fromisoformat(s["last_day"]) if s["last_day"] else None
    gap = (today - last).days if last else None
    if gap == 1:
        s["current"] += 1
    elif gap == 2 and s["shields"] > 0:                  # one missed day, covered by a shield
        s["shields"] -= 1
        s["current"] += 1
    elif gap is None or gap > 1:
        s["current"] = 1
    s["last_day"] = day
    if s["current"] % 7 == 0 and s["shields"] < MAX_SHIELDS:
        s["shields"] += 1                                 # a reward for a full week
    s["best"] = max(s["best"], s["current"])


def _stats(p: dict) -> dict[str, int]:
    c = p["counters"]
    return {"lessons_completed": c["lessons_completed"], "best_streak": p["streak"]["best"], "quiz_correct": c["quiz_correct"],
            "best_run": c["best_run"], "cards_known": c["cards_known"], "questions": c["questions"], "languages": len(c["languages"]),
            "metaverse_runs": c["metaverse_runs"], "courses_completed": c["courses_completed"], "goals_hit": c["goals_hit"],
            "level": level_of(p["xp"])}


def _earn_badges(p: dict) -> list[dict]:
    stats, new = _stats(p), []
    for b in BADGES:
        if b["id"] not in p["badges"] and stats[b["stat"]] >= b["goal"]:
            p["badges"][b["id"]] = int(time.time())
            new.append({k: b[k] for k in ("id", "name", "desc", "icon")})
    return new


def set_goal(goal: int) -> dict:
    if goal not in GOALS:
        raise ValueError(f"Daily goal must be one of {GOALS}")
    with _lock:
        p = load()
        p["goal"] = goal
        _save(p)
        return summary(p, date.today().isoformat())


def set_name(name: str) -> dict:
    with _lock:
        p = load()
        p["name"] = " ".join(name.split())[:30] or "Learner"
        _save(p)
        return summary(p, date.today().isoformat())


# ------------------------------------------------------------------ what the dashboard shows
def summary(p: dict | None = None, day: str | None = None) -> dict:
    p = p or load()
    day = _valid_day(day or "")
    today = p["days"].get(day, {"xp": 0, "lessons": 0, "quiz": 0, "cards": 0, "ask": 0})
    level = level_of(p["xp"])
    s = p["streak"]
    # The streak is shown as alive if today or yesterday counted (or a shield would still cover it).
    last = date.fromisoformat(s["last_day"]) if s["last_day"] else None
    gap = (date.fromisoformat(day) - last).days if last else None
    alive = last is not None and (gap <= 1 or (gap == 2 and s["shields"] > 0))
    week = []
    for back in range(6, -1, -1):
        d = (date.fromisoformat(day) - timedelta(days=back)).isoformat()
        xp = p["days"].get(d, {}).get("xp", 0)
        week.append({"day": d, "xp": xp, "done": xp >= QUALIFY, "today": d == day})
    stats = _stats(p)
    return {
        "name": p["name"], "xp": p["xp"], "level": level, "level_xp": level_floor(level), "next_xp": level_floor(level + 1),
        "streak": {"current": s["current"] if alive else 0, "best": s["best"], "shields": s["shields"],
                   "today_done": today["xp"] >= QUALIFY, "at_risk": alive and s["last_day"] != day and today["xp"] < QUALIFY},
        "today": {"xp": today["xp"], "goal": p["goal"], "lessons": today.get("lessons", 0), "quiz": today.get("quiz", 0),
                  "cards": today.get("cards", 0), "ask": today.get("ask", 0), "cap": DAY_CAP, "qualify": QUALIFY},
        "week": week,
        "badges": [{**{k: b[k] for k in ("id", "name", "desc", "icon", "goal")}, "earned": p["badges"].get(b["id"]),
                    "progress": min(stats[b["stat"]], b["goal"])} for b in BADGES],
        "totals": {"lessons": p["counters"]["lessons_completed"], "quiz": p["counters"]["quiz_correct"], "cards": p["counters"]["cards_known"],
                   "questions": p["counters"]["questions"], "best_run": p["counters"]["best_run"]},
        "goals": list(GOALS),
    }
