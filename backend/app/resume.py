"""Jobs that survive a crash or a dead battery.

Two things are kept on disk. (1) `jobs.db` (SQLite): every job with its kind, state and progress, written as it changes, so after a restart
the queue's history is still there and jobs that were running are marked "interrupted" instead of looking alive forever. (2) The lessons
themselves: a lesson is saved after each language, with the English plan inside, so everything that was finished is kept. At start-up this
module finds lessons with languages still to make and finishes them from the saved plan (the last finished language is where it resumes),
and cleans up what cannot be resumed (a lesson whose plan was still being written, a course episode that was being built)."""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from contextlib import closing
from pathlib import Path

from . import config

log = logging.getLogger(__name__)
DB_PATH = config.MEDIA_DIR / "jobs.db"
_lock = threading.RLock()
KEEP_DAYS = 14


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("""CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, kind TEXT NOT NULL, status TEXT NOT NULL, stage TEXT NOT NULL DEFAULT '',
                   progress REAL NOT NULL DEFAULT 0, error TEXT, lesson_id TEXT, created REAL NOT NULL, updated REAL NOT NULL)""")
    return con


def record(job: dict) -> None:
    """Writes the job's current state. Never raises: a full disk must not stop a lesson from being made."""
    try:
        now = time.time()
        with _lock, closing(_connect()) as con:
            con.execute("""INSERT INTO jobs (id, kind, status, stage, progress, error, lesson_id, created, updated) VALUES (?,?,?,?,?,?,?,?,?)
                           ON CONFLICT(id) DO UPDATE SET status=excluded.status, stage=excluded.stage, progress=excluded.progress, error=excluded.error,
                           lesson_id=COALESCE(excluded.lesson_id, jobs.lesson_id), updated=excluded.updated""",
                        (job["id"], job["kind"], job["status"], job.get("stage", ""), float(job.get("progress", 0)), job.get("error"), job.get("lesson_id"), now, now))
            con.commit()
    except Exception as e:  # noqa: BLE001
        log.debug("job record failed: %s", e)


def recent(limit: int = 30) -> list[dict]:
    with _lock, closing(_connect()) as con:
        return [dict(r) for r in con.execute("SELECT * FROM jobs ORDER BY updated DESC LIMIT ?", (limit,)).fetchall()]


def mark_interrupted() -> int:
    """Jobs that were queued or running when the process stopped: they are not running now."""
    with _lock, closing(_connect()) as con:
        cur = con.execute("UPDATE jobs SET status='interrupted', stage='Interrupted by a restart', updated=? WHERE status IN ('queued','running')", (time.time(),))
        con.execute("DELETE FROM jobs WHERE updated < ?", (time.time() - KEEP_DAYS * 86400,))
        con.commit()
        return cur.rowcount


def _read(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def scan_lessons(lessons_dir: Path) -> tuple[list[str], list[str]]:
    """(lessons with languages still to make, lessons whose plan was still being written when the process stopped)."""
    resumable: list[str] = []
    broken: list[str] = []
    for f in lessons_dir.glob("*/lesson.json"):
        lesson = _read(f)
        if not lesson:
            continue
        if lesson.get("building"):
            broken.append(f.parent.name)
        elif lesson.get("pending"):
            resumable.append(f.parent.name)
    return resumable, broken


def tidy_broken(lesson_id: str, lessons_dir: Path) -> None:
    """A lesson that was cut off while its plan was being written keeps the scenes it had: it just stops being "in progress"."""
    path = lessons_dir / lesson_id / "lesson.json"
    lesson = _read(path)
    if not lesson:
        return
    lesson.pop("building", None)
    lesson["pending"] = []
    lesson["interrupted"] = True
    lesson.setdefault("review", []).append("This lesson was cut short by a restart. It has the scenes that were ready.")
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(lesson, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


def tidy_playlists() -> int:
    """Course episodes that were being made have no worker now: mark them failed so the page stops waiting, and keep the finished ones."""
    from . import playlist
    n = 0
    for f in playlist.PLAYLISTS_DIR.glob("*/playlist.json"):
        pl = _read(f)
        if not pl or pl.get("status") not in ("planning", "building"):
            continue
        for ep in pl.get("episodes", []):
            if ep.get("status") in ("pending", "building"):
                ep.update(status="failed", error="Interrupted by a restart")
        ok = sum(1 for e in pl.get("episodes", []) if e.get("status") == "ready")
        pl["status"] = "partial" if ok else "error"
        pl["error"] = pl.get("error") or "Interrupted by a restart"
        playlist.save(pl)
        n += 1
    return n


def on_startup(submit=None, lessons_dir: Path | None = None) -> dict:
    """Run once when the server starts. Returns what it did (for the log and the tests)."""
    from . import jobs, pipeline
    lessons_dir = lessons_dir or pipeline.LESSONS_DIR
    submit = submit or jobs.submit
    marked = mark_interrupted()
    resumable, broken = scan_lessons(lessons_dir)
    for lid in broken:
        tidy_broken(lid, lessons_dir)
    for lid in resumable:
        submit("langs", pipeline.resume_languages, lid)
    courses = tidy_playlists() if lessons_dir == pipeline.LESSONS_DIR else 0
    summary = {"interrupted_jobs": marked, "resumed_lessons": resumable, "cut_short_lessons": broken, "courses_closed": courses}
    if marked or resumable or broken or courses:
        log.info("Resume after restart: %s", summary)
    return summary
