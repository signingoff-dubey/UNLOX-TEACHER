"""Tutor chat: answers questions about one lesson, using the lesson itself as context.

Context handed to the model: the English lesson plan (every scene's heading, narration, key points, code, equation),
which scene the learner is watching right now, and passages from any uploaded documents (RAG hook).
The reply is written in English, then translated with the same translator the lessons use, so Indian-language
answers are as good as the lesson narration.
"""
from __future__ import annotations

import logging

import requests

from . import config
from .languages import get as get_lang
from .pipeline import load_lesson
from .rag import retrieve_context
from .translate import translate_batch

log = logging.getLogger(__name__)

CHAT_MODEL = config.OLLAMA_MODEL
HISTORY_TURNS = 6


def lesson_plan(lesson: dict) -> dict:
    """English source plan. Older lessons without one fall back to the first available track."""
    if lesson.get("plan"):
        return lesson["plan"]
    track = next(iter(lesson["languages"].values()))
    return {"title": track["title"], "scenes": track["scenes"]}


def scene_text(s: dict, i: int) -> str:
    lines = [f"Scene {i + 1} ({s['template']}): {s['heading']}", f"  Said: {s['narration']}"]
    if s.get("items"):
        lines.append("  Points: " + "; ".join(s["items"]))
    if s.get("left") or s.get("right"):
        lines.append(f"  {s.get('left_title', '')}: {', '.join(s.get('left', []))} | {s.get('right_title', '')}: {', '.join(s.get('right', []))}")
    if s.get("equation"):
        lines.append(f"  Equation: {s['equation']}")
    if s.get("code"):
        lines.append(f"  Code ({s.get('code_lang', '')}):\n    " + "\n    ".join(s["code"]))
        if s.get("output"):
            lines.append("  Output: " + " / ".join(s["output"]))
    return "\n".join(lines)


def lesson_context(lesson: dict, scene_index: int | None) -> str:
    plan = lesson_plan(lesson)
    scenes = plan["scenes"]
    out = [f"LESSON: {plan['title']}", f"Topic requested: {lesson['concept']}", ""]
    out += [scene_text(s, i) for i, s in enumerate(scenes)]
    if scene_index is not None and 0 <= scene_index < len(scenes):
        out += ["", f"The learner is watching scene {scene_index + 1} right now: \"{scenes[scene_index]['heading']}\"."]
    return "\n".join(out)


def scene_at(lesson: dict, lang: str, t: float) -> int | None:
    track = lesson["languages"].get(lang) or next(iter(lesson["languages"].values()))
    for i, s in enumerate(track["scenes"]):
        if s["start_s"] <= t < s["start_s"] + s["duration_s"]:
            return i
    return len(track["scenes"]) - 1 if track["scenes"] else None


SYSTEM = """You are a friendly, patient tutor inside a video-lesson app. The learner is watching the lesson below and asks you questions.
Rules:
- Answer from the lesson first. If the answer is not in the lesson, answer from general knowledge but say so briefly.
- Keep answers short: 2-5 sentences, plain words, one everyday example when it helps. No markdown headings, no emojis.
- If asked to explain again, explain the scene the learner is watching in a different way than the narration.
- If asked for a quiz, ask ONE question and wait for the answer.
- For code, show at most 6 short lines.
- Reply in English. (It is translated for the learner afterwards.)"""


def ask(lesson_id: str, message: str, lang: str, time_s: float, history: list[dict]) -> dict:
    lesson = load_lesson(lesson_id)
    get_lang(lang)
    scene = scene_at(lesson, lang, time_s)
    system = SYSTEM + "\n\n" + lesson_context(lesson, scene)
    docs = retrieve_context(message, lesson.get("documents", []))
    if docs:
        system += f"\n\nPASSAGES FROM THE LEARNER'S DOCUMENTS:\n{docs[:2500]}"
    msgs = [{"role": "system", "content": system}]
    for h in history[-HISTORY_TURNS:]:
        if h.get("role") in ("user", "assistant") and h.get("content"):
            msgs.append({"role": h["role"], "content": h["content"][:1500]})
    msgs.append({"role": "user", "content": message[:1000]})

    if config.LLM_BACKEND == "mock":
        reply = f"(mock tutor) You asked: {message[:80]}. This lesson is about {lesson_plan(lesson)['title']}."
    else:
        try:
            resp = requests.post(f"{config.OLLAMA_URL}/api/chat", json={
                "model": CHAT_MODEL, "messages": msgs, "stream": False, "keep_alive": config.OLLAMA_KEEP_ALIVE,
                "options": config.ollama_options({"temperature": 0.5, "num_ctx": 4096, "num_predict": 350}),
            }, timeout=180)
            resp.raise_for_status()
            reply = resp.json()["message"]["content"].strip()
        except requests.RequestException as e:
            raise RuntimeError(f"Cannot reach Ollama for chat: {e}") from e

    translator = "none"
    if lang != "en":
        (reply,), translator = translate_batch([reply], lang)
    return {"reply": reply, "scene": scene, "lang": lang, "translator": translator}
