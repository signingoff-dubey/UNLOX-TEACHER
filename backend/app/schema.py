"""The lesson plan the LLM must return. It is pure data: the model picks a template
and fills its slots, and the renderer (our code) decides how it looks and moves."""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, PrivateAttr, field_validator

Template = Literal["title", "bullets", "flow", "cycle", "compare", "diagram", "quiz", "summary", "graph", "code"]
CurveType = Literal["line", "parabola", "cubic", "sine", "cosine", "exp", "abs", "sqrt", "reciprocal", "circle", "ellipse"]
MarkKind = Literal["center", "radius", "diameter", "chord", "tangent", "point", "link"]
Icon = Literal[
    "lightbulb", "sun", "leaf", "water", "atom", "cell", "heart", "brain",
    "earth", "bolt", "gear", "book", "flask", "cloud", "magnet", "rocket",
]

TEMPLATES: tuple[str, ...] = Template.__args__  # type: ignore[attr-defined]
ICONS: tuple[str, ...] = Icon.__args__  # type: ignore[attr-defined]


class Curve(BaseModel):
    """A plottable curve picked from a fixed list; the renderer draws it, nothing is evaluated.
    line y=a*x+b | parabola y=a*x^2+b*x+c | cubic y=a*x^3+b*x^2+c*x+d | sine/cosine y=a*sin(b*x+c)+d
    exp y=a*e^(b*x)+c | abs y=a*|x-b|+c | sqrt y=a*sqrt(x-b)+c | reciprocal y=a/x
    circle centre (a,b) radius c | ellipse centre (a,b) semi-axes c (x) and d (y)"""
    type: CurveType
    a: float = 1
    b: float = 0
    c: float = 0
    d: float = 0


class Mark(BaseModel):
    """A feature to highlight. center/radius/diameter/chord/tangent act on the first circle;
    point puts a dot at (x, y)."""
    kind: MarkKind
    x: float = 0
    y: float = 0


class ScenePlan(BaseModel):
    template: Template = "bullets"
    heading: str = Field("", description="Short on-screen heading, max 6 words")
    narration: str = Field("", description="What the teacher says in this scene: 1-3 short sentences")
    items: list[str] = Field(default_factory=list, description="Short labels, max 5 words each")
    icon: Icon = "lightbulb"
    left_title: str = ""
    right_title: str = ""
    left: list[str] = Field(default_factory=list)
    right: list[str] = Field(default_factory=list)
    answer_index: int = 0
    _wanted: str = PrivateAttr("")      # template the model asked for before normalize() changed it (director input)
    # graph scenes: curves then marks are revealed in order; items[k] labels the k-th revealed thing
    curves: list[Curve] = Field(default_factory=list, description="graph scenes: 1-3 curves")
    marks: list[Mark] = Field(default_factory=list, description="graph scenes: up to 4 highlights")
    x_range: list[float] = Field(default_factory=list, description="graph scenes: [xmin, xmax], optional")
    y_range: list[float] = Field(default_factory=list, description="graph scenes: [ymin, ymax], optional")
    equation: str = Field("", description="graph scenes: formula shown on screen, e.g. x^2 + y^2 = r^2")
    # code scenes: shown as text only, never executed. highlights[k] is the line explained by items[k]
    code_lang: str = Field("", description="code scenes: python, rust, javascript, jsx, java, c, go, sql, html...")
    code: list[str] = Field(default_factory=list, description="code scenes: 3-10 short lines of code")
    highlights: list[int] = Field(default_factory=list, description="code scenes: 0-based line numbers, in narration order")
    output: list[str] = Field(default_factory=list, description="code scenes: what the program prints (optional)")

    # Small models slip on types (an icon that is not in the list, code as one string, a range that is not a pair).
    # The plan is asked for as plain JSON text, without Ollama's slow constrained decoding, so these are repaired here.
    @field_validator("template", mode="before")
    @classmethod
    def _template(cls, v):
        v = str(v or "").strip().lower()
        return v if v in TEMPLATES else "bullets"

    @field_validator("icon", mode="before")
    @classmethod
    def _icon(cls, v):
        return v if v in ICONS else "lightbulb"

    @field_validator("heading", "narration", "equation", "code_lang", "left_title", "right_title", mode="before")
    @classmethod
    def _text(cls, v):
        return "" if v is None else v if isinstance(v, str) else str(v)

    @field_validator("items", "left", "right", mode="before")
    @classmethod
    def _labels(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            v = [x.strip(" -*") for x in v.splitlines()] if len(v.splitlines()) > 1 else [v]
        return [str(x) for x in v if x is not None and str(x).strip()] if isinstance(v, (list, tuple)) else []

    @field_validator("code", "output", mode="before")
    @classmethod
    def _lines(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            return [ln for ln in v.splitlines() if ln.strip()]
        return [str(x) for x in v] if isinstance(v, (list, tuple)) else []

    @field_validator("highlights", mode="before")
    @classmethod
    def _highlights(cls, v):
        if isinstance(v, str):
            v = re.findall(r"\d+", v)
        if not isinstance(v, (list, tuple)):
            return []
        out = []
        for x in v:
            try:
                out.append(int(x))
            except (TypeError, ValueError):
                continue
        return out

    @field_validator("x_range", "y_range", mode="before")
    @classmethod
    def _range(cls, v):
        ok = isinstance(v, (list, tuple)) and len(v) == 2 and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in v)
        return list(v) if ok else []

    @field_validator("answer_index", mode="before")
    @classmethod
    def _answer(cls, v):
        try:
            return int(v)
        except (TypeError, ValueError):
            return 0

    @field_validator("curves", mode="before")
    @classmethod
    def _curves(cls, v):
        kinds = CurveType.__args__  # type: ignore[attr-defined]
        return [c for c in v if isinstance(c, dict) and c.get("type") in kinds] if isinstance(v, list) else []

    @field_validator("marks", mode="before")
    @classmethod
    def _marks(cls, v):
        kinds = MarkKind.__args__  # type: ignore[attr-defined]
        return [m for m in v if isinstance(m, dict) and m.get("kind") in kinds] if isinstance(v, list) else []


class LessonPlan(BaseModel):
    title: str = ""
    scenes: list[ScenePlan] = []

    @field_validator("title", mode="before")
    @classmethod
    def _title(cls, v):
        if isinstance(v, dict):                      # the model sometimes nests the first scene here
            v = v.get("heading") or v.get("title") or ""
        return "" if v is None else str(v)

    @field_validator("scenes", mode="before")
    @classmethod
    def _real_scenes(cls, v):
        """Drop what is not a scene (an empty {} or a stray string): the rest of the plan is still good."""
        return [x for x in v if isinstance(x, dict) and (x.get("narration") or x.get("heading"))] if isinstance(v, list) else []


# Which fields hold text a viewer sees or hears (and so must be translated).
TEXT_FIELDS = ("heading", "narration", "left_title", "right_title")
LIST_FIELDS = ("items", "left", "right")

MIN_ITEMS = {"bullets": 2, "flow": 2, "cycle": 3, "diagram": 2, "quiz": 2, "summary": 2}
MAX_CODE_LINES, MAX_CODE_COLS = 11, 72
CURVE_NAMES = {"line": "Line", "parabola": "Parabola", "cubic": "Cubic curve", "sine": "Sine wave", "cosine": "Cosine wave",
               "exp": "Exponential curve", "abs": "Absolute value", "sqrt": "Square root", "reciprocal": "Reciprocal",
               "circle": "Circle", "ellipse": "Ellipse"}
MARK_NAMES = {"center": "Centre", "radius": "Radius", "diameter": "Diameter", "chord": "Chord", "tangent": "Tangent", "point": "Point", "link": "Segment"}


def _finite(*vals: float) -> bool:
    return all(v == v and abs(v) < 1e6 for v in vals)


def _normalize_graph(s: ScenePlan) -> None:
    """Keep only curves/marks the renderer can draw; a graph scene with nothing to draw becomes bullets."""
    s.curves = [c for c in s.curves if _finite(c.a, c.b, c.c, c.d)][:3]
    s.curves = [c for c in s.curves if not (c.type == "circle" and c.c <= 0)
                and not (c.type == "ellipse" and (c.c <= 0 or c.d <= 0))]
    has_circle = any(c.type == "circle" for c in s.curves)
    s.marks = [m for m in s.marks if _finite(m.x, m.y) and (has_circle or m.kind in ("point", "link"))][:6]
    for name in ("x_range", "y_range"):
        r = getattr(s, name)
        setattr(s, name, sorted(r[:2]) if len(r) >= 2 and _finite(*r[:2]) and r[0] != r[1] else [])
    s.equation = s.equation.strip()[:60]
    if s.template == "graph" and not s.curves and not any(m.kind == "point" for m in s.marks):
        s._wanted = "graph"                       # nothing to draw: the director can still rebuild this scene
        s.template = "bullets" if len(s.items) >= 2 else "title"
    if s.template == "graph":
        # One label per revealed thing (curves, then marks). Fill gaps so a terse LLM answer still looks finished;
        # these English defaults are translated with everything else.
        names = [CURVE_NAMES.get(c.type, "Curve") for c in s.curves] + [
            f"Point ({m.x:g}, {m.y:g})" if m.kind == "point" else MARK_NAMES[m.kind] for m in s.marks]
        s.items = s.items[:len(names)] + names[len(s.items):]
    else:
        s.curves, s.marks, s.x_range, s.y_range, s.equation = [], [], [], [], ""


def _normalize_code(s: ScenePlan) -> None:
    s.code = [ln.rstrip().replace("\t", "    ")[:MAX_CODE_COLS] for ln in s.code if ln.strip()][:MAX_CODE_LINES]
    s.output = [ln.rstrip()[:MAX_CODE_COLS] for ln in s.output if ln.strip()][:3]
    s.code_lang = s.code_lang.strip().lower()[:12]
    s.highlights = [h for h in s.highlights if 0 <= h < len(s.code)][:6]
    if s.template == "code" and len(s.code) < 1:
        s.template = "bullets" if len(s.items) >= 2 else "title"
    if s.template == "code":
        if not s.highlights:                      # walk the lines in order, in step with the narration
            s.highlights = list(range(min(len(s.code), 6)))
        s.items = s.items[:len(s.highlights)] + [f"Line {h + 1}" for h in s.highlights[len(s.items):]]
    if s.template != "code":
        s.code, s.output, s.highlights, s.code_lang = [], [], [], ""


def points_from_narration(narration: str, limit: int = 4) -> list[str]:
    """Short labels (max 5 words) from the sentences of a narration, used when the model gave no points."""
    out: list[str] = []
    for sentence in re.split(r"(?<=[.!?।])\s+", narration.strip()):
        words = sentence.strip(" .!?।,;:").split()
        if len(words) >= 2:
            out.append(" ".join(words[:5]) + ("…" if len(words) > 5 else ""))
    return out[:limit]


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
        _normalize_graph(s)
        _normalize_code(s)
        if s.template == "quiz" and not all(i.isdigit() for i in s.items):
            # Small models sometimes leak the answer index ("0") into the options.
            s.items = [i for i in s.items if not i.isdigit()]
        if s.template == "compare" and not (s.left and s.right):
            s._wanted = s._wanted or "compare"
            s.template = "bullets" if len(s.items) >= 2 else "title"
        if len(s.items) < MIN_ITEMS.get(s.template, 0):
            # Do not silently turn the scene into a plain title card (that made whole videos of identical bulb
            # scenes): rebuild points from the narration, and remember what was wanted for the director agent.
            s._wanted = s._wanted or s.template
            points = points_from_narration(s.narration)
            if len(points) >= 2 and s.template in ("bullets", "flow", "cycle", "diagram", "summary"):
                s.items = points[:5]
            elif len(points) >= 2:
                s.items, s.template = points[:5], "bullets"
            else:
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
