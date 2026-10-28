"""Playlists: a topic becomes a short course of 5-8 videos that play one after another.

A curriculum agent outlines the episodes (one clear idea each, building up, last one recaps), then every episode is
built as a normal lesson but told it is part of a series (what came before, what comes next), so episodes link
together instead of repeating. The playlist file is updated after every episode, so the player can start on
episode 1 while the rest are still being made.
"""
from __future__ import annotations

import json
import logging
import subprocess
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
from pydantic import BaseModel, Field

from . import config, content, llm, resources
from .exporter import export_mp4
from .pipeline import LESSONS_DIR, build_lesson, load_lesson

log = logging.getLogger(__name__)

PLAYLISTS_DIR = config.MEDIA_DIR / "playlists"
PLAYLISTS_DIR.mkdir(parents=True, exist_ok=True)
MIN_EPISODES, MAX_EPISODES = 2, 3                   # a course is 2-3 videos: more is less coherent, and people watch the first while the next is made
WORKERS = int(__import__("os").getenv("PLAYLIST_WORKERS", "2"))     # episodes in flight: voices of one overlap planning of the next


class Episode(BaseModel):
    title: str = Field(description="Episode title, max 6 words")
    focus: str = Field(description="One sentence: the single idea this episode teaches")


class Curriculum(BaseModel):
    title: str = Field(description="Course title, max 8 words")
    episodes: list[Episode]


def path_of(playlist_id: str) -> Path:
    if not playlist_id.isalnum():
        raise ValueError("bad playlist id")
    return PLAYLISTS_DIR / playlist_id / "playlist.json"


def load(playlist_id: str) -> dict:
    return json.loads(path_of(playlist_id).read_text(encoding="utf-8"))


def save(pl: dict) -> None:
    p = path_of(pl["id"])
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(pl, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(p)                                                    # readers never see a half-written file


def list_playlists(limit: int = 20) -> list[dict]:
    out = []
    for f in sorted(PLAYLISTS_DIR.glob("*/playlist.json"), key=lambda f: f.stat().st_mtime, reverse=True)[:limit]:
        try:
            pl = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        out.append({"id": pl["id"], "topic": pl["topic"], "title": pl["title"], "created": pl["created"],
                    "status": pl["status"], "episodes": len(pl["episodes"]),
                    "ready": sum(1 for e in pl["episodes"] if e["status"] == "ready")})
    return out


# ------------------------------------------------------------------ curriculum agent
def design_curriculum(topic: str, n: int, level: str, duration_s: int, source: str = "", mode: str = "explain") -> Curriculum:
    """n = 0 means "let the AI decide": one video per concept the learner has to understand (see concepts.py)."""
    if n == 0:
        from .concepts import plan_concepts
        title, cs = plan_concepts(topic, level, source, mode)
        return Curriculum(title=title, episodes=[Episode(title=c.title, focus=c.focus) for c in cs])
    n = min(max(n, MIN_EPISODES), MAX_EPISODES)
    if config.LLM_BACKEND != "mock":
        prompt = (
            f"Design a short video course of exactly {n} episodes (about {duration_s} seconds each) that teaches: {topic}.\n"
            f"Audience: {'a complete beginner' if level == 'beginner' else 'an intermediate learner who knows the basics'}.\n"
            "Rules: each episode teaches ONE clear idea and builds on the one before, and each contains at least one worked example with real values (or real code). "
            "Episode 1 starts teaching the core idea at once: no generic overview or 'why it matters' video. The last episode puts the ideas together with a small challenge. "
            "No overlaps between episodes: no two episodes may use the same example. Titles are at most 6 words and describe the idea (not 'Part 2'). "
            "Each focus is one concrete sentence naming what the learner will be able to do or understand afterwards.")
        if source:
            prompt += ("\n\nMaterial from the student (a document or a photo, read by a computer, so it may contain mistakes). Use it only to learn what the student wants "
                       "to cover; do not copy it:\n" + source[:3000])
        try:
            cur = llm.ask_json(Curriculum, prompt, options={"temperature": 0.4, "num_predict": 700}, timeout=180, expected_tokens=350)
            eps = [e for e in cur.episodes if e.title.strip() and e.focus.strip()]
            if len(eps) >= MIN_EPISODES:
                return Curriculum(title=cur.title.strip() or topic, episodes=eps[:MAX_EPISODES])
            log.warning("curriculum had %d usable episodes; using the fallback outline", len(eps))
        except (requests.RequestException, ValueError, KeyError) as e:
            log.warning("curriculum call failed (%s); using the fallback outline", e)
    steps = ["The core idea with an example", "Going one step further", "Putting it together"]
    keep = steps[:n - 1] + [steps[-1]]
    return Curriculum(title=topic, episodes=[Episode(title=t, focus=f"{t} of {topic}") for t in keep[:n]])


def series_context(pl: dict, i: int) -> dict:
    eps = pl["episodes"]
    taught = "\n".join(f"Video {k + 1} ({e['title']}):\n{e['taught']}" for k, e in enumerate(eps[:i]) if e.get("taught"))
    return {"title": pl["title"], "topic": pl["topic"], "index": i + 1, "total": len(eps), "taught": taught[:1600],
            "previous": [f"{e['title']}: {e['focus']}" for e in eps[:i]],
            "this": eps[i]["focus"], "next": eps[i + 1]["title"] if i + 1 < len(eps) else ""}


# ------------------------------------------------------------------ build
def start(topic: str, languages: list[str], level: str, duration_s: int, n_episodes: int, documents: list[str],
          images: list[str] | None = None, mode: str = "explain", quality: str = "flash") -> dict:
    """Create the playlist record right away so the client has an id to poll before the long job starts."""
    topic = content.clean_topic(topic) if topic.strip() else topic
    pl = {"id": uuid.uuid4().hex[:10], "topic": topic, "title": topic, "created": int(time.time()), "status": "planning",
          "languages": languages, "level": level, "duration_s": duration_s, "documents": documents,
          "images": images or [], "mode": mode, "quality": quality if quality == "pro" else "flash",
          "requested": 0 if n_episodes == 0 else min(max(n_episodes, MIN_EPISODES), MAX_EPISODES), "episodes": [], "error": None}
    save(pl)
    return pl


def _source(pl: dict) -> str:
    """The student's own material as text for the planner: the homework pages and the photos (notes for a long book)."""
    from . import homework
    try:
        if pl["documents"] and not pl["images"]:
            from .ocr import digest
            from .ocr.ingest import read_info, upload_dir
            info = read_info(pl["documents"][0]) or {}
            if info.get("pages", 0) > 40:
                return digest.reference(upload_dir(pl["documents"][0]), budget=6000)
        return homework.source_text(pl["documents"], pl.get("images", []), limit=7000)
    except Exception as e:  # noqa: BLE001
        log.warning("could not read the student's material: %s", e)
        return ""


def build(playlist_id: str, progress=lambda s, p: None) -> dict:
    pl = load(playlist_id)
    t0 = time.perf_counter()
    progress("Designing the course", 0.02)
    try:
        cur = design_curriculum(pl["topic"], pl["requested"], pl["level"], pl["duration_s"], _source(pl), pl.get("mode", "explain"))
    except Exception as e:                       # noqa: BLE001
        pl.update(status="error", error=f"{type(e).__name__}: {e}")
        save(pl)
        raise
    pl["title"] = cur.title
    pl["episodes"] = [{"index": i, "title": e.title, "focus": e.focus, "lesson_id": None, "status": "pending", "error": None}
                      for i, e in enumerate(cur.episodes)]
    pl["status"] = "building"
    save(pl)
    n = len(pl["episodes"])
    frac = [0.0] * n
    state_lock = threading.Lock()
    planned = [threading.Event() for _ in range(n)]      # set once an episode is past planning (only voices left)

    def build_one(i: int) -> None:
        if i:
            planned[i - 1].wait()          # episode 1 gets the model to itself first, so it is playable sooner
            resources.wait_for_headroom(f"episode {i + 1}", min_ram=2.0)       # memory is short: the next episode waits instead of freezing the computer
        ep = pl["episodes"][i]
        ep["status"] = "building"
        with state_lock:
            save(pl)

        def report(stage: str, value: float, **extra) -> None:
            if extra.get("lesson_id") and not ep.get("lesson_id"):          # the first scenes exist: the course page can open this episode now
                ep.update(lesson_id=extra["lesson_id"], preview=True)
                with state_lock:
                    save(pl)
            if extra.get("taught"):                                          # what this video teaches: the next one is written knowing it
                ep["taught"] = extra["taught"]
            frac[i] = value
            if value >= 0.6:
                planned[i].set()
            progress(f"Episode {i + 1} of {n}: {stage}", 0.05 + 0.95 * sum(frac) / n)

        for attempt in (1, 2):
            try:
                lesson = build_lesson(f"{pl['topic']}: {ep['title']}", pl["languages"], pl["level"], pl["duration_s"],
                                      pl["documents"], series=series_context(pl, i), images=pl.get("images", []),
                                      mode=pl.get("mode", "explain"), progressive=True, quality=pl.get("quality", "flash"), progress=report)      # Flash: every episode streams its scenes
                ep.pop("preview", None)
                ep.update(lesson_id=lesson["id"], status="ready", error=None, duration_s=max(t["duration_s"] for t in lesson["languages"].values()))
                break
            except Exception as e:               # noqa: BLE001   one bad episode must not sink the course
                log.error("playlist %s episode %d failed (attempt %d): %s", playlist_id, i + 1, attempt, e)
                if config.is_cuda_error(e):
                    config.mark_cuda_broken(str(e))      # the retry then runs the torch models on the CPU
                if attempt == 2 or not config.is_cuda_error(e):
                    ep.update(status="failed", error=f"{type(e).__name__}: {e}")
                    break
        frac[i] = 1.0
        planned[i].set()
        with state_lock:
            save(pl)

    with ThreadPoolExecutor(max_workers=max(1, WORKERS)) as pool:
        list(pool.map(build_one, range(n)))        # started in order, so episode 1 finishes first

    first_ready = next((e["lesson_id"] for e in pl["episodes"] if e["status"] == "ready" and e.get("lesson_id")), None)
    if first_ready:
        try:
            from . import studio
            studio.prebuild(first_ready)       # the study tools of episode 1 now that nothing else is running; the others are made when opened
        except Exception:  # noqa: BLE001
            log.warning("could not queue the study tools for %s", first_ready, exc_info=True)
    ok = sum(1 for e in pl["episodes"] if e["status"] == "ready")
    pl["status"] = "ready" if ok == n else ("partial" if ok else "error")
    pl["built_s"] = round(time.perf_counter() - t0, 1)
    save(pl)
    progress("Ready", 1.0)
    log.info("playlist %s: %d/%d episodes in %.0fs", playlist_id, ok, n, pl["built_s"])
    return pl


# ------------------------------------------------------------------ one downloadable video
def export_all(playlist_id: str, lang: str, height: int = 720, progress=lambda s, p: None) -> dict:
    """Render every episode and join them into one MP4 (same codec settings, so ffmpeg can join without re-encoding)."""
    pl = load(playlist_id)
    ready = [e for e in pl["episodes"] if e["status"] == "ready"]
    if not ready:
        raise ValueError("No finished episodes to export")
    files: list[Path] = []
    for k, ep in enumerate(ready):
        lesson = load_lesson(ep["lesson_id"])
        if lang not in lesson["languages"]:
            raise ValueError(f"Episode {ep['index'] + 1} has no '{lang}' track")
        res = export_mp4(ep["lesson_id"], lang, height, lambda s, p, k=k: progress(f"Episode {k + 1}/{len(ready)}: {s}", 0.9 * (k + p) / len(ready)))
        files.append(LESSONS_DIR / ep["lesson_id"] / Path(res["url"]).name)
    out_dir = path_of(playlist_id).parent
    listing = out_dir / f"concat_{lang}_{height}.txt"
    listing.write_text("".join(f"file '{f.as_posix()}'\n" for f in files), encoding="utf-8")
    out = out_dir / f"course_{lang}_{height}p.mp4"
    progress("Joining episodes", 0.93)
    proc = subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(out)],
                          capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError("ffmpeg join failed: " + proc.stderr[-300:])
    url = f"/media/playlists/{playlist_id}/{out.name}"
    pl.setdefault("videos", {})[f"{lang}_{height}p"] = url
    save(pl)
    progress("Done", 1.0)
    return {"url": url, "episodes": len(files)}


# ------------------------------------------------------------------ one more video, asked for in the chat (see videochat.py)
MAX_TOTAL = 12
_extra_lock = threading.Lock()          # the playlist file is read, changed and written back under this lock, so two new videos never overwrite each other


def of_lesson(lesson_id: str) -> dict | None:
    """The playlist a lesson is an episode of, if any."""
    for f in PLAYLISTS_DIR.glob("*/playlist.json"):
        try:
            pl = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if any(e.get("lesson_id") == lesson_id for e in pl.get("episodes", [])):
            return pl
    return None


def wrap_lesson(lesson: dict) -> dict:
    """A playlist with this single lesson as episode 1, so a new video can be added next to it."""
    track = lesson["languages"][next(iter(lesson["languages"]))]
    title = track.get("title") or lesson.get("concept") or "Your lesson"
    pl = {"id": uuid.uuid4().hex[:10], "topic": lesson.get("concept") or title, "title": title, "created": int(time.time()), "status": "ready",
          "languages": lesson.get("order") or list(lesson["languages"]), "level": "beginner",
          "duration_s": int(max(30, min(240, round(track["duration_s"] / 30) * 30))),
          "documents": lesson.get("documents") or [], "images": [], "mode": "explain", "requested": 2,
          "episodes": [{"index": 0, "title": title, "focus": lesson.get("concept") or title, "lesson_id": lesson["id"], "status": "ready", "error": None,
                        "duration_s": track["duration_s"]}],
          "error": None, "built_s": 0}
    with _extra_lock:
        save(pl)
    return pl


def _status(pl: dict) -> str:
    eps = pl["episodes"]
    if any(e["status"] in ("building", "pending") for e in eps):
        return "building"
    ok = sum(1 for e in eps if e["status"] == "ready")
    return "ready" if ok == len(eps) else ("partial" if ok else "error")


def append_episode(playlist_id: str, title: str, topic: str, duration_s: int, continues: bool = False) -> tuple[dict, int]:
    """Add a pending episode (right away, so the page has its position before the video exists). Returns (playlist, index)."""
    with _extra_lock:
        pl = load(playlist_id)
        if len(pl["episodes"]) >= MAX_TOTAL:
            raise ValueError(f"This playlist already has {MAX_TOTAL} videos. Start a new one from the home page.")
        if pl["status"] == "planning" or any(not e.get("extra") and e["status"] in ("building", "pending") for e in pl["episodes"]):
            raise ValueError("The course is still being made. Ask again when it has finished.")
        index = len(pl["episodes"])
        pl["episodes"].append({"index": index, "title": title, "focus": topic, "lesson_id": None, "status": "pending", "error": None,
                               "extra": True, "topic": topic, "continues": continues, "target_s": int(max(30, min(240, duration_s)))})
        pl["status"] = "building"
        save(pl)
    return pl, index


def _update_episode(playlist_id: str, index: int, **fields) -> None:
    with _extra_lock:
        pl = load(playlist_id)
        pl["episodes"][index].update(fields)
        pl["status"] = _status(pl)
        save(pl)


def build_extra(playlist_id: str, index: int, progress=lambda s, p, **kw: None) -> dict:
    """Build the episode added by `append_episode`, scene by scene like every other video (the job reports `lesson_id` as soon as scene 1 exists)."""
    pl = load(playlist_id)
    ep = pl["episodes"][index]
    _update_episode(playlist_id, index, status="building")

    def report(stage: str, value: float, **extra) -> None:
        if extra.get("lesson_id"):
            _update_episode(playlist_id, index, lesson_id=extra["lesson_id"], preview=True)
        progress(stage, value, **extra)

    continues = bool(ep.get("continues"))
    for attempt in (1, 2):
        try:
            lesson = build_lesson(ep.get("topic") or ep["title"], pl["languages"], pl["level"], ep.get("target_s") or pl["duration_s"],
                                  pl["documents"] if continues else [], series=series_context(pl, index) if continues else None,
                                  mode=pl.get("mode", "explain"), progressive=True, quality=pl.get("quality", "flash"), progress=report)
            _update_episode(playlist_id, index, lesson_id=lesson["id"], status="ready", error=None, preview=False,
                            duration_s=max(t["duration_s"] for t in lesson["languages"].values()))
            return {"playlist_id": playlist_id, "index": index, "lesson_id": lesson["id"]}
        except Exception as e:                   # noqa: BLE001
            log.error("playlist %s extra video %d failed (attempt %d): %s", playlist_id, index + 1, attempt, e)
            if config.is_cuda_error(e):
                config.mark_cuda_broken(str(e))
            if attempt == 2 or not config.is_cuda_error(e):
                _update_episode(playlist_id, index, status="failed", error=f"{type(e).__name__}: {e}", preview=False)
                raise
    return {"playlist_id": playlist_id, "index": index}
