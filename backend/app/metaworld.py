"""Metaverse worlds made by the local model from any topic the learner types, and the metaverse's saved wardrobe.

The model returns data only (four stations to read, each with questions, and a closing text). We clean it, keep only
questions that can be played (four different options, a valid right answer), translate it for other languages and hand the
browser the JSON it draws. No code comes from the model.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Callable

from pydantic import BaseModel, Field

from . import config, llm
from .translate import translate_batch

log = logging.getLogger(__name__)
Progress = Callable[[str, float], None]
COLORS = ["#62e6ff", "#ffb454", "#ff6fa8", "#74ffb8"]
ZONES = 4
PER_GATE = 3
SAVE_FILE = config.MEDIA_DIR / "metaverse_save.json"


class MQuestion(BaseModel):
    question: str = ""
    options: list[str] = Field(default_factory=list, description="exactly 4 short options")
    answer_index: int = Field(0, description="0-based index of the right option")
    hint: str = Field("", description="a short nudge that does not give the answer away")
    why: str = Field("", description="one sentence on why the right option is right")


class MStation(BaseModel):
    name: str = Field("", description="2-3 words")
    title: str = Field("", description="a short heading for what this station teaches")
    body: str = Field("", description="2-4 sentences that teach it")
    terms: list[str] = Field(default_factory=list, description="2-4 key words")
    code: str = Field("", description="optional short code or formula, empty if none")
    questions: list[MQuestion] = Field(default_factory=list)


class MWorld(BaseModel):
    title: str = ""
    stations: list[MStation] = Field(default_factory=list)
    finale: str = Field("", description="2 sentences that sum up what the learner now knows")


def _clip(s: str, n: int) -> str:
    s = " ".join(str(s).split())
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def _questions(st: MStation) -> list[dict]:
    out = []
    for q in st.questions:
        opts = [_clip(o, 90) for o in q.options if o.strip()][:4]
        if len(q.question.strip()) < 8 or len(opts) != 4 or len(set(opts)) != 4 or not 0 <= q.answer_index < 4:
            continue
        right = opts[q.answer_index]
        out.append({"q": _clip(q.question, 160), "options": [right] + [o for i, o in enumerate(opts) if i != q.answer_index], "answer": 0,
                    "hint": _clip(q.hint or "Think about what the station said.", 140), "why": _clip(q.why, 200)})
    return out[:PER_GATE]


def clean(doc: MWorld, topic: str) -> dict:
    """The playable world from the model's answer. Raises ValueError when there is not enough to walk through."""
    zones = []
    for st in doc.stations:
        qs = _questions(st)
        if len(st.body.split()) < 8 or not qs:
            continue
        zones.append({"name": _clip(st.name or st.title, 22), "color": COLORS[len(zones) % 4],
                      "info": {"title": _clip(st.title or st.name, 60), "body": _clip(st.body, 520), "terms": [_clip(t, 28) for t in st.terms if t.strip()][:4] or [_clip(st.name, 28)],
                               **({"code": st.code.strip()[:400]} if st.code.strip() else {})},
                      "quiz": qs[0], "more": qs[1:]})
        if len(zones) == ZONES:
            break
    if len(zones) < 2:
        raise ValueError("The model did not write enough for a world. Try again, or try a more specific topic.")
    title = _clip(doc.title or topic, 40)
    return {"title": title, "match": topic.lower(), "zones": zones,
            "finale": {"title": "Summit reached", "body": _clip(doc.finale or f"You walked through all of {title}.", 300)}}


def _mock(topic: str) -> MWorld:
    st = [MStation(name=f"Part {i + 1}", title=f"{topic}, part {i + 1}", body=f"This is the part {i + 1} of {topic}. It explains one idea in a few simple words for a beginner.",
                   terms=[topic], questions=[MQuestion(question=f"Which is the idea of part {i + 1}?", options=["The idea", "Not this", "Nor this", "Neither"], answer_index=0, hint="Reread it.", why="It is the idea.")]) for i in range(4)]
    return MWorld(title=topic, stations=st, finale=f"You now know the basics of {topic}.")


def _translate(world: dict, lang: str, progress: Progress) -> dict:
    """Every text a learner reads, translated in one batch (the lesson's own engine and cache)."""
    texts: list[str] = [world["title"], world["finale"]["body"]]
    for z in world["zones"]:
        texts += [z["name"], z["info"]["title"], z["info"]["body"], *z["info"]["terms"]]
        for q in [z["quiz"], *z["more"]]:
            texts += [q["q"], *q["options"], q["hint"], q["why"]]
    progress("Translating the world", 0.8)
    out, _ = translate_batch(texts, lang)
    it = iter(out)
    world["title"], world["finale"]["body"] = next(it), next(it)
    for z in world["zones"]:
        z["name"], z["info"]["title"], z["info"]["body"] = next(it), next(it), next(it)
        z["info"]["terms"] = [next(it) for _ in z["info"]["terms"]]
        for q in [z["quiz"], *z["more"]]:
            q["q"] = next(it)
            q["options"] = [next(it) for _ in q["options"]]
            q["hint"], q["why"] = next(it), next(it)
    return world


def build(topic: str, lang: str = "en", progress: Progress = lambda s, p: None) -> dict:
    """A world for any topic, written by the local model: {"world": ..., "stats": ...}."""
    topic = " ".join(topic.split())[:120]
    if len(topic) < 2:
        raise ValueError("Type a topic first")
    progress("Planning the stations", 0.05)
    if config.LLM_BACKEND == "mock":
        doc = _mock(topic)
    else:
        ask = (f"Build a small learning world about: {topic}\n"
               f"Write exactly {ZONES} stations that teach it step by step for a beginner, in order. Each station has a short name, a title, a body of 2-4 simple sentences, "
               f"2-4 key terms, and {PER_GATE} multiple-choice questions (4 options each, answer_index, a hint, a one-sentence why) that test what that station taught. "
               "Put a small code line or formula in `code` only if the topic needs one. Facts must be correct. Finally write `finale`: two sentences that sum up what the learner knows now.")
        doc = llm.ask_json(MWorld, ask, options={"temperature": 0.4, "num_predict": 2400}, timeout=420, expected_tokens=1100,
                           on_progress=lambda f: progress("Writing the stations and questions", 0.08 + 0.7 * f))
    progress("Building the world", 0.75)
    world = clean(doc, topic)
    if lang != "en":
        world = _translate(world, lang, progress)
    progress("Ready", 1.0)
    return {"world": world, "stats": {"stations": len(world["zones"]), "questions": sum(1 + len(z["more"]) for z in world["zones"]), "language": lang}}


# ------------------------------------------------------------------ the wardrobe (points and purchases), kept on this computer
class MetaSave(BaseModel):
    wallet: int = Field(0, ge=0, le=10_000_000)
    life: int = Field(0, ge=0, le=100_000_000)
    owned: list[str] = Field(default_factory=list, max_length=300)
    look: dict[str, str | None] = Field(default_factory=dict)
    rev: int = Field(0, ge=0)                      # increases on every change; the newer copy wins


def load_save() -> dict | None:
    try:
        return json.loads(SAVE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def store_save(data: MetaSave) -> dict:
    clean_ = data.model_dump()
    clean_["owned"] = [re.sub(r"[^\w\-]", "", o)[:40] for o in clean_["owned"]]
    current = load_save()
    if current and current.get("rev", 0) > clean_["rev"]:
        return current                              # an older tab must not overwrite newer purchases
    SAVE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = SAVE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(clean_), encoding="utf-8")
    os.replace(tmp, SAVE_FILE)
    return clean_
