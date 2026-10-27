"""Reviewer agent: checks what the planner wrote and repairs it before it reaches the screen.

Deterministic checks first (free), then ONE small LLM repair call only for code that does not parse.
The LLM still returns data only (lines of text), never anything that is executed.
"""
from __future__ import annotations

import ast
import json
import logging

import requests

from pydantic import BaseModel

from . import config, llm
from .schema import LessonPlan, MAX_CODE_COLS, ScenePlan

log = logging.getLogger(__name__)


def _python_error(lines: list[str]) -> str | None:
    try:
        ast.parse("\n".join(lines))        # parse only: the snippet is never executed
        return None
    except SyntaxError as e:
        return f"line {e.lineno}: {e.msg}"


class _Fixed(BaseModel):
    code: list[str]


def _repair(scene: ScenePlan, error: str) -> list[str] | None:
    prompt = (f"This {scene.code_lang} snippet is meant to be valid. Problem: {error}.\n"
              "Return the corrected snippet as JSON {\"code\": [lines]}, each line under 45 characters, same meaning, "
              "no markdown.\n\n" + "\n".join(scene.code))
    try:
        fixed = [ln.rstrip()[:MAX_CODE_COLS] for ln in llm.ask_json(_Fixed, prompt, options={"temperature": 0.1, "num_predict": 300},
                                                                      retries=0, timeout=120, expected_tokens=150).code if ln.strip()]
        return fixed if fixed and _python_error(fixed) is None else None
    except (requests.RequestException, ValueError, KeyError):
        return None


def _words(plan: LessonPlan) -> int:
    return sum(len(s.narration.split()) for s in plan.scenes)


def _lengthen(plan: LessonPlan, target_words: int) -> bool:
    """Writer agent: small models write lessons that are too short, and shorten even more under a JSON constraint.
    So each scene's narration is rewritten with a short free-text call, in order, each seeing the one before it.
    The scenes, points and code stay exactly as planned. Returns True if anything was lengthened."""
    nl = chr(10)
    per_scene = max(14, round(target_words / len(plan.scenes)))      # a floor of 22 made a 4-minute plan of 23 scenes run to 3.5 minutes
    changed, previous = False, ""
    for i, s in enumerate(plan.scenes):
        facts = []
        if s.items:
            facts.append("Points, in this order: " + "; ".join(s.items))
        if s.code:
            facts.append(f"The code shown ({s.code_lang}):{nl}" + nl.join(s.code))
        if s.equation:
            facts.append("Equation on screen: " + s.equation)
        prompt = (
            f"You write the spoken narration for scene {i + 1} of {len(plan.scenes)} in a short video lesson titled \"{plan.title}\".{nl}"
            f"Scene type: {s.template}. On-screen heading: {s.heading}.{nl}" + nl.join(facts) + nl
            + (f"The previous scene said: {previous}{nl}" if previous else "")
            + f"Current draft: {s.narration}{nl}"
            f"Write the new narration: {per_scene} to {per_scene + 8} words, 2-3 warm, simple sentences for a school student. "
            f"Cover every point in the order shown, add one reason or tiny everyday example, and do not repeat the draft word for word. "
            f"Plain text only: no markdown, no list, no quotes.")
        try:
            r = requests.post(f"{config.OLLAMA_URL}/api/chat", json={
                "model": config.OLLAMA_MODEL, "stream": False, "keep_alive": config.OLLAMA_KEEP_ALIVE,
                "messages": [{"role": "user", "content": prompt}],
                "options": config.ollama_options({"temperature": 0.6, "num_predict": 110}),
            }, timeout=120)
            r.raise_for_status()
            text = " ".join(r.json()["message"]["content"].replace("\"", "").split())
        except (requests.RequestException, ValueError, KeyError) as e:
            log.warning("lengthen: scene %d failed: %s", i + 1, e)
            previous = s.narration
            continue
        if len(text.split()) > len(s.narration.split()) and len(text.split()) <= per_scene + 14:
            s.narration, changed = text, True
        previous = s.narration
    return changed


def review(plan: LessonPlan, duration_s: int = 60, wps: float = 2.3) -> tuple[LessonPlan, list[str]]:
    """Returns the (possibly repaired) plan and human-readable notes about what was changed."""
    notes: list[str] = []
    target = round(duration_s * wps)
    before = _words(plan)
    if config.LLM_BACKEND != "mock" and before < 0.85 * target and _lengthen(plan, target):
        notes.append(f"lengthened narration from {before} to {_words(plan)} words (target about {target})")
    for i, s in enumerate(plan.scenes):
        if s.template == "code" and s.code_lang in ("python", "py"):
            err = _python_error(s.code)
            if not err:
                continue
            fixed = None if config.LLM_BACKEND == "mock" else _repair(s, err)
            if fixed:
                s.code = fixed
                s.highlights = [h for h in s.highlights if h < len(fixed)]
                notes.append(f"scene {i + 1}: repaired Python snippet ({err})")
            else:
                notes.append(f"scene {i + 1}: Python snippet does not parse ({err}); left as written")
    for n in notes:
        log.info("review: %s", n)
    return plan, notes
