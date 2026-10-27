"""Concept -> LessonPlan, using a local LLM through Ollama with a JSON schema."""
from __future__ import annotations

import json
import logging

import requests
from pydantic import ValidationError

from . import config
from .schema import ICONS, LessonPlan, ScenePlan, normalize

log = logging.getLogger(__name__)

SYSTEM_PROMPT = f"""You are an expert school teacher who designs short animated video lessons.
Return ONLY a JSON lesson plan. You never write code; you choose a scene template and fill its fields.

Lesson shape (5-7 scenes; the length and level are given in the request):
1. "title" scene: hook the student with a question or surprising fact.
2-5. Teach the core idea step by step, using the best-fitting templates.
   Include one everyday example or analogy that an Indian school student knows.
6. "quiz" scene: one multiple-choice question about the key idea.
7. "summary" scene: 2-4 recap points.

Templates and the fields they use:
- title:   heading, narration, icon
- bullets: heading, narration, items (2-5 key points)
- flow:    heading, narration, items (2-5 steps in order, e.g. a process)
- cycle:   heading, narration, items (3-5 stages that repeat, e.g. water cycle)
- compare: heading, narration, left_title, left (2-4), right_title, right (2-4)
- diagram: heading (the central thing), narration, items (2-5 labelled parts around it)
- quiz:    heading (the question), narration (asks it, then reveals the answer), items (3 options), answer_index (0-based)
- summary: heading, narration, items (2-4 recap points)
- graph:   heading, narration, curves (1-3), marks (0-4), equation, items (one short label per curve, then one per mark, in that order), optional x_range/y_range
- code:    heading, narration, code_lang, code (3-10 short lines, each under 45 characters: split long statements over several lines, never cut a line short), highlights (line numbers 0-based, in the order the narration explains them), items (one short note per highlight, same order), output (what it prints, optional)

Choose the scenes by subject:
- MATHS / geometry / physics curves (circle, parabola, line, sine wave, exponential, trigonometry, quadratic, graphs, functions): use 2-3 "graph" scenes. Curve types and parameters:
  line y=a*x+b | parabola y=a*x^2+b*x+c | cubic y=a*x^3+b*x^2+c*x+d | sine or cosine y=a*sin(b*x+c)+d | exp y=a*e^(b*x)+c
  abs y=a*|x-b|+c | sqrt y=a*sqrt(x-b)+c | reciprocal y=a/x | circle centre (a,b) radius c | ellipse centre (a,b) semi-axes c (x), d (y).
  marks: for a circle use center, radius, diameter, chord, tangent; use point with x,y for any dot. Reveal one thing per narrated sentence.
- PROGRAMMING (Python, Rust, JavaScript, React, SQL, Java, Go, any language or framework): use 2-3 "code" scenes with REAL, correct, tiny snippets
  (a first example, then the key idea), and a "flow" or "diagram" for the concept. React snippets use code_lang "jsx". The code is only shown, never run.
- REQUIRED: a maths topic MUST contain at least 2 "graph" scenes (build up: the shape and its parts first, then a second view such as a related curve, a point or a worked value).
  A programming topic MUST contain at least 2 "code" scenes (first a tiny working example, then the next key idea), never only "bullets".
- Other subjects: use the generic templates only.

Example graph scene: {{"template":"graph","heading":"Parts of a circle","narration":"A circle is all points at the same distance from the centre. That distance is the radius. Twice the radius is the diameter.","curves":[{{"type":"circle","a":0,"b":0,"c":3}}],"marks":[{{"kind":"center"}},{{"kind":"radius"}},{{"kind":"diameter"}}],"equation":"x^2 + y^2 = r^2","items":["Circle","Centre","Radius","Diameter"]}}
Example graph scene 2: {{"template":"graph","heading":"A parabola","narration":"The graph of y equals x squared is a U shape. It touches zero at the bottom. At x equals two, y is four.","curves":[{{"type":"parabola","a":1,"b":0,"c":0}}],"marks":[{{"kind":"point","x":2,"y":4}}],"equation":"y = x^2","items":["Parabola","Point (2, 4)"]}}
Example code scene: {{"template":"code","heading":"A for loop","narration":"The list holds three fruits. The for loop visits each fruit in turn. And print shows it.","code_lang":"python","code":["fruits = ['apple', 'mango', 'kiwi']","for fruit in fruits:","    print(fruit)"],"highlights":[0,1,2],"items":["A list of fruits","Visit each one","Show it"],"output":["apple","mango","kiwi"]}}

Rules:
- narration is what the teacher says aloud: simple, warm, 2-3 sentences of about 25 words in total per scene (never fewer than 15 words), no lists, no markdown, no emojis.
- heading max 6 words. Each item max 5 words.
- Write the narration so it walks through the items in the same order they appear.
- For code and graph scenes the narration must follow the same order as items and highlights.
- icon must be one of: {", ".join(ICONS)}.
- Write everything in English (it is translated later)."""


def plan_lesson(concept: str, level: str = "beginner", duration_s: int = 60, context: str = "",
                on_progress=lambda f: None, wps: float = 2.3) -> LessonPlan:
    if config.LLM_BACKEND == "mock":
        return normalize(sample_for(concept))
    last_error = ""
    for attempt in range(2):
        try:
            try:
                raw = _ollama_chat(concept, last_error, level, duration_s, context, on_progress, wps)
            except requests.RequestException as e:
                raise RuntimeError(
                    f"Cannot reach Ollama at {config.OLLAMA_URL} with model '{config.OLLAMA_MODEL}'. "
                    f"Start it with `ollama serve` and `ollama pull {config.OLLAMA_MODEL}`. ({e})"
                ) from e
            return normalize(LessonPlan.model_validate_json(raw))
        except (ValidationError, ValueError, json.JSONDecodeError) as e:
            last_error = str(e)[:500]
            log.warning("Plan attempt %d invalid: %s", attempt + 1, last_error)
    log.error("LLM failed twice; using fallback plan")
    return normalize(fallback_plan(concept))


def _ollama_chat(concept: str, previous_error: str, level: str = "beginner", duration_s: int = 60,
                 context: str = "", on_progress=lambda f: None, wps: float = 2.3) -> str:
    words = round(duration_s * wps / 10) * 10                 # spoken words per second of the slowest chosen language
    scenes = 4 if duration_s <= 40 else 5 if duration_s <= 55 else 6 if duration_s <= 75 else 7
    audience = ("a complete beginner: plain words, one idea per scene, everyday examples" if level == "beginner"
                else "an intermediate learner: assume the basics, add the why and one deeper detail or edge case")
    user = (f"Create a lesson plan that explains: {concept}\n"
            f"Audience: {audience}.\n"
            f"Length: exactly {scenes} scenes and about {words} spoken words in total (about {duration_s} seconds).")
    if context:
        user += f"\nTeach from this source material (use only facts found in it):\n{context[:3000]}"
    if previous_error:
        user += f"\nYour previous answer was invalid ({previous_error}). Follow the schema exactly."
    resp = requests.post(
        f"{config.OLLAMA_URL}/api/chat",
        json={
            "model": config.OLLAMA_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user},
            ],
            "format": LessonPlan.model_json_schema(),
            "stream": True,
            "keep_alive": config.OLLAMA_KEEP_ALIVE,
            "options": config.ollama_options({"temperature": 0.4, "num_ctx": 4096}),
        },
        timeout=300,
        stream=True,
    )
    resp.raise_for_status()
    # Streamed: each chunk is about one token, so progress = tokens so far / tokens a lesson of this length needs.
    expected = max(350, duration_s * 12)
    parts: list[str] = []
    n = 0
    for line in resp.iter_lines():
        if not line:
            continue
        chunk = json.loads(line)
        parts.append(chunk.get("message", {}).get("content", ""))
        n += 1
        if n % 6 == 0:
            on_progress(min(n / expected, 0.97))
        if chunk.get("done"):
            break
    on_progress(1.0)
    return "".join(parts)


def ollama_generate(prompt: str) -> str:
    """Plain completion, used by the 'ollama' translation backend."""
    resp = requests.post(
        f"{config.OLLAMA_URL}/api/generate",
        json={"model": config.OLLAMA_MODEL, "prompt": prompt, "stream": False,
              "keep_alive": "5m", "options": config.ollama_options({"temperature": 0.1})},
        timeout=300,
    )
    resp.raise_for_status()
    return resp.json()["response"].strip()


def fallback_plan(concept: str) -> LessonPlan:
    c = concept.strip().rstrip("?.")
    return LessonPlan(title=c, scenes=[
        ScenePlan(template="title", heading=c, icon="lightbulb",
                  narration=f"Today we will understand {c}, one simple step at a time."),
        ScenePlan(template="summary", heading="Remember", items=[c],
                  narration=f"Think about where you see {c} in daily life, and ask your teacher one question about it."),
    ])


def sample_for(concept: str) -> LessonPlan:
    """Pick the hand-written sample that matches the topic, so every scene type can be tested offline."""
    c = concept.lower()
    if any(w in c for w in ("circle", "parabola", "graph", "sine", "quadratic")):
        return sample_circle()
    if any(w in c for w in ("python", "rust", "react", "javascript", "code", "loop")):
        return sample_code()
    return sample_plan()


def sample_circle() -> LessonPlan:
    return LessonPlan.model_validate({
        "title": "The Circle",
        "scenes": [
            {"template": "title", "heading": "What is a circle?", "icon": "earth",
             "narration": "A wheel, a clock, a coin. What shape do they share? A circle."},
            {"template": "graph", "heading": "Parts of a circle", "equation": "x^2 + y^2 = r^2",
             "curves": [{"type": "circle", "a": 0, "b": 0, "c": 3}],
             "marks": [{"kind": "center"}, {"kind": "radius"}, {"kind": "diameter"}],
             "items": ["Circle", "Centre", "Radius", "Diameter"],
             "narration": "A circle is every point at the same distance from its centre. That distance is the radius. And a line through the centre, twice the radius, is the diameter."},
            {"template": "graph", "heading": "Chord and tangent", "equation": "x^2 + y^2 = 9",
             "curves": [{"type": "circle", "a": 0, "b": 0, "c": 3}],
             "marks": [{"kind": "chord"}, {"kind": "tangent"}],
             "items": ["Circle", "Chord", "Tangent"],
             "narration": "A chord joins two points on the circle. A tangent touches it at exactly one point."},
            {"template": "graph", "heading": "Compare with a parabola", "equation": "y = x^2",
             "curves": [{"type": "parabola", "a": 1, "b": 0, "c": 0}, {"type": "line", "a": 2, "b": 3}],
             "marks": [{"kind": "point", "x": 3, "y": 9}],
             "items": ["Parabola", "Line", "Meeting point"],
             "narration": "Other curves have their own shapes. A parabola bends like a bowl, and a straight line can cut through it."},
            {"template": "quiz", "heading": "If the radius is 5, the diameter is?", "icon": "lightbulb",
             "items": ["5", "10", "25"], "answer_index": 1,
             "narration": "Quick question. If the radius is five, what is the diameter? Ten, because it is twice the radius."},
            {"template": "summary", "heading": "Remember", "items": ["Radius: centre to edge", "Diameter: twice the radius", "Chord and tangent"],
             "narration": "The radius runs from the centre to the edge, the diameter is twice that, and chords and tangents are lines that meet the circle."},
        ],
    })


def sample_code() -> LessonPlan:
    return LessonPlan.model_validate({
        "title": "Python for loops",
        "scenes": [
            {"template": "title", "heading": "Do things again and again", "icon": "gear",
             "narration": "Imagine greeting every friend in your class one by one. A for loop does exactly that for you."},
            {"template": "code", "heading": "A for loop", "code_lang": "python",
             "code": ["fruits = ['apple', 'mango', 'kiwi']", "for fruit in fruits:", "    print(fruit)"],
             "highlights": [0, 1, 2], "items": ["A list of fruits", "Visit each fruit", "Show it"],
             "output": ["apple", "mango", "kiwi"],
             "narration": "First we make a list of three fruits. The for loop then visits each fruit in turn. And print shows it on the screen."},
            {"template": "code", "heading": "Count with range", "code_lang": "python",
             "code": ["total = 0", "for n in range(1, 6):", "    total += n", "print(total)"],
             "highlights": [0, 1, 2, 3], "items": ["Start at zero", "Numbers 1 to 5", "Add each number", "Show the sum"],
             "output": ["15"],
             "narration": "Start the total at zero. Loop over the numbers one to five. Add each number to the total. Finally print the sum, fifteen."},
            {"template": "flow", "heading": "How the loop runs", "items": ["Take next item", "Run the body", "Any items left?", "Done"],
             "narration": "Each round takes the next item, runs the body, and checks if any items are left. When none remain, the loop is done."},
            {"template": "summary", "heading": "Remember", "items": ["for visits every item", "range makes numbers", "Indent the body"],
             "narration": "A for loop visits every item, range makes a run of numbers, and the indented lines are what repeats."},
        ],
    })


def sample_plan() -> LessonPlan:
    """A hand-written lesson for testing the whole pipeline without any model."""
    return LessonPlan.model_validate({
        "title": "Photosynthesis",
        "scenes": [
            {"template": "title", "heading": "How do plants eat?", "icon": "leaf",
             "narration": "Plants never go to a kitchen, yet they make their own food every day. How do they do it?"},
            {"template": "diagram", "heading": "Leaf", "icon": "leaf",
             "items": ["Sunlight", "Water", "Carbon dioxide", "Chlorophyll"],
             "narration": "A leaf needs sunlight, water from the roots, and carbon dioxide from the air. The green chlorophyll captures the light."},
            {"template": "flow", "heading": "The recipe", "icon": "sun",
             "items": ["Light is captured", "Water is split", "Sugar is made", "Oxygen is released"],
             "narration": "First, light is captured. Then water is split. Next, sugar is made, and finally oxygen is released into the air."},
            {"template": "compare", "heading": "Inputs and outputs", "icon": "flask",
             "left_title": "Goes in", "left": ["Sunlight", "Water", "Carbon dioxide"],
             "right_title": "Comes out", "right": ["Glucose", "Oxygen"],
             "narration": "Sunlight, water and carbon dioxide go in. Glucose and oxygen come out. Just like a chapati maker turns flour and water into chapatis!"},
            {"template": "quiz", "heading": "Which gas do plants release?", "icon": "cloud",
             "items": ["Nitrogen", "Oxygen", "Carbon dioxide"], "answer_index": 1,
             "narration": "Quick question. Which gas do plants release? The answer is oxygen, the air we breathe."},
            {"template": "summary", "heading": "Remember", "icon": "lightbulb",
             "items": ["Plants make food", "They need light", "They give us oxygen"],
             "narration": "Plants make their own food, they need light to do it, and they give us the oxygen we breathe."},
        ],
    })
