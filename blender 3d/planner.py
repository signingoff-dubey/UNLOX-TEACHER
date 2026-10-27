"""Plans a 3D lesson with the local model. The model only ever returns JSON data, constrained by a schema, and
everything it returns is validated and clamped here before Blender sees it."""
from __future__ import annotations

import json
import re

TEMPLATES = {   # hand-built scenes (blender/templates.py) used when they fit the question
    "seasons": {"focus": ["intro", "tilt", "june", "december", "orbit"],
                "about": "why the Earth has seasons: tilted axis, orbit, solstices, day length"},
    "solar_system": {"focus": ["overview", "inner", "outer", "earth", "sun"],
                     "about": "the Sun and the eight planets: order, sizes, orbits"},
    "atom": {"focus": ["overview", "nucleus", "shells", "electrons"],
             "about": "structure of one atom (Bohr model): protons, neutrons, electron shells"},
}
ELEMENTS = ["hydrogen", "helium", "lithium", "carbon", "nitrogen", "oxygen", "neon", "sodium", "magnesium",
            "chlorine", "argon", "calcium"]
KINDS = ["sphere", "box", "bar", "cylinder", "cone", "torus", "ring", "plane", "arrow", "planet", "star", "atom",
         "molecule", "cell", "wave", "spring", "leaf", "tree", "cloud", "drop"]
COLORS = ["red", "orange", "yellow", "green", "teal", "blue", "sky", "purple", "pink", "white", "grey", "black",
          "brown", "gold", "silver", "skin"]
FINISHES = ["matte", "glossy", "metal", "glass", "glow"]
ENVIRONMENTS = ["space", "studio", "sky", "lab", "underwater"]
CAMERAS = ["wide", "close", "orbit", "top", "side", "low"]
ACTIONS = ["appear", "disappear", "move", "rotate", "spin", "orbit", "grow", "shrink", "stretch", "pulse", "highlight"]


def _chat(schema: dict, system: str, prompt: str, temperature: float = 0.3) -> dict:
    import requests
    from app import config
    last = None
    for attempt in range(2):
        r = requests.post(f"{config.OLLAMA_URL}/api/chat", timeout=600, json={
            "model": config.OLLAMA_MODEL, "stream": False, "format": schema,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            "options": {"temperature": temperature + 0.2 * attempt, "num_ctx": 8192}})
        r.raise_for_status()
        try:
            return json.loads(r.json()["message"]["content"])
        except json.JSONDecodeError as e:
            last = e
    raise RuntimeError(f"the model did not return valid JSON: {last}")


SYSTEM = "You plan short narrated 3D science and maths videos for school students. Reply with JSON only."


def route(concept: str) -> str:
    """'seasons' / 'solar_system' / 'atom' when a hand-built scene fits exactly, else 'custom'."""
    menu = "\n".join(f"- {k}: {v['about']}" for k, v in TEMPLATES.items())
    out = _chat({"type": "object", "required": ["choice"], "properties": {"choice": {"enum": [*TEMPLATES, "custom"]}}},
                SYSTEM, f"Topic: {concept!r}\nHand-built 3D scenes:\n{menu}\n"
                        "Answer with the scene's name only if the topic is exactly what it shows; otherwise 'custom'.", 0.0)
    return out.get("choice", "custom")


def plan_template(concept: str, template: str) -> dict:
    t = TEMPLATES[template]
    schema = {"type": "object", "required": ["element", "shots"], "properties": {
        "element": {"enum": ELEMENTS},
        "shots": {"type": "array", "minItems": 3, "maxItems": 6, "items": {
            "type": "object", "required": ["focus", "narration"],
            "properties": {"focus": {"enum": t["focus"]}, "narration": {"type": "string"}}}}}}
    plan = _chat(schema, SYSTEM, f"Topic: {concept!r}. The 3D scene shows {t['about']}. Camera shots available: "
                                 f"{', '.join(t['focus'])}. Write 3 to 5 shots in order, each with one or two short "
                                 "spoken sentences (max 30 words) for a 12-year-old. Set element for atoms.")
    named = [e for e in ELEMENTS if re.search(rf"\b{e}\b", concept.lower())]
    shots = [{"focus": s["focus"] if s.get("focus") in t["focus"] else t["focus"][0], "narration": s["narration"].strip()}
             for s in plan.get("shots", []) if str(s.get("narration", "")).strip()]
    if not shots:
        raise RuntimeError("the plan had no narration")
    return {"template": template, "element": named[0] if named else plan.get("element", "carbon"), "shots": shots}


EXAMPLE = {   # teaches the format; deliberately a different topic from most questions
    "environment": "lab",
    "objects": [
        {"id": "plank", "kind": "box", "color": "brown", "finish": "matte", "x": 0, "y": 0, "z": 1.0, "size": 1,
         "sx": 5, "sy": 0.8, "sz": 0.15, "label": "lever", "param": ""},
        {"id": "fulcrum", "kind": "cone", "color": "grey", "finish": "metal", "x": 0, "y": 0, "z": 0.45, "size": 0.9,
         "sx": 1, "sy": 1, "sz": 1, "label": "fulcrum", "param": ""},
        {"id": "load", "kind": "box", "color": "blue", "finish": "glossy", "x": -2.0, "y": 0, "z": 1.5, "size": 0.8,
         "sx": 1, "sy": 1, "sz": 1, "label": "load", "param": ""},
        {"id": "effort", "kind": "arrow", "color": "red", "finish": "glow", "x": 2.2, "y": 0, "z": 2.0, "size": 1.2,
         "sx": 1, "sy": 1, "sz": 1, "label": "effort", "param": "down"}],
    "shots": [
        {"narration": "A lever is a stiff bar that turns on a point called the fulcrum.", "camera": "wide", "focus": "",
         "actions": [{"do": "appear", "target": "plank", "with": "", "x": 0, "y": 0, "z": 0, "amount": 0},
                     {"do": "appear", "target": "fulcrum", "with": "", "x": 0, "y": 0, "z": 0, "amount": 0}]},
        {"narration": "Put a heavy load on one end.", "camera": "close", "focus": "load",
         "actions": [{"do": "appear", "target": "load", "with": "", "x": 0, "y": 0, "z": 0, "amount": 0}]},
        {"narration": "Push down on the other end, and the load goes up with less effort.", "camera": "side", "focus": "",
         "actions": [{"do": "appear", "target": "effort", "with": "", "x": 0, "y": 0, "z": 0, "amount": 0},
                     {"do": "rotate", "target": "plank", "with": "", "x": 0, "y": 0, "z": 0, "amount": 0},
                     {"do": "move", "target": "load", "with": "", "x": -2.0, "y": 0, "z": 2.0, "amount": 0},
                     {"do": "highlight", "target": "effort", "with": "", "x": 0, "y": 0, "z": 0, "amount": 0}]}]}


def plan_custom(concept: str) -> dict:
    num = {"type": "number"}
    obj = {"type": "object", "required": ["id", "kind", "color", "finish", "x", "y", "z", "size", "label", "param"],
           "properties": {"id": {"type": "string"}, "kind": {"enum": KINDS}, "color": {"enum": COLORS},
                          "finish": {"enum": FINISHES}, "x": num, "y": num, "z": num, "size": num,
                          "sx": num, "sy": num, "sz": num, "label": {"type": "string"}, "param": {"type": "string"}}}
    act = {"type": "object", "required": ["do", "target"],
           "properties": {"do": {"enum": ACTIONS}, "target": {"type": "string"}, "with": {"type": "string"},
                          "x": num, "y": num, "z": num, "amount": num}}
    shot = {"type": "object", "required": ["narration", "camera", "focus", "actions"],
            "properties": {"narration": {"type": "string"}, "camera": {"enum": CAMERAS}, "focus": {"type": "string"},
                           "actions": {"type": "array", "maxItems": 5, "items": act}}}
    schema = {"type": "object", "required": ["environment", "objects", "shots"], "properties": {
        "environment": {"enum": ENVIRONMENTS},
        "objects": {"type": "array", "minItems": 1, "maxItems": 12, "items": obj},
        "shots": {"type": "array", "minItems": 3, "maxItems": 6, "items": shot}}}
    prompt = f"""Design a 3D explanation of: {concept!r}

Build it from these parts (kind): {', '.join(KINDS)}.
- planet: param = earth, mars, jupiter, moon, venus, saturn... ; star: a glowing sun with light.
- atom: param = element name ({', '.join(ELEMENTS)}). molecule: param = formula (H2O, CO2, O2, CH4, NH3, NaCl, HCl, C6H6, or any formula).
- cell: a living cell with nucleus. wave: a moving water/sound wave surface. spring: a coil.
- leaf, tree, cloud, drop (a water drop): everyday nature objects; colour the leaf and tree green.
- arrow: param = right, left, up, down, toward or away (a force, flow or direction). bar: a chart bar standing on the floor.
Units: 1 = one metre. Keep everything between -6 and 6; z is up; the camera looks from -y. size = how big (0.3 to 5).
sx, sy, sz stretch a box or cylinder (for planks, rods, walls); use 1 when not needed.
label = a 1 to 3 word name shown above the object ("" for none). Use ids like "sun", "leaf", "plank".
Actions per shot (do): appear (pops in; anything that appears later starts hidden), disappear, move (to x y z), rotate (amount
degrees), spin (keeps spinning, amount degrees per second), orbit (target goes round "with", amount degrees per second),
grow / shrink / stretch (amount = times bigger or smaller), pulse, highlight.
camera: wide (everything), close (the focus object), orbit (circles the focus or everything), top, side, low.
Write 3 to 5 shots in teaching order; each narration is one or two short sentences (max 30 words) for a 12-year-old,
and the shot's actions show what the sentence says. Use 3 to 10 objects; show the idea, not decoration.
Lay objects out so they do not overlap: spread them left to right along x (about 1.5 to 3 apart), in the order the
story flows (inputs on the left, outputs on the right), all near z = 1. Give every important object a label.

Example of the format (a different topic):
{json.dumps(EXAMPLE)}"""
    return validate_scene(_chat(schema, SYSTEM, prompt))


def _num(v, lo, hi, default):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, v)) if v == v else default


def _extent(o: dict) -> float:
    """Rough radius of an object, including box/cylinder stretch."""
    return o["size"] / 2 * max(1.0, o["sx"], o["sy"], o["sz"])


def spread(objects: list[dict], orbiters: set[str], iterations: int = 60) -> None:
    """Small models often stack objects on one spot. Push overlapping objects apart (sideways first, so things
    stay above the floor), keeping each one near where the plan put it. Orbiting objects move on their own."""
    import math
    movable = [o for o in objects if o["id"] not in orbiters]
    for _ in range(iterations):
        moved = False
        for i, a in enumerate(movable):
            for b in movable[i + 1:]:
                need = (_extent(a) + _extent(b)) * 1.15
                dx, dy, dz = b["x"] - a["x"], b["y"] - a["y"], b["z"] - a["z"]
                d = math.sqrt(dx * dx + dy * dy + dz * dz)
                if d >= need:
                    continue
                push = (need - d) / 2
                if math.hypot(dx, dy) < 0.1 * need:   # stacked or on the same spot: split them sideways along x
                    ux, uy, uz = (1.0 if (i + objects.index(b)) % 2 else -1.0), 0.0, 0.0
                else:
                    ux, uy, uz = dx / d, dy / d, dz / d * 0.3                 # prefer sideways
                n = math.sqrt(ux * ux + uy * uy + uz * uz) or 1.0
                for o, sgn in ((a, -1), (b, 1)):
                    o["x"] += sgn * push * ux / n; o["y"] += sgn * push * uy / n; o["z"] += sgn * push * uz / n
                moved = True
        if not moved:
            break
    for o in objects:
        o["x"], o["y"], o["z"] = (round(max(-8.0, min(8.0, o[k])), 3) for k in ("x", "y", "z"))


def validate_scene(raw: dict) -> dict:
    objects, ids = [], set()
    for o in (raw.get("objects") or [])[:12]:
        oid = re.sub(r"[^a-z0-9_]", "_", str(o.get("id", "")).lower()).strip("_")[:20] or f"obj{len(objects)}"
        while oid in ids:
            oid += "_2"
        ids.add(oid)
        objects.append({
            "id": oid, "kind": o.get("kind") if o.get("kind") in KINDS else "sphere",
            "color": o.get("color") if o.get("color") in COLORS else "grey",
            "finish": o.get("finish") if o.get("finish") in FINISHES else "matte",
            "x": _num(o.get("x"), -8, 8, 0), "y": _num(o.get("y"), -8, 8, 0), "z": _num(o.get("z"), -8, 8, 0),
            "size": _num(o.get("size"), 0.2, 6, 1),
            "sx": _num(o.get("sx"), 0.1, 8, 1), "sy": _num(o.get("sy"), 0.1, 8, 1), "sz": _num(o.get("sz"), 0.1, 8, 1),
            "label": str(o.get("label") or "").strip()[:30], "param": str(o.get("param") or "").strip()[:24]})
    if not objects:
        raise RuntimeError("the plan had no objects")
    shots = []
    for s in (raw.get("shots") or [])[:7]:
        text = str(s.get("narration", "")).strip()[:300]
        if not text:
            continue
        acts = []
        for a in (s.get("actions") or [])[:5]:
            tgt = re.sub(r"[^a-z0-9_]", "_", str(a.get("target", "")).lower()).strip("_")
            if a.get("do") not in ACTIONS or tgt not in ids:
                continue
            w = re.sub(r"[^a-z0-9_]", "_", str(a.get("with", "")).lower()).strip("_")
            if a["do"] == "orbit" and w not in ids:
                continue
            acts.append({"do": a["do"], "target": tgt, "with": w if w in ids else "",
                         "x": _num(a.get("x"), -8, 8, 0), "y": _num(a.get("y"), -8, 8, 0), "z": _num(a.get("z"), -8, 8, 0),
                         "amount": _num(a.get("amount"), -720, 720, 0)})
        focus = re.sub(r"[^a-z0-9_]", "_", str(s.get("focus", "")).lower()).strip("_")
        shots.append({"narration": text, "camera": s.get("camera") if s.get("camera") in CAMERAS else "wide",
                      "focus": focus if focus in ids else "", "actions": acts})
    if not shots:
        raise RuntimeError("the plan had no narration")
    spread(objects, {a["target"] for s in shots for a in s["actions"] if a["do"] == "orbit"})
    return {"environment": raw.get("environment") if raw.get("environment") in ENVIRONMENTS else "studio",
            "objects": objects, "shots": shots}
