"""Concept -> LessonPlan, using a local LLM through Ollama with a JSON schema."""
from __future__ import annotations

import json
import logging
import re

import requests
from pydantic import ValidationError

from . import config
from .knowledge import Passage, pages_passages, retrieve
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
- narration is what the teacher says aloud: simple, warm, 2-3 complete sentences (25-40 words) per scene,
  no lists, no markdown, no emojis. Explain WHY, not just WHAT. The whole lesson is 140-200 spoken words.
- Every scene teaches something new. Never repeat the same points in two scenes.
- diagram items are labelled parts or ingredients (nouns), never steps; steps belong in a flow scene.
- heading max 6 words. Each item max 5 words.
- Write the narration so it walks through the items in the same order they appear.
- icon must be one of: {", ".join(ICONS)}.
- Write everything in English (it is translated later)."""


PAGE_REQUEST = re.compile(r"\b(chapter|ch\.?|unit|lesson|section|page|pages|pp?\.)\s*\d", re.I)


def plan_lesson(concept: str, upload: str | None = None, focus: str = "") -> tuple[LessonPlan, list[dict]]:
    """Returns the lesson plan and the sources it was grounded in.

    - concept only: search the knowledge base / library.
    - concept + upload: search that PDF first, then the library.
    - upload with no concept, a `focus`, or a concept like "explain chapter 4": teach that part of
      the PDF from its passages in reading order."""
    if config.LLM_BACKEND == "mock":
        return normalize(sample_plan()), []
    page_mode = bool(upload) and (not concept or bool(focus) or bool(PAGE_REQUEST.search(concept)))
    passages: list[Passage] = []
    if page_mode:
        passages = pages_passages(upload, focus or (concept if PAGE_REQUEST.search(concept) else ""))
    if not passages:
        page_mode = False
        passages = retrieve(concept or focus, upload=upload)
    sources = _page_sources(passages) if page_mode else _sources(passages)
    reference = _condensed_block(passages) if page_mode else _reference_block(passages)
    if page_mode:
        book = passages[0].title
        part = focus or (concept if PAGE_REQUEST.search(concept) else "") or passages[0].section or "this chapter"
        concept = f"the main ideas of {part} from the textbook \"{book}\"" + (f" ({concept})" if concept and
                                                                               not PAGE_REQUEST.search(concept) else "")
    last_error = ""
    best: LessonPlan | None = None
    for attempt in range(3):
        try:
            try:
                raw = _ollama_chat(concept, last_error, reference)
            except requests.RequestException as e:
                raise RuntimeError(
                    f"Cannot reach Ollama at {config.OLLAMA_URL} with model '{config.OLLAMA_MODEL}'. "
                    f"Start it with `ollama serve` and `ollama pull {config.OLLAMA_MODEL}`. ({e})"
                ) from e
            plan = normalize(LessonPlan.model_validate_json(raw))
        except (ValidationError, ValueError, json.JSONDecodeError) as e:
            last_error = f"invalid JSON: {str(e)[:400]}"
            log.warning("Plan attempt %d invalid: %s", attempt + 1, last_error)
            continue
        issue = quality_issue(plan)
        if not issue:
            return plan, sources
        log.info("Plan attempt %d needs work: %s", attempt + 1, issue)
        if best is None or _words(best) < _words(plan):
            best = plan
        last_error = issue
    if best:
        return best, sources          # imperfect but usable beats the generic fallback
    log.error("LLM never produced a valid plan; using fallback plan")
    return normalize(fallback_plan(concept)), sources


def _words(plan: LessonPlan) -> int:
    return sum(len(s.narration.split()) for s in plan.scenes)


def quality_issue(plan: LessonPlan) -> str | None:
    """Cheap checks for the ways small models write weak lessons. Returns feedback for a retry."""
    words = _words(plan)
    if words < 110:
        return (f"the narration is too short ({words} words, about {words // 2.6:.0f} seconds). Write 140-200 "
                "words in total: every scene needs 2-3 full sentences that explain why, not just what")
    if len(plan.scenes) < 4:
        return "use 5-7 scenes: a hook, 2-4 teaching scenes, a quiz and a summary"
    if sum(1 for s in plan.scenes if s.template == "title") > 1:
        return ("only the first scene may be a title; every other scene needs its template's items "
                "(e.g. the summary needs 2-4 recap points in items)")
    lists = [set(i.lower() for i in s.items) for s in plan.scenes if s.template not in ("summary", "quiz") and s.items]
    for a in range(len(lists)):
        for b in range(a + 1, len(lists)):
            if lists[a] and len(lists[a] & lists[b]) >= max(2, len(lists[a]) // 2):
                return "two scenes repeat the same items; each scene must teach something different"
    return None


def _reference_block(passages: list[Passage], budget: int = 4000) -> str:
    """Retrieved passages, most relevant first, within a character budget."""
    parts, used = [], 0
    for i, p in enumerate(passages, 1):
        head = p.title + (f" ({p.section})" if p.section else "")
        piece = f"[{i}] {head}: {p.text}"
        if used + len(piece) > budget:
            break
        parts.append(piece)
        used += len(piece)
    return "\n\n".join(parts)


def _condensed_block(passages: list[Passage], budget: int = 9000) -> str:
    """A whole chapter can be 80 passages (~50k characters). Keep reading order and coverage:
    sample evenly if there are too many, then trim each passage at a sentence boundary."""
    per_min = 280
    if len(passages) * per_min > budget:
        n = budget // per_min
        step = len(passages) / n
        passages = [passages[int(i * step)] for i in range(n)]
    per = max(per_min, budget // max(len(passages), 1))
    parts = []
    for p in passages:
        text = p.text if len(p.text) <= per else p.text[:per].rsplit(". ", 1)[0] + "."
        parts.append(f"[{p.section or p.title}] {text}")
    return "\n\n".join(parts)


def _sources(passages: list[Passage]) -> list[dict]:
    out: dict[str, dict] = {}
    for p in passages:
        out.setdefault(p.title, {"title": p.title, "section": p.section, "url": p.url,
                                 "source": p.source, "score": p.score})
    return list(out.values())


def _page_sources(passages: list[Passage]) -> list[dict]:
    """One source for a page-range lesson: the book, its chapter and the full page span."""
    pages: set[int] = set()
    for p in passages:
        if m := re.search(r"#page=(\d+)", p.url):
            pages.add(int(m.group(1)))
        if m := re.search(r"pp?\.\s*(\d+)(?:\s*[–-]\s*(\d+))?", p.section):   # "pp. 214–219" carries the end page
            pages.update(int(x) for x in m.groups() if x)
    pages = sorted(pages)
    first = passages[0]
    chapter = re.sub(r",?\s*pp?\.\s*[\d–-]+$", "", first.section).strip(", ")
    span = (f"p. {pages[0]}" if len(pages) == 1 or pages[0] == pages[-1] else f"pp. {pages[0]}–{pages[-1]}") \
        if pages else ""
    section = ", ".join(x for x in (chapter, span) if x)
    return [{"title": first.title, "section": section, "url": first.url, "source": first.source, "score": 1.0}]


def _ollama_chat(concept: str, previous_error: str, reference: str = "") -> str:
    user = f"Create a lesson plan that explains: {concept}"
    if reference:
        user += (
            "\n\nReference material from the school knowledge base. Use it for correct facts, numbers and "
            "terms, but explain in your own simple words for a school student. Ignore anything not about "
            f"the concept.\n\n{reference}"
        )
    if previous_error:
        user += f"\n\nYour previous lesson plan had a problem: {previous_error}. Write a better one."
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
            "options": {"temperature": 0.4, "num_ctx": 8192},
        },
        timeout=300,
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"]


def ollama_generate(prompt: str, max_tokens: int = 512) -> str:
    """Plain completion, used by the 'ollama' translation backend."""
    resp = requests.post(
        f"{config.OLLAMA_URL}/api/generate",
        json={"model": config.OLLAMA_MODEL, "prompt": prompt, "stream": False, "keep_alive": "5m",
              "options": {"temperature": 0.1, "num_predict": max_tokens, "repeat_penalty": 1.15}},
        timeout=90,
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
