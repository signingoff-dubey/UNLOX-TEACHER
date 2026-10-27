"""What the planner and the tutor know about the learner: age (to pitch the words) and the things they got wrong before (to revise).
Both are plain prompt input: no model is trained or called here."""
from __future__ import annotations

from . import rewards


def age_hint() -> str:
    """One sentence telling the model who it is talking to, or "" when no age is set."""
    try:
        age = rewards.profile().get("age", 0)
    except Exception:  # noqa: BLE001  a damaged profile file must never stop a lesson
        return ""
    if age <= 0:
        return ""
    band = ("a young child: very simple words, short sentences, playful examples" if age <= 8 else
            "a child: simple words and everyday examples" if age <= 12 else
            "a teenager: clear words, real-world examples, a little more depth" if age <= 17 else
            "an adult: direct and precise, with the reason behind each step")
    return f"The learner is {age} years old, so write for {band}."
