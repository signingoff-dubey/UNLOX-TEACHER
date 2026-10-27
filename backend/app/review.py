"""Reviewer agent: checks what the planner wrote and repairs it before it reaches the screen.

Deterministic checks first (free), then ONE small LLM repair call only for code that does not parse.
The LLM still returns data only (lines of text), never anything that is executed.
"""
from __future__ import annotations

import ast
import json
import logging

import requests

from . import config
from .schema import LessonPlan, MAX_CODE_COLS, ScenePlan

log = logging.getLogger(__name__)


def _python_error(lines: list[str]) -> str | None:
    try:
        ast.parse("\n".join(lines))        # parse only: the snippet is never executed
        return None
    except SyntaxError as e:
        return f"line {e.lineno}: {e.msg}"


def _repair(scene: ScenePlan, error: str) -> list[str] | None:
    prompt = (f"This {scene.code_lang} snippet is meant to be valid. Problem: {error}.\n"
              "Return the corrected snippet as JSON {\"code\": [lines]}, each line under 45 characters, same meaning, "
              "no markdown.\n\n" + "\n".join(scene.code))
    try:
        r = requests.post(f"{config.OLLAMA_URL}/api/chat", json={
            "model": config.OLLAMA_MODEL, "stream": False, "keep_alive": config.OLLAMA_KEEP_ALIVE,
            "messages": [{"role": "user", "content": prompt}],
            "format": {"type": "object", "properties": {"code": {"type": "array", "items": {"type": "string"}}}, "required": ["code"]},
            "options": config.ollama_options({"temperature": 0.1, "num_predict": 300}),
        }, timeout=120)
        r.raise_for_status()
        fixed = [ln.rstrip()[:MAX_CODE_COLS] for ln in json.loads(r.json()["message"]["content"])["code"] if ln.strip()]
        return fixed if fixed and _python_error(fixed) is None else None
    except (requests.RequestException, ValueError, KeyError):
        return None


def review(plan: LessonPlan) -> tuple[LessonPlan, list[str]]:
    """Returns the (possibly repaired) plan and human-readable notes about what was changed."""
    notes: list[str] = []
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
