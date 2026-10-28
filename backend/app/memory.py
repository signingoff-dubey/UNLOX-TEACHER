"""What already exists: the memory the planner (and the tutor) read before they write anything new.

A learner who asks for "AVL trees" after a video on "binary search trees" should get a video that builds on it, not the same hook, definitions and
examples again. Every finished lesson is summarised once (its headings, key points and first lines of code); `context()` picks the few that are about the
same subject as the new request and turns them into a short paragraph for the prompt. Nothing here needs a model or the internet, and nothing here can stop
a lesson: any failure returns an empty string.
"""
from __future__ import annotations

import json
import logging
import re
import threading
from dataclasses import dataclass, field



from .schema import SCHEMA_WORDS

log = logging.getLogger(__name__)

MAX_LESSONS = 3                  # how many earlier videos are described to the planner
MAX_CHARS = 520                  # per earlier video
MIN_OVERLAP = 0.5                # share of the request's key words that an earlier lesson must also be about (its subject and title, not its headings)
_STOP = {"teach", "about", "basics", "basic", "introduction", "explain", "what", "does", "work", "works", "make", "video", "lesson", "learn", "with", "from",
         "that", "this", "your", "have", "into", "using", "language", "concept", "concepts", "simple", "tell", "show"}


@dataclass
class Entry:
    id: str
    concept: str
    title: str
    created: int
    headings: list[str]
    points: list[str]
    code: list[str]
    stems: set[str] = field(default_factory=set)
    mtime: float = 0.0


_cache: dict[str, Entry] = {}
_lock = threading.Lock()


def stems(text: str) -> set[str]:
    return {(w[:-1] if len(w) > 3 and w.endswith("s") else w)[:5] for w in re.findall(r"[a-z0-9+#]+", text.lower()) if len(w) > 2 and w not in _STOP}


def summarise(lesson: dict) -> Entry | None:
    plan = lesson.get("plan") or {}
    scenes = plan.get("scenes") or []
    if len(scenes) < 2:
        return None
    heads = [s.get("heading", "") for s in scenes if s.get("template") not in ("title", "quiz") and s.get("heading")]
    points: list[str] = []
    code: list[str] = []
    for s in scenes:
        if s.get("template") in ("title", "quiz", "summary"):
            continue
        first = (s.get("items") or [None])[0] or (s.get("narration", "").split(".")[0])
        if first:
            points.append(str(first)[:70])
        for ln in s.get("code") or []:
            if ln.strip() and ln.strip() not in ("{", "}") and len(code) < 4:
                code.append(ln.strip()[:60])
                break
    concept = lesson.get("concept") or plan.get("title") or ""
    title = plan.get("title") or concept
    if title.strip().lower() in SCHEMA_WORDS:
        title = concept                                          # an old plan whose title was a word of the schema
    return Entry(lesson["id"], concept, title, int(lesson.get("created") or 0), heads, points, code,
                 stems(f"{concept} {title}"))


def library(exclude: set[str] | None = None) -> list[Entry]:
    """Every finished lesson, summarised (re-read only when its file changed)."""
    from .pipeline import LESSONS_DIR
    out: list[Entry] = []
    try:
        files = list(LESSONS_DIR.glob("*/lesson.json"))
    except OSError:
        return out
    for path in files:
        lid = path.parent.name
        if exclude and lid in exclude:
            continue
        try:
            mtime = path.stat().st_mtime
            with _lock:
                hit = _cache.get(lid)
            if hit is None or hit.mtime != mtime:
                hit = summarise(json.loads(path.read_text(encoding="utf-8")))
                if hit is None:
                    continue
                hit.mtime = mtime
                with _lock:
                    _cache[lid] = hit
            out.append(hit)
        except (OSError, ValueError, KeyError):
            continue
    return out


def related(concept: str, exclude: set[str] | None = None, limit: int = MAX_LESSONS) -> list[Entry]:
    want = stems(concept)
    if not want:
        return []
    scored = []
    same = concept.strip().lower()
    for e in library(exclude):
        if e.concept.strip().lower() == same:
            continue                                         # the same request again is a retry, not something to avoid repeating
        share = len(want & e.stems) / len(want)
        if share >= MIN_OVERLAP:
            scored.append((share, e.created, e))
    scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
    seen, out = set(), []
    for _, _, e in scored:
        key = e.concept.lower()
        if key not in seen:                                  # the same request made twice is one memory
            seen.add(key)
            out.append(e)
    return out[:limit]


def describe(e: Entry) -> str:
    text = f"- \"{e.title}\" covers: " + "; ".join(dict.fromkeys(e.headings))[:260]
    if e.code:
        text += " [code shown: " + " | ".join(e.code[:3]) + "]"
    return text[:MAX_CHARS]


def context(concept: str, exclude: set[str] | None = None) -> str:
    """A paragraph for the planner's prompt, or "" when the learner has nothing on this subject yet."""
    try:
        found = related(concept, exclude)
        if not found:
            return ""
        return ("The learner already has these videos on related subjects. Do NOT repeat their hook, definitions, examples or code; assume they were watched, "
                "refer back to them in at most one short phrase, and go further (a new example, the next idea):\n" + "\n".join(describe(e) for e in found))
    except Exception:  # noqa: BLE001  memory is a help, never a requirement
        log.warning("memory context skipped", exc_info=True)
        return ""


def repeats(plan_headings: list[str], concept: str, exclude: set[str] | None = None) -> list[str]:
    """Headings of the new plan that an earlier video on the same subject already used (reported, for the review notes)."""
    try:
        old = {h.lower().strip() for e in related(concept, exclude) for h in e.headings}
        return [h for h in plan_headings if h.lower().strip() in old and len(h.split()) >= 2]
    except Exception:  # noqa: BLE001
        return []


def forget(lesson_id: str) -> None:
    with _lock:
        _cache.pop(lesson_id, None)


def clear() -> None:
    with _lock:
        _cache.clear()
