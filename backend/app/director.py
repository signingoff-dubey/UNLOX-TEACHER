"""Visual director agent.

The planner writes the whole lesson in one pass and small models get lazy: they reuse one scene type, or give a
scene too little content so it collapses into a plain title card. The director looks at the finished plan the way
a viewer would and redesigns every weak scene with a short, focused call so each scene shows something different
and actually shows the idea (graphs for maths, code for programming, diagrams and flows for processes).

It only changes the visual fields (template, points, curves, code...). Heading and narration are kept, and the
model still returns data, never code.
"""
from __future__ import annotations

import json
import logging
import re

import requests

from . import config, llm
from . import content
from .schema import LessonPlan, ScenePlan, normalize

log = logging.getLogger(__name__)

MATHS = re.compile(r"\b(graph|circle|parabola|coordinate|geometry|equation|function|trigonometr|sine|cosine|algebra|angle|"
                   r"triangle|quadratic|linear|slope|line|vector|calculus|derivative|integral|plot|curve|ellipse|"
                   r"exponential|logarithm|polynomial|matrix|maths?|mathematics|physics|projectile|wave)\w*", re.I)
CODE = re.compile(r"\b(python|rust|react|javascript|typescript|java|golang|go lang|sql|html|css|c\+\+|c#|kotlin|swift|"
                  r"code|coding|programming|loop|function|algorithm|variable|array|class|api|git|linux|bash|regex)\b", re.I)


def domain_of(text: str) -> str:
    if CODE.search(text) and not re.search(r"\b(graph|coordinate|circle|parabola)\b", text, re.I):
        return "code"
    if MATHS.search(text):
        return "maths"
    return "general"


GUIDE = """Templates (pick the one that SHOWS the idea):
- graph: plot on x/y axes. curves (1-3) with type line|parabola|cubic|sine|cosine|exp|abs|sqrt|reciprocal|circle|ellipse and numbers a,b,c,d:
  line y=a*x+b | parabola y=a*x^2+b*x+c | sine y=a*sin(b*x+c)+d | circle centre (a,b) radius c | ellipse centre (a,b) semi-axes c,d.
  marks: {"kind":"point","x":2,"y":3} plots a dot; {"kind":"link","x":4,"y":1} draws a segment from the previous point to this one;
  circles also take center, radius, diameter, chord, tangent. A graph can have only points (no curves), e.g. to teach plotting coordinates.
  equation: the formula shown beside it. items: one short label per curve, then one per mark, in that order (e.g. "A(2, 3)").
- code: code_lang, code (3-10 lines under 45 chars), highlights (0-based lines in narration order), items (one note per highlight), output (optional).
- network: nodes (3-8 labels of at most 4 words) and edges [{"src": 0, "dst": 2}, ...] (arrows between node positions) for a process that branches or joins,
  e.g. a food web or how data moves between parts. heading = the title. Do not write coordinates.
- flow: items = 3-5 ordered steps.   - cycle: items = 3-5 stages that repeat.
- diagram: heading = the central thing, items = 3-5 labelled parts around it.
- compare: left_title, left (2-4), right_title, right (2-4).
- quiz: heading = the question, items = 3 options, answer_index.
- bullets: items = 2-5 key points (use only when nothing visual fits)."""


def _weak_reasons(scenes: list[ScenePlan], i: int, domain: str) -> str:
    s, prev = scenes[i], scenes[i - 1] if i else None
    if i == 0:
        return ""
    if s.template == "title":
        return "a plain title card in the middle of the lesson"
    if prev is not None and s.template == prev.template and s.template not in ("graph", "code"):
        return f"the same scene type ({s.template}) as the scene before"
    if s.template == "bullets" and domain in ("maths", "code"):
        return "only bullet text for a topic that needs a picture or code"
    if s._wanted and s.template in ("bullets", "title"):
        return f"it asked for '{s._wanted}' but had too little content"
    return ""


def _ask(scene: ScenePlan, plan: LessonPlan, i: int, concept: str, domain: str, avoid: set[str], reason: str) -> ScenePlan | None:
    scenes = plan.scenes
    prev = scenes[i - 1].template if i else "none"
    nxt = scenes[i + 1].template if i + 1 < len(scenes) else "none"
    hint = {"maths": "This is a maths topic: prefer graph scenes with real, correct curves, points or shapes.",
            "code": "This is a programming topic: prefer code scenes with a real, correct, tiny snippet, plus flow/diagram for concepts.",
            "general": "Prefer diagram, flow, cycle or compare over plain bullets."}[domain]
    prompt = (
        f"Design the on-screen visual for ONE scene of a short video lesson.\n"
        f"Lesson topic: {concept}. Lesson title: {plan.title}. Scene {i + 1} of {len(scenes)}.\n"
        f"Heading: {scene.heading}\nNarration (keep exactly as is): {scene.narration}\n"
        f"Previous scene uses: {prev}. Next scene uses: {nxt}. The current design is weak: {reason}.\n{hint}\n\n{GUIDE}\n\n"
        f"Rules: never use 'title'. Do not use: {', '.join(sorted(avoid | {'title'}))}. Everything shown must match the narration, "
        f"in the same order. Each item at most 5 words. Return the scene as JSON with template, heading, narration and the fields the template needs."
    )
    try:
        new = llm.ask_json(ScenePlan, prompt, options={"temperature": 0.5, "num_predict": 450}, retries=0, timeout=120, expected_tokens=250)
    except (requests.RequestException, ValueError, KeyError) as e:
        log.warning("director: scene %d call failed: %s", i + 1, e)
        return None
    new.narration, new.heading = scene.narration, scene.heading or new.heading          # visuals only
    probe = LessonPlan(title=plan.title, scenes=[ScenePlan(template="title", heading=plan.title, narration="x"), new])
    new = normalize(probe).scenes[1]
    return new if new.template not in avoid and new.template != "title" else None


def direct(plan: LessonPlan, concept: str, on_progress=lambda f: None) -> tuple[LessonPlan, list[str]]:
    """Redesign weak or repetitive scenes. Returns the plan and a note per change."""
    notes: list[str] = []
    if config.LLM_BACKEND == "mock":
        return plan, notes
    domain = domain_of(f"{concept} {plan.title}")
    # A title card in the middle with a one-line caption has nothing to show or say: it is removed. (Turning it into a code scene made
    # "Let's learn about ." appear on top of a code block.)
    empty = [i for i, s in enumerate(plan.scenes) if i and s.template == "title" and (content.is_placeholder(s) or len(s.narration.split()) < content.MIN_NARRATION_WORDS)]
    for i in reversed(empty):
        if len(plan.scenes) > 3:
            notes.append(f"scene {i + 1}: removed (an empty title card in the middle of the lesson)")
            del plan.scenes[i]
    todo = [(i, _weak_reasons(plan.scenes, i, domain)) for i in range(len(plan.scenes))]
    todo = [(i, why) for i, why in todo if why]
    for k, (i, why) in enumerate(todo):
        on_progress(k / max(len(todo), 1))
        old = plan.scenes[i]
        prev = plan.scenes[i - 1].template
        avoid = {prev} if prev not in ("graph", "code") else set()
        new = _ask(old, plan, i, concept, domain, avoid, why) or _ask(old, plan, i, concept, domain, avoid | {old.template}, why)
        if new is None:
            log.info("director: scene %d kept (%s)", i + 1, why)
            continue
        plan.scenes[i] = new
        notes.append(f"scene {i + 1}: {old.template} -> {new.template} ({why})")
    on_progress(1.0)
    for n in notes:
        log.info("director: %s", n)
    return plan, notes
