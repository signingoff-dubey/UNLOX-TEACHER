"""Concept -> LessonPlan, using a local LLM through Ollama with a JSON schema."""
from __future__ import annotations

import json
import logging

import requests
from pydantic import ValidationError

from . import config
from .schema import ICONS, LessonPlan, ScenePlan, normalize

log = logging.getLogger(__name__)

SYSTEM_PROMPT = f"""You are an expert school teacher who designs short animated video lessons.
Return ONLY a JSON lesson plan. You never write code; you choose a scene template and fill its fields.

Lesson shape (5-7 scenes, 140-200 spoken words in total, about 60 seconds):
1. "title" scene: hook the student with a question or surprising fact.
2-5. Teach the core idea step by step, using the best-fitting templates.
   Include one everyday example or analogy that an Indian school student knows.
6. "quiz" scene: one multiple-choice question about the key idea.
7. "summary" scene: 2-4 recap points.

Templates and the fields they use:
- title:   heading, narration, icon
- bullets: heading, narration, items (2-5 key points)
- flow:    heading, narration, items (2-5 steps in order, e.g. a process)
- cycle:   heading, narration, items (3-5 stages that repeat, e.g. water cycle)
- compare: heading, narration, left_title, left (2-4), right_title, right (2-4)
- diagram: heading (the central thing), narration, items (2-5 labelled parts around it)
- quiz:    heading (the question), narration (asks it, then reveals the answer), items (3 options), answer_index (0-based)
- summary: heading, narration, items (2-4 recap points)

Rules:
- narration is what the teacher says aloud: simple, warm, 1-3 short sentences, no lists, no markdown, no emojis.
- heading max 6 words. Each item max 5 words.
- Write the narration so it walks through the items in the same order they appear.
- icon must be one of: {", ".join(ICONS)}.
- Write everything in English (it is translated later)."""


def plan_lesson(concept: str) -> LessonPlan:
    if config.LLM_BACKEND == "mock":
        return normalize(sample_plan())
    last_error = ""
    for attempt in range(2):
        try:
            try:
                raw = _ollama_chat(concept, last_error)
            except requests.RequestException as e:
                raise RuntimeError(
                    f"Cannot reach Ollama at {config.OLLAMA_URL} with model '{config.OLLAMA_MODEL}'. "
                    f"Start it with `ollama serve` and `ollama pull {config.OLLAMA_MODEL}`. ({e})"
                ) from e
            return normalize(LessonPlan.model_validate_json(raw))
        except (ValidationError, ValueError, json.JSONDecodeError) as e:
            last_error = str(e)[:500]
            log.warning("Plan attempt %d invalid: %s", attempt + 1, last_error)
    log.error("LLM failed twice; using fallback plan")
    return normalize(fallback_plan(concept))


def _ollama_chat(concept: str, previous_error: str) -> str:
    user = f"Create a lesson plan that explains: {concept}"
    if previous_error:
        user += f"\nYour previous answer was invalid ({previous_error}). Follow the schema exactly."
    resp = requests.post(
        f"{config.OLLAMA_URL}/api/chat",
        json={
            "model": config.OLLAMA_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user},
            ],
            "format": LessonPlan.model_json_schema(),
            "stream": False,
            "keep_alive": config.OLLAMA_KEEP_ALIVE,
            "options": {"temperature": 0.4, "num_ctx": 4096},
        },
        timeout=300,
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"]


def ollama_generate(prompt: str) -> str:
    """Plain completion, used by the 'ollama' translation backend."""
    resp = requests.post(
        f"{config.OLLAMA_URL}/api/generate",
        json={"model": config.OLLAMA_MODEL, "prompt": prompt, "stream": False,
              "keep_alive": "5m", "options": {"temperature": 0.1}},
        timeout=300,
    )
    resp.raise_for_status()
    return resp.json()["response"].strip()


def fallback_plan(concept: str) -> LessonPlan:
    c = concept.strip().rstrip("?.")
    return LessonPlan(title=c, scenes=[
        ScenePlan(template="title", heading=c, icon="lightbulb",
                  narration=f"Today we will understand {c}, one simple step at a time."),
        ScenePlan(template="summary", heading="Remember", items=[c],
                  narration=f"Think about where you see {c} in daily life, and ask your teacher one question about it."),
    ])


def sample_plan() -> LessonPlan:
    """A hand-written lesson for testing the whole pipeline without any model."""
    return LessonPlan.model_validate({
        "title": "Photosynthesis",
        "scenes": [
            {"template": "title", "heading": "How do plants eat?", "icon": "leaf",
             "narration": "Plants never go to a kitchen, yet they make their own food every day. How do they do it?"},
            {"template": "diagram", "heading": "Leaf", "icon": "leaf",
             "items": ["Sunlight", "Water", "Carbon dioxide", "Chlorophyll"],
             "narration": "A leaf needs sunlight, water from the roots, and carbon dioxide from the air. The green chlorophyll captures the light."},
            {"template": "flow", "heading": "The recipe", "icon": "sun",
             "items": ["Light is captured", "Water is split", "Sugar is made", "Oxygen is released"],
             "narration": "First, light is captured. Then water is split. Next, sugar is made, and finally oxygen is released into the air."},
            {"template": "compare", "heading": "Inputs and outputs", "icon": "flask",
             "left_title": "Goes in", "left": ["Sunlight", "Water", "Carbon dioxide"],
             "right_title": "Comes out", "right": ["Glucose", "Oxygen"],
             "narration": "Sunlight, water and carbon dioxide go in. Glucose and oxygen come out. Just like a chapati maker turns flour and water into chapatis!"},
            {"template": "quiz", "heading": "Which gas do plants release?", "icon": "cloud",
             "items": ["Nitrogen", "Oxygen", "Carbon dioxide"], "answer_index": 1,
             "narration": "Quick question. Which gas do plants release? The answer is oxygen, the air we breathe."},
            {"template": "summary", "heading": "Remember", "icon": "lightbulb",
             "items": ["Plants make food", "They need light", "They give us oxygen"],
             "narration": "Plants make their own food, they need light to do it, and they give us the oxygen we breathe."},
        ],
    })
