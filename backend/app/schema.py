"""The lesson plan the LLM must return. It is pure data: the model picks a template
and fills its slots, and the renderer (our code) decides how it looks and moves."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Template = Literal["title", "bullets", "flow", "cycle", "compare", "diagram", "quiz", "summary", "graph", "code"]
CurveType = Literal["line", "parabola", "cubic", "sine", "cosine", "exp", "abs", "sqrt", "reciprocal", "circle", "ellipse"]
MarkKind = Literal["center", "radius", "diameter", "chord", "tangent", "point"]
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


class LessonPlan(BaseModel):
    title: str
    scenes: list[ScenePlan]


# Which fields hold text a viewer sees or hears (and so must be translated).
TEXT_FIELDS = ("heading", "narration", "left_title", "right_title")
LIST_FIELDS = ("items", "left", "right")

MIN_ITEMS = {"bullets": 2, "flow": 2, "cycle": 3, "diagram": 2, "quiz": 2, "summary": 2}
MAX_CODE_LINES, MAX_CODE_COLS = 11, 72
CURVE_NAMES = {"line": "Line", "parabola": "Parabola", "cubic": "Cubic curve", "sine": "Sine wave", "cosine": "Cosine wave",
               "exp": "Exponential curve", "abs": "Absolute value", "sqrt": "Square root", "reciprocal": "Reciprocal",
               "circle": "Circle", "ellipse": "Ellipse"}
MARK_NAMES = {"center": "Centre", "radius": "Radius", "diameter": "Diameter", "chord": "Chord", "tangent": "Tangent", "point": "Point"}


def _finite(*vals: float) -> bool:
    return all(v == v and abs(v) < 1e6 for v in vals)


def _normalize_graph(s: ScenePlan) -> None:
    """Keep only curves/marks the renderer can draw; a graph scene with nothing to draw becomes bullets."""
    s.curves = [c for c in s.curves if _finite(c.a, c.b, c.c, c.d)][:3]
    s.curves = [c for c in s.curves if not (c.type == "circle" and c.c <= 0)
                and not (c.type == "ellipse" and (c.c <= 0 or c.d <= 0))]
    has_circle = any(c.type == "circle" for c in s.curves)
    s.marks = [m for m in s.marks if _finite(m.x, m.y) and (has_circle or m.kind == "point")][:4]
    for name in ("x_range", "y_range"):
        r = getattr(s, name)
        setattr(s, name, sorted(r[:2]) if len(r) >= 2 and _finite(*r[:2]) and r[0] != r[1] else [])
    s.equation = s.equation.strip()[:60]
    if s.template == "graph" and not s.curves:
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
