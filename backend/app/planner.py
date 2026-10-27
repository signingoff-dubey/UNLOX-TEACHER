"""Concept -> LessonPlan, using a local LLM through Ollama with a JSON schema."""
from __future__ import annotations

import json
import logging
import re

import requests
from pydantic import ValidationError

from . import config
from .knowledge import Passage, pages_passages, retrieve
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
- Coordinate geometry / graphs / plotting: use graph scenes with only points (no curve) to teach the plane, e.g.
  {{"template":"graph","heading":"Plotting points","curves":[],"marks":[{{"kind":"point","x":3,"y":2}},{{"kind":"point","x":-4,"y":1}},{{"kind":"link","x":-1,"y":-3}}],"items":["A(3, 2)","B(-4, 1)","C(-1, -3)"],"narration":"..."}}
  then a graph with a line or curve and its equation. Use "link" marks to draw a segment between points.
- VARIETY IS REQUIRED: never use the same template twice in a row, and use "title" only for the first scene. Every scene must show
  something different (graph, diagram, flow, cycle, compare, code, quiz), not only text.
- Other subjects: use the generic templates only.

Example graph scene: {{"template":"graph","heading":"Parts of a circle","narration":"A circle is all points at the same distance from the centre. That distance is the radius. Twice the radius is the diameter.","curves":[{{"type":"circle","a":0,"b":0,"c":3}}],"marks":[{{"kind":"center"}},{{"kind":"radius"}},{{"kind":"diameter"}}],"equation":"x^2 + y^2 = r^2","items":["Circle","Centre","Radius","Diameter"]}}
Example graph scene 2: {{"template":"graph","heading":"A parabola","narration":"The graph of y equals x squared is a U shape. It touches zero at the bottom. At x equals two, y is four.","curves":[{{"type":"parabola","a":1,"b":0,"c":0}}],"marks":[{{"kind":"point","x":2,"y":4}}],"equation":"y = x^2","items":["Parabola","Point (2, 4)"]}}
Example code scene: {{"template":"code","heading":"A for loop","narration":"The list holds three fruits. The for loop visits each fruit in turn. And print shows it.","code_lang":"python","code":["fruits = ['apple', 'mango', 'kiwi']","for fruit in fruits:","    print(fruit)"],"highlights":[0,1,2],"items":["A list of fruits","Visit each one","Show it"],"output":["apple","mango","kiwi"]}}

Rules:
- narration is what the teacher says aloud: simple, warm, 2-3 sentences of about 25 words in total per scene (never fewer than 15 words), no lists, no markdown, no emojis.
- Every scene teaches something new. Never repeat the same points in two scenes.
- diagram items are labelled parts or ingredients (nouns), never steps; steps belong in a flow scene.
- heading max 6 words. Each item max 5 words.
- Write the narration so it walks through the items in the same order they appear.
- For code and graph scenes the narration must follow the same order as items and highlights.
- icon must be one of: {", ".join(ICONS)}.
- Write everything in English (it is translated later)."""


PAGE_REQUEST = re.compile(r"\b(chapter|ch\.?|unit|lesson|section|page|pages|pp?\.)\s*\d", re.I)


def plan_lesson(concept: str, level: str = "beginner", duration_s: int = 60, upload: str | None = None, focus: str = "",
                on_progress=lambda f: None, wps: float = 2.3, series: dict | None = None) -> tuple[LessonPlan, list[dict]]:
    """Returns the lesson plan and the sources it was grounded in.

    - concept only: search the knowledge base / library.
    - concept + upload: search that PDF first, then the library.
    - upload with no concept, a `focus`, or a concept like "explain chapter 4": teach that part of
      the PDF from its passages in reading order."""
    if config.LLM_BACKEND == "mock":
        return normalize(sample_for(concept)), []
    page_mode = bool(upload) and (not concept or bool(focus) or bool(PAGE_REQUEST.search(concept)))
    passages: list[Passage] = []
    if page_mode:
        passages = pages_passages(upload, focus or (concept if PAGE_REQUEST.search(concept) else ""))
    if not passages:
        page_mode = False
        passages = retrieve(concept or focus, upload=upload)
    sources = _page_sources(passages) if page_mode else _sources(passages)
    reference = _condensed_block(passages) if page_mode else _reference_block(passages)
    if upload and not focus and not concept.strip():
        from .ocr import digest                      # a whole PDF: plan from its study notes (a few KB), not from every page
        from .ocr.ingest import upload_dir
        reference = digest.reference(upload_dir(upload)) or reference
    if page_mode:
        book = passages[0].title
        part = focus or (concept if PAGE_REQUEST.search(concept) else "") or passages[0].section or "this chapter"
        concept = f"the main ideas of {part} from the textbook \"{book}\"" + (f" ({concept})" if concept and
                                                                               not PAGE_REQUEST.search(concept) else "")
    last_error = ""
    best: LessonPlan | None = None
    for attempt in range(3):
        try:
            try:
                raw = _ollama_chat(concept, last_error, level, duration_s, reference, on_progress, wps, series)
            except requests.RequestException as e:
                raise RuntimeError(
                    f"Cannot reach Ollama at {config.OLLAMA_URL} with model '{config.OLLAMA_MODEL}'. "
                    f"Start it with `ollama serve` and `ollama pull {config.OLLAMA_MODEL}`. ({e})"
                ) from e
            plan = normalize(LessonPlan.model_validate_json(raw))
        except (ValidationError, ValueError, json.JSONDecodeError) as e:
            last_error = f"invalid JSON: {str(e)[:400]}"
            log.warning("Plan attempt %d invalid: %s", attempt + 1, last_error)
            continue
        issue = quality_issue(plan)
        if not issue:
            return plan, sources
        log.info("Plan attempt %d needs work: %s", attempt + 1, issue)
        if best is None or _words(best) < _words(plan):
            best = plan
        last_error = issue
    if best:
        return best, sources          # imperfect but usable beats the generic fallback
    log.error("LLM never produced a valid plan; using fallback plan")
    return normalize(fallback_plan(concept)), sources


def _words(plan: LessonPlan) -> int:
    return sum(len(s.narration.split()) for s in plan.scenes)


def quality_issue(plan: LessonPlan, duration_s: int = 60, wps: float = 2.3) -> str | None:
    """Cheap checks for the ways small models write weak lessons. Returns feedback for a retry.
    Narration length is NOT checked here: the writer agent in review.py lengthens short scenes."""
    if len(plan.scenes) < 4:
        return "use 5-7 scenes: a hook, 2-4 teaching scenes, a quiz and a summary"
    lists = [set(i.lower() for i in s.items) for s in plan.scenes if s.template not in ("summary", "quiz") and s.items]
    for a in range(len(lists)):
        for b in range(a + 1, len(lists)):
            if lists[a] and len(lists[a] & lists[b]) >= max(2, len(lists[a]) // 2):
                return "two scenes repeat the same items; each scene must teach something different"
    return None


def _reference_block(passages: list[Passage], budget: int = 4000) -> str:
    """Retrieved passages, most relevant first, within a character budget."""
    parts, used = [], 0
    for i, p in enumerate(passages, 1):
        head = p.title + (f" ({p.section})" if p.section else "")
        piece = f"[{i}] {head}: {p.text}"
        if used + len(piece) > budget:
            break
        parts.append(piece)
        used += len(piece)
    return "\n\n".join(parts)


def _condensed_block(passages: list[Passage], budget: int = 9000) -> str:
    """A whole chapter can be 80 passages (~50k characters). Keep reading order and coverage:
    sample evenly if there are too many, then trim each passage at a sentence boundary."""
    per_min = 280
    if len(passages) * per_min > budget:
        n = budget // per_min
        step = len(passages) / n
        passages = [passages[int(i * step)] for i in range(n)]
    per = max(per_min, budget // max(len(passages), 1))
    parts = []
    for p in passages:
        text = p.text if len(p.text) <= per else p.text[:per].rsplit(". ", 1)[0] + "."
        parts.append(f"[{p.section or p.title}] {text}")
    return "\n\n".join(parts)


def _sources(passages: list[Passage]) -> list[dict]:
    """One entry per article or PDF, most relevant first. PDF entries get the page span of
    all their retrieved passages, not just the first one's."""
    groups: dict[str, list[Passage]] = {}
    for p in passages:
        groups.setdefault(p.title, []).append(p)
    out = []
    for title, ps in groups.items():
        first = ps[0]
        pages = _page_numbers(ps)
        if pages:
            chapters = {_chapter(p.section) for p in ps}
            chapter = chapters.pop() if len(chapters) == 1 else ""   # don't label a span with one chapter
            section = ", ".join(x for x in (chapter, _span(pages)) if x)
        else:
            section = first.section
        out.append({"title": title, "section": section, "url": first.url, "source": first.source,
                    "score": max(p.score for p in ps)})
    return out


def _page_sources(passages: list[Passage]) -> list[dict]:
    """One source for a page-range lesson: the book, its chapter and the full page span."""
    first = passages[0]
    section = ", ".join(x for x in (_chapter(first.section), _span(_page_numbers(passages))) if x)
    return [{"title": first.title, "section": section, "url": first.url, "source": first.source, "score": 1.0}]


def _page_numbers(passages: list[Passage]) -> list[int]:
    pages: set[int] = set()
    for p in passages:
        if m := re.search(r"#page=(\d+)", p.url):
            pages.add(int(m.group(1)))
        if m := re.search(r"pp?\.\s*(\d+)(?:\s*[–-]\s*(\d+))?", p.section):   # "pp. 214–219" carries the end page
            pages.update(int(x) for x in m.groups() if x)
    return sorted(pages)


def _chapter(section: str) -> str:
    """The section label without its page part: "Ch 3, pp. 214–219" -> "Ch 3"."""
    return re.sub(r",?\s*pp?\.\s*[\d–-]+$", "", section).strip(", ")


def _span(pages: list[int]) -> str:
    if not pages:
        return ""
    return f"p. {pages[0]}" if pages[0] == pages[-1] else f"pp. {pages[0]}–{pages[-1]}"


def _ollama_chat(concept: str, previous_error: str, level: str = "beginner", duration_s: int = 60,
                 context: str = "", on_progress=lambda f: None, wps: float = 2.3, series: dict | None = None) -> str:
    words = round(duration_s * wps / 10) * 10                 # spoken words per second of the slowest chosen language
    scenes = 4 if duration_s <= 40 else 5 if duration_s <= 55 else 6 if duration_s <= 75 else 7
    audience = ("a complete beginner: plain words, one idea per scene, everyday examples" if level == "beginner"
                else "an intermediate learner: assume the basics, add the why and one deeper detail or edge case")
    user = (f"Create a lesson plan that explains: {concept}\n"
            f"Audience: {audience}.\n"
            f"Length: exactly {scenes} scenes and about {words} spoken words in total (about {duration_s} seconds).")
    if series:
        user += (f"\nThis is episode {series['index']} of {series['total']} in the video course \"{series['title']}\" on {series['topic']}."
                 f"\nThis episode teaches only: {series['this']}")
        if series["previous"]:
            user += ("\nEarlier episodes already covered (do NOT repeat them, build on them): " + " | ".join(series["previous"])
                     + "\nThe first scene must connect to the previous episode in one short sentence.")
        if series["next"]:
            user += f"\nThe last scene must end with a one-line teaser for the next episode: {series['next']}."
        else:
            user += "\nThis is the final episode: finish with a recap and one small challenge."
    if context:
        user += ("\nReference material from the knowledge base or the uploaded PDF. Use it for correct facts, numbers and terms, "
                 "but explain in your own simple words. Ignore anything not about the concept:\n" + context)
    if previous_error:
        user += f"\n\nYour previous lesson plan had a problem: {previous_error}. Write a better one."
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
            "options": config.ollama_options({"temperature": 0.4, "num_ctx": 8192 if context else 4096}),
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


def ollama_generate(prompt: str, max_tokens: int = 512) -> str:
    """Plain completion, used by the 'ollama' translation backend."""
    resp = requests.post(
        f"{config.OLLAMA_URL}/api/generate",
        json={"model": config.OLLAMA_MODEL, "prompt": prompt, "stream": False, "keep_alive": "5m",
              "options": config.ollama_options({"temperature": 0.1, "num_predict": max_tokens, "repeat_penalty": 1.15})},
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
