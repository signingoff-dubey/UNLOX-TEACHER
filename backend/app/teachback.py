"""Teach-back: the learner explains the lesson in their own words (typed, or spoken and turned into text by Whisper) and gets a score and
the points they missed. No model judges anything: the lesson's key points and the learner's sentences are turned into embedding vectors
and compared by cosine similarity; a key point is "covered" when some sentence of the explanation is close enough to it.

The key points are the English plan's sentences, so explain in English (the embedding model is English). When the embedding model is not
running, a plain shared-words comparison is used instead, so the check still works."""
from __future__ import annotations

import logging
import re

import numpy as np

from .fidelity import overlap
from .pipeline import load_lesson

log = logging.getLogger(__name__)
COVERED = 0.62            # cosine similarity (nomic-embed-text, no prefix) at which a sentence says the same thing as a key point.
                          # Measured on a real lesson: off-topic sentences reach 0.56 at most, a paraphrase of a point 0.75, so 0.62 sits between them.
COVERED_WORDS = 0.45      # shared content words, when only the word comparison is available
MIN_WORDS = 4


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?।])\s+|\n+", text.strip())
    return [p.strip() for p in parts if len(p.split()) >= MIN_WORDS]


def key_points(lesson: dict, limit: int = 20) -> list[dict]:
    """What the lesson teaches, one sentence at a time: [{point, scene, heading}]. Title and quiz scenes add nothing to explain."""
    plan = lesson.get("plan") or {}
    out: list[dict] = []
    seen: set[str] = set()
    for i, s in enumerate(plan.get("scenes", [])):
        if s.get("template") in ("title", "quiz"):
            continue
        for sentence in _sentences(s.get("narration", "")):
            k = sentence.lower()
            if k not in seen:
                seen.add(k)
                out.append({"point": sentence, "scene": i, "heading": s.get("heading", "")})
    return out[:limit]


def _vectors(texts: list[str]) -> np.ndarray | None:
    try:
        from .knowledge import embed
        return embed(texts, "")                      # no task prefix: with one, unrelated texts score higher and the gap to paraphrases shrinks
    except Exception as e:  # noqa: BLE001  the embedding model is not running: the caller falls back to words
        log.info("embeddings unavailable for teach-back (%s); comparing words instead", e)
        return None


def check(lesson_id: str, explanation: str, embed_fn=None) -> dict:
    """Score 0-100, the key points covered (with the sentence that covered them) and the ones missed."""
    lesson = load_lesson(lesson_id)
    points = key_points(lesson)
    mine = _sentences(explanation)
    if not points:
        raise ValueError("This lesson has nothing to explain back yet.")
    if not mine:
        raise ValueError("Write a few sentences first: at least one with four words or more.")
    vecs = (embed_fn or _vectors)([p["point"] for p in points] + mine)
    covered, missed = [], []
    for k, p in enumerate(points):
        if vecs is not None:
            sims = vecs[len(points):] @ vecs[k]
            j = int(np.argmax(sims))
            sim, hit = float(sims[j]), sims[j] >= COVERED
        else:
            scores = [overlap(p["point"], s) for s in mine]
            j = int(np.argmax(scores))
            sim, hit = float(scores[j]), scores[j] >= COVERED_WORDS
        (covered if hit else missed).append({**p, "similarity": round(sim, 2), **({"said": mine[j]} if hit else {})})
    score = round(100 * len(covered) / len(points))
    return {"score": score, "covered": covered, "missed": missed, "sentences": len(mine), "points": len(points),
            "method": "embeddings" if vecs is not None else "words",
            "verdict": "You explained it well." if score >= 80 else "Good start. Add the missed points." if score >= 40 else "Watch the lesson again, then try once more."}
