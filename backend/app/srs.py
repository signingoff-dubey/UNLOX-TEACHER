"""Spaced repetition and weak spots. Pure Python and SQLite: no model is called here.

- Review (SM-2): every flashcard and quiz question the study tools made becomes a card. The learner rates how well they remembered
  (0-5); SM-2 decides when the card is due again (1 day, 6 days, then growing by the card's ease). Cards are collected from the study
  files of every lesson, so nothing needs to be set up.
- Weak spots: a wrong quiz answer is logged against the lesson's topic. Topics missed again and again are handed to the planner
  as the focus of a "Revise" lesson (a prompt input, not new code from the model). Answering right twice clears a topic.
"""
from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import threading
from contextlib import closing
from datetime import date, timedelta
from pathlib import Path

from . import config

log = logging.getLogger(__name__)

DB_PATH = config.MEDIA_DIR / "learning.db"
_lock = threading.RLock()
CLEARED_AFTER = 2                       # right answers in a row that clear a weak topic


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    con.executescript("""
        CREATE TABLE IF NOT EXISTS cards (
            id TEXT PRIMARY KEY, lesson_id TEXT NOT NULL, kind TEXT NOT NULL, topic TEXT NOT NULL, front TEXT NOT NULL, back TEXT NOT NULL,
            ease REAL NOT NULL DEFAULT 2.5, interval INTEGER NOT NULL DEFAULT 0, reps INTEGER NOT NULL DEFAULT 0, lapses INTEGER NOT NULL DEFAULT 0,
            due TEXT NOT NULL, last TEXT NOT NULL DEFAULT '');
        CREATE INDEX IF NOT EXISTS cards_due ON cards(due);
        CREATE TABLE IF NOT EXISTS weak (
            lesson_id TEXT NOT NULL, question TEXT NOT NULL, topic TEXT NOT NULL, wrong INTEGER NOT NULL DEFAULT 0, streak INTEGER NOT NULL DEFAULT 0,
            cleared INTEGER NOT NULL DEFAULT 0, last TEXT NOT NULL DEFAULT '', PRIMARY KEY (lesson_id, question));
    """)
    return con


def _today(day: str | None = None) -> str:
    try:
        return date.fromisoformat(day).isoformat() if day else date.today().isoformat()
    except ValueError:
        return date.today().isoformat()


# ------------------------------------------------------------------ SM-2
def sm2(ease: float, interval: int, reps: int, quality: int) -> tuple[float, int, int, bool]:
    """One review. quality 0-5 (0-2 = forgot, 3 = hard, 4 = good, 5 = easy). Returns (ease, interval days, reps, lapsed)."""
    q = max(0, min(5, int(quality)))
    ease = max(1.3, ease + 0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
    if q < 3:
        return ease, 1, 0, True
    interval = 1 if reps == 0 else 6 if reps == 1 else max(1, round(interval * ease))
    return ease, interval, reps + 1, False


# ------------------------------------------------------------------ collecting cards from the study files
def _card_id(lesson_id: str, kind: str, front: str) -> str:
    return hashlib.sha1(f"{lesson_id}|{kind}|{front}".encode("utf-8")).hexdigest()[:12]


def _lesson_cards(folder: Path) -> list[tuple[str, str, str, str]]:
    """(kind, topic, front, back) from a lesson's cached flashcards and quiz (the English versions)."""
    out: list[tuple[str, str, str, str]] = []
    try:
        topic = json.loads((folder / "lesson.json").read_text(encoding="utf-8")).get("concept", "")
    except (OSError, ValueError):
        topic = ""
    for f in sorted(folder.glob("studio2_flashcards_en_*.json"))[:1]:
        try:
            for c in json.loads(f.read_text(encoding="utf-8"))["data"]["cards"]:
                out.append(("flashcard", topic, c["front"], c["back"]))
        except (OSError, ValueError, KeyError, TypeError):
            pass
    for f in sorted(folder.glob("studio2_quiz_en_*.json"))[:1]:
        try:
            for q in json.loads(f.read_text(encoding="utf-8"))["data"]["questions"]:
                right = q["options"][q["answer_index"]]
                out.append(("quiz", topic, q["question"], f"{right}. {q.get('explanation', '')}".strip()))
        except (OSError, ValueError, KeyError, IndexError, TypeError):
            pass
    return out


def ingest(lessons_dir: Path | None = None, day: str | None = None) -> int:
    """Adds a card for every flashcard and quiz question not seen before (due today). Returns how many were added."""
    root = lessons_dir or (config.MEDIA_DIR / "lessons")
    added = 0
    with _lock, closing(_connect()) as con:
        for folder in root.glob("*/"):
            for kind, topic, front, back in _lesson_cards(folder):
                cur = con.execute("INSERT OR IGNORE INTO cards (id, lesson_id, kind, topic, front, back, due) VALUES (?,?,?,?,?,?,?)",
                                  (_card_id(folder.name, kind, front), folder.name, kind, topic, front, back, _today(day)))
                added += cur.rowcount
        con.commit()
    return added


def due(day: str | None = None, limit: int = 20, lessons_dir: Path | None = None) -> dict:
    """The cards to review on `day`, most overdue first, new cards after the ones already learning."""
    d = _today(day)
    ingest(lessons_dir, d)
    with _lock, closing(_connect()) as con:
        rows = con.execute("SELECT * FROM cards WHERE due <= ? ORDER BY reps = 0, due, lapses DESC LIMIT ?", (d, max(1, min(limit, 100)))).fetchall()
        total = con.execute("SELECT COUNT(*) FROM cards WHERE due <= ?", (d,)).fetchone()[0]
    return {"day": d, "due": total, "cards": [dict(r) for r in rows]}


def review(card_id: str, quality: int, day: str | None = None) -> dict:
    """Rates a card. Returns when it is due next."""
    d = _today(day)
    with _lock, closing(_connect()) as con:
        r = con.execute("SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone()
        if r is None:
            raise KeyError(card_id)
        ease, interval, reps, lapsed = sm2(r["ease"], r["interval"], r["reps"], quality)
        nxt = (date.fromisoformat(d) + timedelta(days=interval)).isoformat()
        con.execute("UPDATE cards SET ease=?, interval=?, reps=?, lapses=lapses+?, due=?, last=? WHERE id=?", (ease, interval, reps, int(lapsed), nxt, d, card_id))
        con.commit()
        lesson_id = r["lesson_id"]
    return {"id": card_id, "lesson_id": lesson_id, "interval": interval, "due": nxt, "ease": round(ease, 2), "forgot": lapsed}


def stats(day: str | None = None) -> dict:
    d = _today(day)
    with _lock, closing(_connect()) as con:
        total = con.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
        due_now = con.execute("SELECT COUNT(*) FROM cards WHERE due <= ?", (d,)).fetchone()[0]
        learned = con.execute("SELECT COUNT(*) FROM cards WHERE interval >= 21").fetchone()[0]
        new = con.execute("SELECT COUNT(*) FROM cards WHERE reps = 0 AND last = ''").fetchone()[0]
        done_today = con.execute("SELECT COUNT(*) FROM cards WHERE last = ?", (d,)).fetchone()[0]
    return {"total": total, "due": due_now, "learned": learned, "new": new, "reviewed_today": done_today}


# ------------------------------------------------------------------ weak spots
def log_wrong(lesson_id: str, question: str, topic: str = "", day: str | None = None) -> None:
    with _lock, closing(_connect()) as con:
        con.execute("""INSERT INTO weak (lesson_id, question, topic, wrong, streak, cleared, last) VALUES (?,?,?,1,0,0,?)
                       ON CONFLICT(lesson_id, question) DO UPDATE SET wrong = wrong + 1, streak = 0, cleared = 0, last = excluded.last""",
                    (lesson_id, question[:300], topic[:120], _today(day)))
        con.commit()


def log_right(lesson_id: str, question: str) -> None:
    """A right answer. Two in a row on a missed question clear it."""
    with _lock, closing(_connect()) as con:
        con.execute("UPDATE weak SET streak = streak + 1, cleared = CASE WHEN streak + 1 >= ? THEN 1 ELSE 0 END WHERE lesson_id = ? AND question = ?",
                    (CLEARED_AFTER, lesson_id, question[:300]))
        con.commit()


def weak_spots(limit: int = 5) -> list[dict]:
    """Topics still being missed, the most missed first."""
    with _lock, closing(_connect()) as con:
        rows = con.execute("SELECT topic, SUM(wrong) AS wrong, COUNT(*) AS questions, MAX(last) AS last FROM weak WHERE cleared = 0 AND topic != '' "
                           "GROUP BY topic ORDER BY wrong DESC, last DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]


def weak_focus(limit: int = 3) -> str:
    """One prompt sentence for the planner: what the learner keeps getting wrong. Empty when there is nothing."""
    spots = weak_spots(limit)
    if not spots:
        return ""
    with _lock, closing(_connect()) as con:
        qs = [r["question"] for r in con.execute("SELECT question FROM weak WHERE cleared = 0 ORDER BY wrong DESC, last DESC LIMIT 5").fetchall()]
    return ("The learner keeps getting these wrong, so revise them: " + "; ".join(s["topic"] for s in spots) +
            ". Questions they missed: " + " | ".join(q[:120] for q in qs) + ". Re-teach the underlying ideas simply and check them again.")
