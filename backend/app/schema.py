"""The lesson plan the LLM must return. It is pure data: the model picks a template
and fills its slots, and the renderer (our code) decides how it looks and moves."""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, PrivateAttr, field_validator

Template = Literal["title", "bullets", "flow", "cycle", "compare", "diagram", "quiz", "summary", "graph", "code", "network"]
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


class Edge(BaseModel):
    """An arrow from node `src` to node `dst` (0-based positions in `nodes`)."""
    src: int = 0
    dst: int = 0


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
    # network scenes: the model lists the boxes and the arrows; positions are computed (layout.py), never written by the model
    nodes: list[str] = Field(default_factory=list, description="network scenes: 3-8 short labels, max 4 words each")
    edges: list[Edge] = Field(default_factory=list, description="network scenes: arrows {src, dst} as positions in nodes")
    positions: list[list[float]] = Field(default_factory=list, description="computed: [x, y] of every node")

    @field_validator("edges", mode="before")
    @classmethod
    def _edges(cls, v):
        """Arrows as {"src": 0, "dst": 1}, {"from": 0, "to": 1} or [0, 1]; anything else is dropped."""
        out = []
        for e in v if isinstance(v, list) else []:
            try:
                if isinstance(e, dict):
                    a, b = e.get("src", e.get("from")), e.get("dst", e.get("to"))
                elif isinstance(e, (list, tuple)) and len(e) >= 2:
                    a, b = e[0], e[1]
                else:
                    continue
                out.append({"src": int(a), "dst": int(b)})
            except (TypeError, ValueError):
                continue
        return out

    @field_validator("nodes", mode="before")
    @classmethod
    def _nodes(cls, v):
        return [str(x) for x in v if isinstance(x, (str, int, float))] if isinstance(v, list) else []

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


class Mistake(BaseModel):
    wrong: str = Field("", description="a common wrong belief, max 14 words")
    right: str = Field("", description="the correct fact, max 14 words")


class LessonPlan(BaseModel):
    title: str = ""
    scenes: list[ScenePlan] = []
    common_mistakes: list[Mistake] = Field(default_factory=list, description="0-2 common wrong beliefs with the correction; shown as a compare scene")

    @field_validator("common_mistakes", mode="before")
    @classmethod
    def _mistakes(cls, v):
        if not isinstance(v, list):
            return []
        return [m for m in v if isinstance(m, dict) and str(m.get("wrong", "")).strip() and str(m.get("right", "")).strip()][:3]

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
        if not isinstance(v, list):
            return []
        return [x for x in v if isinstance(x, ScenePlan) or (isinstance(x, dict) and (x.get("narration") or x.get("heading")))]


# Which fields hold text a viewer sees or hears (and so must be translated).
TEXT_FIELDS = ("heading", "narration", "left_title", "right_title")
LIST_FIELDS = ("items", "left", "right", "nodes")

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


def _normalize_network(s: ScenePlan) -> None:
    """Clean the boxes and arrows, and compute where everything goes. A network that cannot be drawn becomes a flow of its boxes."""
    from .layout import layered
    nodes: list[str] = []
    remap: dict[int, int] = {}
    for i, label in enumerate(s.nodes[:12]):
        label = " ".join(label.split())[:40]
        if label and label.lower() not in [n.lower() for n in nodes]:
            remap[i] = len(nodes)
            nodes.append(label)
    seen: set[tuple[int, int]] = set()
    edges: list[Edge] = []
    for e in s.edges:
        a, b = remap.get(e.src), remap.get(e.dst)
        if a is not None and b is not None and a != b and (a, b) not in seen:
            seen.add((a, b))
            edges.append(Edge(src=a, dst=b))
    nodes, edges = nodes[:8], [e for e in edges if e.src < 8 and e.dst < 8][:14]
    if s.template == "network" and (len(nodes) < 3 or not edges):
        s._wanted = s._wanted or "network"
        s.items = s.items or nodes
        s.template = "flow" if len(s.items) >= 2 else "bullets"
        nodes, edges = [], []
    s.nodes, s.edges = (nodes, edges) if s.template == "network" else ([], [])
    s.positions = layered(len(s.nodes), [(e.src, e.dst) for e in s.edges]) if s.template == "network" else []


def points_from_narration(narration: str, limit: int = 4) -> list[str]:
    """Short labels (max 5 words) from the sentences of a narration, used when the model gave no points."""
    out: list[str] = []
    for sentence in re.split(r"(?<=[.!?।])\s+", narration.strip()):
        words = sentence.strip(" .!?।,;:").split()
        if len(words) >= 2:
            out.append(" ".join(words[:5]) + ("…" if len(words) > 5 else ""))
    return out[:limit]


SCHEMA_WORDS = {"string", "heading", "title", "text", "narration", "scene title", "scene heading", "...", "null", "none", "n/a"}


def normalize(plan: LessonPlan, segment: bool = False, last: bool = True, title: bool | None = None) -> LessonPlan:
    """Repair the small mistakes local models make so the renderer never sees bad data. A `segment` (one part of a longer video) gets no title card
    of its own (that was the \"title card in the middle\" with the caption \"Let's learn about ...\"), and only the `last` part gets the misconceptions scene."""
    scenes: list[ScenePlan] = []
    for s in plan.scenes[:24]:                                  # a 4-minute video has up to ~20 scenes
        s.items = [i.strip() for i in s.items if i and i.strip()][:6]
        s.left = [i.strip() for i in s.left if i and i.strip()][:4]
        s.right = [i.strip() for i in s.right if i and i.strip()][:4]
        s.heading = s.heading.strip()
        if not s.heading or s.heading.lower().strip(".:") in SCHEMA_WORDS:
            s.heading = plan.title                          # the model copied a word of the schema ("string") instead of writing a heading
        s.narration = " ".join(s.narration.split())
        if not s.narration:
            continue
        _normalize_graph(s)
        _normalize_code(s)
        _normalize_network(s)
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
    if scenes[0].template != "title" and (not segment if title is None else title):      # (the first part of a long video gets the opening card, the others do not)
        scenes.insert(0, ScenePlan(template="title", heading=plan.title,
                                   narration=f"Let's learn about {plan.title}.", icon=scenes[0].icon))
    if not segment or last:
        _add_misconceptions(plan, scenes)
    plan.scenes = scenes
    return plan


def _add_misconceptions(plan: LessonPlan, scenes: list[ScenePlan]) -> None:
    """The planner's common_mistakes become one compare scene (wrong belief on the left, the fact on the right), placed before the closing
    quiz or summary. No new template: it is an ordinary compare scene. Skipped when the lesson is too short or already compares."""
    pairs = [m for m in plan.common_mistakes if m.wrong.strip() and m.right.strip()][:2]
    if not pairs or len(scenes) < 4 or any(s.template == "compare" for s in scenes):
        return
    first = pairs[0]
    spoken = f"A common mistake: many people think {first.wrong.strip().rstrip('.')}. In fact, {first.right.strip().rstrip('.')}."
    if len(pairs) > 1:
        spoken += f" Another one: {pairs[1].wrong.strip().rstrip('.')}. But {pairs[1].right.strip().rstrip('.')}."
    scene = ScenePlan(template="compare", heading="Common mistakes", narration=spoken, left_title="What people think", right_title="What is true",
                      left=[p.wrong.strip() for p in pairs], right=[p.right.strip() for p in pairs], icon="lightbulb")
    at = len(scenes) - 1 if scenes[-1].template in ("quiz", "summary") else len(scenes)
    if len(scenes) >= 2 and scenes[-1].template == "quiz" and scenes[-2].template == "summary":
        at = len(scenes) - 2
    scenes.insert(at, scene)
