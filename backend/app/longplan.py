"""Videos longer than LONG_MIN seconds (up to 4 minutes) are planned in parts and joined into one lesson.

One answer from a 7B model cannot hold 4 minutes together: it loses the thread and runs long. So an outline is written first
(a title and one goal per part), then every part of about 30 s is planned as "part k of n of ONE video" (the planner's segment
mode): it knows what was already taught and what comes next, only the first part has a title scene, and only the last has the
quiz and the recap. The scenes of all parts are then joined, and the rest of the pipeline (visual director, writer, translation,
voices) treats the result like any other lesson.
"""
from __future__ import annotations

import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from pydantic import BaseModel, Field

from . import config, llm, memory
from . import content
from .planner import plan_lesson
from .schema import LessonPlan

log = logging.getLogger(__name__)

LONG_MIN = 90                      # seconds: anything longer is planned in parts
PART_S = 40                        # about how long one part is: a 2 minute video is 3 parts, never more (more parts, a less coherent video)
MAX_S = 240


class Chapter(BaseModel):
    title: str = Field(description="What this part is about, max 6 words")
    goal: str = Field(description="One sentence: what the learner understands after this part")


class Storyboard(BaseModel):
    title: str = Field(description="Title of the whole video, max 8 words")
    chapters: list[Chapter]


MAX_PARTS = 3
PRO_BLOCK_S = 60                   # Pro writes the video in blocks of a minute: the first minute whole, then each further minute patched on (it also keeps one call inside the 6144-token context window)


def parts_for(duration_s: int) -> int:
    return max(2, min(MAX_PARTS, round(min(duration_s, MAX_S) / PART_S)))


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


WORKERS = int(os.getenv("LONGPLAN_WORKERS", "1"))     # one after the other: part k is told what parts 1..k-1 really contain (headings, points, code), which writing them at the same time could not


def plan_long(concept: str, level: str, duration_s: int, upload: str | None, focus: str, wps: float,
              on_progress: Callable[[float], None] = lambda f: None, extra: str = "", mode: str = "explain", preview=None) -> tuple[LessonPlan, list[dict]]:
    """Plan a long video part by part, two parts at a time. Returns the joined plan and the sources of all parts.
    The outline already says what each part is about, so a part knows what came before from the outline's titles, not from the
    scenes of the part before it: that is what lets the parts be written at the same time."""
    n = parts_for(duration_s)
    part_s = round(duration_s / n)
    on_progress(0.02)
    sb = outline(concept or focus or "the topic", n, level, duration_s)
    on_progress(0.08)
    frac = [0.0] * n
    lock = threading.Lock()
    best = [0.08]
    done: dict[int, tuple[LessonPlan, list[dict]]] = {}
    handed = [1]                       # parts already given to the player: part 1 is streamed token by token, the others whole and in order

    def hand_over() -> None:           # lock held
        while preview is not None and handed[0] in done:
            preview.add_scenes([s.model_dump() for s in done[handed[0]][0].scenes])
            handed[0] += 1

    def report(i: int, f: float) -> None:
        with lock:
            frac[i] = f
            best[0] = max(best[0], 0.08 + 0.92 * sum(frac) / n)       # parts finish in any order: never let the bar go back
            on_progress(best[0])

    def one(i: int) -> tuple[LessonPlan, list[dict]]:
        ch = sb.chapters[i]
        with lock:
            taught = "\n".join(content.taught_summary(done[j][0]) for j in range(i) if j in done)           # what the earlier parts really contain
        series = {"segment": True, "title": sb.title, "topic": concept or focus or sb.title, "index": i + 1, "total": n,
                  "previous": [f"{c.title}: {c.goal}" for c in sb.chapters[:i]], "this": ch.goal or ch.title,
                  "next": sb.chapters[i + 1].title if i + 1 < n else "", "taught": taught[:1400]}
        topic = f"{concept}: {ch.title}" if concept else ch.title
        got = plan_lesson(topic, level=level, duration_s=part_s, upload=upload, focus=focus, wps=wps, series=series,
                          extra=extra, mode=mode, on_progress=lambda f: report(i, f), on_text=preview.feed if preview is not None and i == 0 else None)
        report(i, 1.0)
        with lock:
            done[i] = got
            hand_over()                # part 2 appears in the player as soon as parts 1 and 2 are both written
        return got

    with ThreadPoolExecutor(max_workers=max(1, min(WORKERS, n))) as pool:
        parts = list(pool.map(one, range(n)))                          # results come back in order
    scenes, sources, seen = [], [], set()
    for part, src in parts:
        scenes += part.scenes
        for s_ in src:
            key = (s_.get("title"), s_.get("section"))
            if key not in seen:
                seen.add(key)
                sources.append(s_)
    plan = LessonPlan(title=sb.title, scenes=scenes)
    for note in content.dedupe_plan(plan):                             # the joined video, judged the way a viewer would
        log.info("long plan: %s", note)
    on_progress(1.0)
    return plan, sources


# ---------------------------------------------------------------- Pro: the whole video is outlined scene by scene first, then written with everything before it in view
class Beat(BaseModel):
    heading: str = Field(description="The scene's heading, max 6 words")
    template: str = Field(description="title|bullets|flow|cycle|compare|diagram|graph|code|network|quiz|summary")
    point: str = Field(description="The one new thing this scene teaches, with its example or value, max 18 words")


class Beats(BaseModel):
    title: str = Field(description="Title of the whole video, max 8 words")
    beats: list[Beat]


def scenes_for(duration_s: int, wps: float = 2.3) -> int:
    """How many scenes a Pro video has: about one every 11 seconds (each carries about 25 words)."""
    return max(5, min(24, round(duration_s / 11)))


def beat_sheet(concept: str, n: int, level: str, duration_s: int, library: str, technical: bool, language: str) -> Beats | None:
    """The scene-by-scene plan of the whole video, or None if the model could not write one (the parts are then planned from a short outline instead)."""
    if config.LLM_BACKEND == "mock":
        return None
    shows = ("Choose scene templates that SHOW the idea: code for programs, network (boxes and arrows) for trees and structures, graph for curves, "
             "flow/cycle/compare/diagram otherwise, never a row of bullets. " if technical else "Vary the templates (flow, cycle, compare, diagram, bullets). ")
    user = (f"Plan ONE video of about {duration_s} seconds that teaches: {concept}.\n"
            f"Audience: {'a complete beginner' if level == 'beginner' else 'an intermediate learner who knows the basics'}.\n"
            f"Write exactly {n} beats, one per scene, in teaching order. Beat 1 is a title scene that hooks the learner with a question or surprising fact; "
            f"the last two beats are a quiz and then a summary; every beat between them teaches ONE new thing and builds on the one before. "
            f"{shows}No two beats may teach the same thing or share a heading. Define a term before using it. "
            + (f"The code language is {language}. " if language else "")
            + "Give each beat a concrete point (a real value, example or rule), not a vague phrase.")
    if library:
        user += "\n" + library
    try:
        sheet = llm.ask_json(Beats, user, options={"temperature": 0.4, "num_predict": 60 * n + 120}, retries=1, timeout=180, expected_tokens=40 * n)
    except Exception as e:  # noqa: BLE001  an outline is an aid: without it the video is planned from a short outline of parts
        log.warning("beat sheet failed (%s)", e)
        return None
    beats = [b for b in sheet.beats if b.heading.strip() and b.point.strip()]
    if len(beats) < max(4, n - 3):
        return None
    seen, kept = set(), []
    for b in beats:
        key = " ".join(b.heading.lower().split())
        if key not in seen:
            seen.add(key)
            kept.append(b)
    return Beats(title=sheet.title.strip(), beats=kept[:n])


def plan_pro(concept: str, level: str, duration_s: int, upload: str | None, focus: str, wps: float,
             on_progress: Callable[[float], None] = lambda f: None, extra: str = "", mode: str = "explain", course: dict | None = None) -> tuple[LessonPlan, list[dict]]:
    """Pro: nothing is shown until the whole video is planned. The video is outlined scene by scene first. Then the first minute is written in one call, and, when
    more than a minute was asked for, each further minute is patched on in a call of its own that sees the whole outline and the full text written so far."""
    from .planner import language_of, plan_lesson, subject_of
    topic = concept or focus or "the topic"
    n = scenes_for(duration_s, wps)
    on_progress(0.02)
    library = memory.context(topic)
    if course:                                                    # an episode of a course: what the other episodes teach is part of what exists
        library = (library + "\n" if library else "") + (f"This video is episode {course.get('index')} of {course.get('total')} of the course \"{course.get('title')}\" "
                                                          f"and teaches only: {course.get('this')}.")
        if course.get("previous"):
            library += " Earlier episodes: " + " | ".join(course["previous"]) + "."
        if course.get("taught"):
            library += "\nAlready taught in them (do not repeat):\n" + course["taught"]
    sheet = beat_sheet(topic, n, level, duration_s, library, any(subject_of(topic)), language_of(topic))
    on_progress(0.10)
    if sheet is None:                                             # no outline: the video is planned in parts from a short outline (Flash's way), still without streaming
        return plan_long(concept, level, duration_s, upload, focus, wps, lambda f: on_progress(0.10 + 0.90 * f), extra, mode, preview=None)
    blocks = max(1, -(-duration_s // PRO_BLOCK_S))                # a minute each; the last one may be shorter
    size = -(-len(sheet.beats) // blocks)
    groups = [sheet.beats[i:i + size] for i in range(0, len(sheet.beats), size)]
    done: list[LessonPlan] = []
    sources: list[dict] = []
    seen: set = set()
    for k, group in enumerate(groups):
        lines = "\n".join(f"{j + 1}. [{b.template}] {b.heading}: {b.point}" for j, b in enumerate(group))
        written = "\n".join(content.taught_summary(p, limit=1800 // max(1, len(done))) for p in done)
        series = {"segment": True, "title": sheet.title or topic, "topic": topic, "index": k + 1, "total": len(groups),
                  "previous": [b.heading for g in groups[:k] for b in g], "this": f"the beats listed below", "beats": lines,
                  "scenes": len(group), "next": groups[k + 1][0].heading if k + 1 < len(groups) else "", "taught": written, "library": library}
        part_s = round(duration_s * len(group) / len(sheet.beats))
        got, src = plan_lesson(topic, level=level, duration_s=part_s, upload=upload, focus=focus, wps=wps, series=series, extra=extra, mode=mode,
                               on_progress=lambda f, k=k: on_progress(0.10 + 0.90 * (k + f) / len(groups)))
        done.append(got)
        for s_ in src:
            key = (s_.get("title"), s_.get("section"))
            if key not in seen:
                seen.add(key)
                sources.append(s_)
    plan = LessonPlan(title=sheet.title or topic, scenes=[s for p in done for s in p.scenes])
    for note in content.dedupe_plan(plan):
        log.info("pro plan: %s", note)
    on_progress(1.0)
    return plan, sources
