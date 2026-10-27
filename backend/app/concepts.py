"""How many videos does a topic need? One per concept the learner has to understand, so the model first lists the concepts
(from the topic, and from the homework or photo text when there is one) and the number of videos is the number of concepts.

The prompt carries the rules and a few worked examples: small models over-count (every sub-point becomes a concept) unless told
that closely related ideas are ONE concept, and that a narrow topic is one or two."""
from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from . import config, llm

log = logging.getLogger(__name__)

MAX_CONCEPTS = 8


class Concept(BaseModel):
    title: str = Field(description="The concept, max 6 words")
    focus: str = Field(description="One sentence: what the learner understands after this video")


class ConceptList(BaseModel):
    title: str = Field(description="Title of the whole course, max 8 words")
    concepts: list[Concept]


RULES = (
    "List the distinct concepts a {level} learner must understand {goal}.\n"
    "Rules:\n"
    "- One concept is one idea that needs its own explanation with an example. Merge ideas that are only variations or steps of the same idea.\n"
    "- Never list a concept twice. Ignore question numbers, page numbers and chapter headings.\n"
    "- A narrow topic has 1 or 2 concepts. A broad topic has 3 to 6. Never more than 8, and do not pad the list.\n"
    "- Order them from the foundation to the advanced.\n"
    "Examples of how many: 'what is a variable in Python' = 1 concept. 'Newton's laws of motion' = 3 (inertia, force and acceleration, "
    "action and reaction). 'Photosynthesis' = 3 (what plants need and make, the light reactions, the Calvin cycle). "
    "A homework with 12 questions that all use the quadratic formula and factorising = 2 concepts (factorising, the quadratic formula).")


def fallback(topic: str, has_source: bool) -> list[Concept]:
    """When the model cannot answer: a sensible spread, so the learner still gets a course."""
    steps = ["The big picture", "The core idea", "A worked example", "Putting it together"]
    n = 4 if has_source else 3
    keep = [steps[0], *steps[1:n - 1], steps[-1]]
    return [Concept(title=t, focus=f"{t} of {topic}.") for t in keep]


def plan_concepts(topic: str, level: str = "beginner", source: str = "", mode: str = "explain") -> tuple[str, list[Concept]]:
    """Returns (course title, concepts). Between 1 and MAX_CONCEPTS."""
    title = topic or "Your lesson"
    if config.LLM_BACKEND == "mock":
        return title, fallback(title, bool(source))
    goal = ("in order to solve the homework below" if mode == "homework" else
            "to master the topic and revise it for a test" if mode == "study" else "to understand the topic")
    user = (RULES.format(level="beginner" if level == "beginner" else "intermediate", goal=goal)
            + f"\n\nTopic: {topic or '(see the material below)'}")
    if source:
        user += "\n\nMaterial from the student (a document or a photo):\n" + source[:7000]
    try:
        got = llm.ask_json(ConceptList, user, options={"temperature": 0.3, "num_predict": 700}, retries=1, timeout=180, expected_tokens=300)
    except Exception as e:  # noqa: BLE001  never stop a lesson because the planning call failed
        log.warning("concept planning failed (%s); using the fallback outline", e)
        return title, fallback(title, bool(source))
    seen, out = set(), []
    for c in got.concepts:
        key = " ".join(c.title.lower().split())
        if c.title.strip() and c.focus.strip() and key not in seen:
            seen.add(key)
            out.append(c)
    out = out[:MAX_CONCEPTS]
    if not out:
        return title, fallback(title, bool(source))
    log.info("concepts for %r: %d -> %s", topic, len(out), [c.title for c in out])
    return got.title.strip() or title, out
