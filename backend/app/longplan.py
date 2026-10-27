"""Videos longer than LONG_MIN seconds (up to 4 minutes) are planned in parts and joined into one lesson.

One answer from a 7B model cannot hold 4 minutes together: it loses the thread and runs long. So an outline is written first
(a title and one goal per part), then every part of about 40 s is planned as "part k of n of ONE video" (the planner's segment
mode): it knows what was already taught and what comes next, only the first part has a title scene, and only the last has the
quiz and the recap. The scenes of all parts are then joined, and the rest of the pipeline (visual director, writer, translation,
voices) treats the result like any other lesson.
"""
from __future__ import annotations

import logging
from typing import Callable

from pydantic import BaseModel, Field

from . import config, llm
from .planner import plan_lesson
from .schema import LessonPlan

log = logging.getLogger(__name__)

LONG_MIN = 90                      # seconds: anything longer is planned in parts
PART_S = 40                        # about how long one part is
MAX_S = 240


class Chapter(BaseModel):
    title: str = Field(description="What this part is about, max 6 words")
    goal: str = Field(description="One sentence: what the learner understands after this part")


class Storyboard(BaseModel):
    title: str = Field(description="Title of the whole video, max 8 words")
    chapters: list[Chapter]


def parts_for(duration_s: int) -> int:
    return max(2, round(min(duration_s, MAX_S) / PART_S))


def outline(concept: str, n: int, level: str, duration_s: int) -> Storyboard:
    """The outline of the whole video. If the model fails, a generic outline keeps the video going."""
    roles = ["the big picture and why it matters", "the core idea", "a worked example", "a second example or a common mistake",
             "going one step further", "putting it together and a small challenge"]
    fallback = Storyboard(title=concept[:60] or "Lesson", chapters=[
        Chapter(title=roles[min(i, len(roles) - 1)].split(" and ")[0].capitalize(), goal=f"{roles[min(i, len(roles) - 1)].capitalize()} of {concept}.") for i in range(n)])
    if config.LLM_BACKEND == "mock":
        return fallback
    user = (f"Outline ONE continuous video of about {duration_s} seconds that teaches: {concept}.\n"
            f"Audience: {'a complete beginner' if level == 'beginner' else 'an intermediate learner who knows the basics'}.\n"
            f"Write exactly {n} parts. Part 1 is the big picture and why it matters. Each middle part adds one new idea with an example and builds on "
            "the one before. The last part puts it together with a small challenge. No overlaps. Titles are at most 6 words.")
    try:
        sb = llm.ask_json(Storyboard, user, options={"temperature": 0.4, "num_predict": 500}, retries=1, timeout=120, expected_tokens=220)
    except Exception as e:  # noqa: BLE001  the outline is a nicety: never let it stop a lesson
        log.warning("outline failed (%s); using the generic outline", e)
        return fallback
    chapters = [c for c in sb.chapters if c.title.strip() and c.goal.strip()][:n]
    while len(chapters) < n:
        chapters.append(fallback.chapters[len(chapters)])
    return Storyboard(title=sb.title.strip() or fallback.title, chapters=chapters)


def _summary(plan: LessonPlan) -> str:
    return "; ".join(s.heading for s in plan.scenes[:4] if s.heading)


def plan_long(concept: str, level: str, duration_s: int, upload: str | None, focus: str, wps: float,
              on_progress: Callable[[float], None] = lambda f: None) -> tuple[LessonPlan, list[dict]]:
    """Plan a long video part by part. Returns the joined plan and the sources of all parts."""
    n = parts_for(duration_s)
    part_s = round(duration_s / n)
    on_progress(0.02)
    sb = outline(concept or focus or "the topic", n, level, duration_s)
    on_progress(0.08)
    scenes, previous, sources, seen = [], [], [], set()
    for i, ch in enumerate(sb.chapters):
        series = {"segment": True, "title": sb.title, "topic": concept or focus or sb.title, "index": i + 1, "total": n,
                  "previous": list(previous), "this": ch.goal or ch.title,
                  "next": sb.chapters[i + 1].title if i + 1 < n else ""}
        topic = f"{concept}: {ch.title}" if concept else ch.title
        part, src = plan_lesson(topic, level=level, duration_s=part_s, upload=upload, focus=focus, wps=wps, series=series,
                                on_progress=lambda f, i=i: on_progress(0.08 + 0.92 * (i + f) / n))
        scenes += part.scenes
        previous.append(f"{ch.title} ({_summary(part)})")
        for s in src:
            key = (s.get("title"), s.get("section"))
            if key not in seen:
                seen.add(key)
                sources.append(s)
    on_progress(1.0)
    return LessonPlan(title=sb.title, scenes=scenes), sources
