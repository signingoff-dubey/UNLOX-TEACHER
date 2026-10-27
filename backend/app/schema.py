"""The lesson plan the LLM must return. It is pure data: the model picks a template
and fills its slots, and the renderer (our code) decides how it looks and moves."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Template = Literal["title", "bullets", "flow", "cycle", "compare", "diagram", "quiz", "summary"]
Icon = Literal[
    "lightbulb", "sun", "leaf", "water", "atom", "cell", "heart", "brain",
    "earth", "bolt", "gear", "book", "flask", "cloud", "magnet", "rocket",
]

TEMPLATES: tuple[str, ...] = Template.__args__  # type: ignore[attr-defined]
ICONS: tuple[str, ...] = Icon.__args__  # type: ignore[attr-defined]


class ScenePlan(BaseModel):
    template: Template
    heading: str = Field(description="Short on-screen heading, max 6 words")
    narration: str = Field(description="What the teacher says in this scene: 1-3 short sentences")
    items: list[str] = Field(default_factory=list, description="Short labels, max 5 words each")
    icon: Icon = "lightbulb"
    left_title: str = ""
    right_title: str = ""
    left: list[str] = Field(default_factory=list)
    right: list[str] = Field(default_factory=list)
    answer_index: int = 0


class LessonPlan(BaseModel):
    title: str
    scenes: list[ScenePlan]


# Which fields hold text a viewer sees or hears (and so must be translated).
TEXT_FIELDS = ("heading", "narration", "left_title", "right_title")
LIST_FIELDS = ("items", "left", "right")

MIN_ITEMS = {"bullets": 2, "flow": 2, "cycle": 3, "diagram": 2, "quiz": 2, "summary": 2}


def normalize(plan: LessonPlan) -> LessonPlan:
    """Repair the small mistakes local models make so the renderer never sees bad data."""
    scenes: list[ScenePlan] = []
    for s in plan.scenes[:8]:
        s.items = [i.strip() for i in s.items if i and i.strip()][:6]
        s.left = [i.strip() for i in s.left if i and i.strip()][:4]
        s.right = [i.strip() for i in s.right if i and i.strip()][:4]
        s.heading = s.heading.strip() or plan.title
        s.narration = " ".join(s.narration.split())
        if not s.narration:
            continue
        if s.template == "compare" and not (s.left and s.right):
            s.template = "bullets" if len(s.items) >= 2 else "title"
        if len(s.items) < MIN_ITEMS.get(s.template, 0):
            s.template = "title"
        if s.template == "quiz":
            s.answer_index = min(max(s.answer_index, 0), len(s.items) - 1)
        scenes.append(s)
    if not scenes:
        raise ValueError("Lesson plan has no usable scenes")
    if scenes[0].template != "title":
        scenes.insert(0, ScenePlan(template="title", heading=plan.title,
                                   narration=f"Let's learn about {plan.title}.", icon=scenes[0].icon))
    plan.scenes = scenes
    return plan
