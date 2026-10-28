"""Concept -> LessonPlan, using a local LLM through Ollama with a JSON schema."""
from __future__ import annotations

import json
import logging
import re

import requests
from pydantic import ValidationError

from . import config, content, llm, memory
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


# The prompt above is written for every subject. Most lessons are neither maths nor programming, and then three quarters of it (the graph and
# code templates, their examples and rules, and their fields in the schema) is prompt the model has to read for nothing: it is read again
# for every part of a long video and every episode of a course, and a longer prompt also means a later first scene. system_prompt() leaves
# out what the topic cannot use. The text is carved out of SYSTEM_PROMPT, so there is still one place to edit the wording.
_FULL = SYSTEM_PROMPT


def _between(a: str, b: str | None) -> str:
    i = _FULL.index(a)
    return _FULL[i:_FULL.index(b, i)] if b else _FULL[i:]


_HEAD = _FULL[:_FULL.index("- graph:")]
_GRAPH_T = _between("- graph:", "- code:")
_CODE_T = _between("- code:", "\nChoose the scenes by subject:")
_MATH_S = _between("- MATHS", "- PROGRAMMING")
_CODE_S = _between("- PROGRAMMING", "- REQUIRED:")
_REQ_MATH, _REQ_CODE = _between("- REQUIRED:", "- Coordinate geometry").split("\n  A programming topic", 1)
_REQ_CODE = "- REQUIRED: a programming topic" + _REQ_CODE
_GEOM = _between("- Coordinate geometry", "- VARIETY")
_VARIETY = _between("- VARIETY", "Example graph scene:")
_EX_GRAPH = _between("Example graph scene:", "Example code scene:")
_EX_CODE = _between("Example code scene:", "Rules:")
_RULES = _between("Rules:", None)

MATH_WORDS = re.compile(r"\b(maths?|mathematics|algebra|geometry|graphs?|plot\w*|functions?|circles?|parabolas?|lines?|equations?|trigonometry|sine|cosine|"
                        r"quadratic|cubic|calculus|derivatives?|integrals?|exponential|physics|motion|velocity|slope|curves?|coordinates?|ellipse|angles?|"
                        r"triangles?|statistics|probability|sqrt|logarithm\w*)\b", re.I)
CODE_WORDS = re.compile(r"\b(python|java|javascript|typescript|rust|golang|go lang|c\+\+|c#|sql|react|jsx|html|css|node|code|coding|programming?|"
                        r"loops?|arrays?|algorithms?|recursion|variables?|syntax|api|database|git|linux|bash|shell|compilers?|classes|objects?|pointers?|dsa|"
                        r"data structures?|avl|bst|binary (search )?trees?|linked lists?|stacks?|queues?|heaps?|hash ?(maps?|tables?)|sorting|searching|big-?o|"
                        r"graph algorithms?|dijkstra|bfs|dfs|mern|mean stack|oop|oops|dbms)\b", re.I)
NET_WORDS = re.compile(r"\b(trees?|avl|bst|graphs? (theory|algorithms?)|linked lists?|networks?|hierarch\w+|architecture|pipeline|flowcharts?|mind ?maps?|"
                       r"org(anisation|anization)? chart|family tree|heaps?|tries?|dijkstra|bfs|dfs|stack|mern|mean stack|osi|tcp|internet|food (web|chain))\b", re.I)
LANGS = {"python": "python", "java": "java", "javascript": "javascript", "js": "javascript", "typescript": "typescript", "c++": "cpp", "cpp": "cpp", "c#": "csharp",
         "rust": "rust", "go": "go", "golang": "go", "sql": "sql", "kotlin": "kotlin", "react": "jsx", "html": "html", "bash": "bash", "c": "c"}
SUBJECT_DROP = {"graph": frozenset({"curves", "marks", "equation", "x_range", "y_range"}),
                "code": frozenset({"code_lang", "code", "highlights", "output"}),
                "net": frozenset({"nodes", "edges", "positions"})}


def network_subject(concept: str) -> bool:
    """Trees, linked structures, pipelines and hierarchies are drawn as boxes and arrows (the network template). An unknown subject keeps it."""
    c = (concept or "").strip()
    return True if (not c or len(c) > 120) else bool(NET_WORDS.search(c))


def language_of(concept: str) -> str:
    """The programming language the learner named ("... in C language", "python loops"), or "" when none is named."""
    low = (concept or "").lower()
    for word in sorted(LANGS, key=len, reverse=True):
        if re.search(r"(?<![\w+#])" + re.escape(word) + r"(?![\w+#])" + (r"(?:\s+(?:language|programming))?" if word == "c" else ""), low):
            if word == "c" and not re.search(r"\bin c\b|\bc (language|programming|code)\b|\busing c\b", low):
                continue                                          # a lone "c" is not a language unless it is used like one
            if word == "go" and not re.search(r"\bgolang\b|\bgo (language|programming)\b|\bin go\b", low):
                continue
            return LANGS[word]
    return ""


def subject_of(concept: str) -> tuple[bool, bool]:
    """(needs graph scenes, needs code scenes). An unknown subject (a whole PDF, a photo) keeps both."""
    c = (concept or "").strip()
    if not c or len(c) > 120:
        return True, True
    return bool(MATH_WORDS.search(c)), bool(CODE_WORDS.search(c))


_NET_T = ("- network: heading, narration, nodes (3-8 short labels, max 4 words), edges (arrows {\"src\":i,\"dst\":j} using positions in nodes; src is the parent or the start), "
          "items (optional). The boxes are placed for you: never write positions. Use it to DRAW trees, linked structures, hierarchies, pipelines and architectures.\n")
_NET_S = ("- TREES, LINKED STRUCTURES, HIERARCHIES, ARCHITECTURES, PIPELINES: draw them with a \"network\" scene (nodes and edges), one per key shape "
          "(for example a tree before and after a rotation), not with bullets. The narration walks through the nodes in order.\n")
_EX_NET = ('Example network scene: {{"template":"network","heading":"A right-heavy chain","narration":"Insert ten, then twenty, then thirty. Each new key goes to the right of the last, '
           'so the tree leans into a line.","nodes":["10","20","30"],"edges":[{{"src":0,"dst":1}},{{"src":1,"dst":2}}],"items":[]}}\n')


def system_prompt(concept: str = "") -> tuple[str, frozenset[str]]:
    """The system prompt for this concept and the schema fields to leave out of the example."""
    math, code = subject_of(concept)
    net = network_subject(concept)
    parts = [_HEAD]
    if math:
        parts.append(_GRAPH_T)
    if code:
        parts.append(_CODE_T)
    if net:
        parts.append(_NET_T)
    parts.append("\n\nChoose the scenes by subject:\n")
    if math:
        parts += [_MATH_S, _REQ_MATH.rstrip("\n") + "\n", _GEOM]
    if code:
        parts += [_CODE_S, _REQ_CODE.rstrip("\n") + "\n"]
    if net:
        parts.append(_NET_S)
    variety = _VARIETY
    if not math:
        variety = variety.replace("graph, ", "")
    if not code:
        variety = variety.replace("code, ", "")
    parts.append(variety)
    if math:
        parts.append(_EX_GRAPH)
    if code:
        parts.append(_EX_CODE)
    if net:
        parts.append(_EX_NET)
    rules = _RULES if (math or code) else re.sub(r"^- For code and graph scenes[^\n]*\n", "", _RULES, flags=re.M)         # (that rule is about graph and code scenes only)
    parts.append(rules)
    drop = frozenset().union(*(SUBJECT_DROP[k] for k, need in (("graph", math), ("code", code), ("net", net)) if not need))
    return "".join(parts), drop


PAGE_REQUEST = re.compile(r"\b(chapter|ch\.?|unit|lesson|section|page|pages|pp?\.)\s*\d", re.I)


MODE_HINTS = {
    "revise": ("This is a revision lesson for a learner who keeps getting some things wrong. Re-teach those ideas from a different angle, "
               "with a fresh example, and end with a quiz scene that checks them again."),
    "study": ("This is for studying and revising: name the key terms, give one memory trick or mnemonic, and end with a quiz scene "
              "that tests recall of the most important facts."),
    "homework": ("The student must finish a homework on this. Teach only the concepts needed to solve it, with one worked example in "
                 "the style of the homework. Do NOT give the answers to the homework questions."),
}


def plan_lesson(concept: str, level: str = "beginner", duration_s: int = 60, upload: str | None = None, focus: str = "",
                on_progress=lambda f: None, wps: float = 2.3, series: dict | None = None,
                extra: str = "", mode: str = "explain", on_text=None) -> tuple[LessonPlan, list[dict]]:
    """Returns the lesson plan and the sources it was grounded in. `on_text` hears the plan's JSON as it is written (see streaming.py).

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
        passages = retrieve(concept or focus or extra[:200], upload=upload)
    sources = _page_sources(passages) if page_mode else _sources(passages)
    reference = _condensed_block(passages) if page_mode else _reference_block(passages, budget=2400 if duration_s <= 75 else 3600)      # less to read, an earlier first scene
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
                raw = _ollama_chat(concept, last_error, level, duration_s, reference, on_progress, wps, series, extra, mode, on_text)
            except requests.RequestException as e:
                raise RuntimeError(
                    f"Cannot reach Ollama at {config.OLLAMA_URL} with model '{config.OLLAMA_MODEL}'. "
                    f"Start it with `ollama serve` and `ollama pull {config.OLLAMA_MODEL}`. ({e})"
                ) from e
            seg = bool(series and series.get("segment"))
            plan = normalize(LessonPlan.model_validate_json(llm.extract_json(raw)), segment=seg, last=seg and not series.get("next"), title=(series["index"] == 1) if seg else None)
            if seg:
                for n in content.clean_part(plan, series["index"], series["total"]):
                    log.info("planner: %s", n)
        except (ValidationError, ValueError, json.JSONDecodeError) as e:
            last_error = f"invalid JSON: {str(e)[:400]}"
            log.warning("Plan attempt %d invalid: %s", attempt + 1, last_error)
            continue
        issue = quality_issue(plan, min_scenes=2 if (series and series.get('segment')) else 4, questions=None if series else content.sub_questions(concept),
                              technical=any(subject_of(concept)))
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


def quality_issue(plan: LessonPlan, duration_s: int = 60, wps: float = 2.3, min_scenes: int = 4, questions: list[str] | None = None, technical: bool = False) -> str | None:
    """Cheap checks for the ways small models write weak lessons. Returns feedback for a retry.
    Narration length is NOT checked here: the writer agent in review.py lengthens short scenes."""
    if len(plan.scenes) < min_scenes:
        return "use 5-7 scenes: a hook, 2-4 teaching scenes, a quiz and a summary" if min_scenes >= 4 else f"write at least {min_scenes} scenes"
    lists = [set(i.lower() for i in s.items) for s in plan.scenes if s.template not in ("summary", "quiz") and s.items]
    for a in range(len(lists)):
        for b in range(a + 1, len(lists)):
            if lists[a] and len(lists[a] & lists[b]) >= max(2, len(lists[a]) // 2):
                return "two scenes repeat the same items; each scene must teach something different"
    issue = content.schema_echo(plan) or content.repeated_headings(plan) or content.repeated_code(plan) or content.quiz_problem(plan)
    if issue:
        return issue
    if technical and len(plan.scenes) >= 5 and all(s.template in ("title", "bullets", "flow", "compare", "summary", "quiz", "cycle") for s in plan.scenes):
        return "this is a technical topic: show it, with a code scene, a network (boxes and arrows) scene or a graph scene, not only text scenes"
    if content.analogy_overload(plan):
        return "too many scenes rely on a comparison to an everyday object (a book, a cake, a seesaw): explain with the real terms, real numbers and one precise example instead"
    missed = content.unanswered(plan, questions or [])
    if missed:
        return f"the lesson does not answer the learner's question: '{missed}'. Give it its own scene(s) with the real explanation"
    short = content.narration_problems(plan)
    if len(short) >= max(2, len(plan.scenes) // 3):
        return "the narration is too short: write 2-3 full sentences (about 25 words) in every scene that explain the idea, never a placeholder like 'Let's learn about'"
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
                 context: str = "", on_progress=lambda f: None, wps: float = 2.3, series: dict | None = None,
                 extra: str = "", mode: str = "explain", on_text=None) -> str:
    words = round(duration_s * wps / 10) * 10                 # spoken words per second of the slowest chosen language
    scenes = 4 if duration_s <= 40 else 5 if duration_s <= 55 else 6 if duration_s <= 75 else 7
    technical = any(subject_of(concept))
    audience = ("a complete beginner: plain words, one idea per scene, everyday examples" if level == "beginner"
                else "an intermediate learner: assume the basics, add the why and one deeper detail or edge case")
    from .learner import age_hint
    if age_hint():
        audience = f"{audience}. {age_hint()}"
    user = (f"Create a lesson plan that explains: {concept}\n"
            f"Audience: {audience}.\n"
            f"Length: exactly {scenes} scenes and about {words} spoken words in total (about {duration_s} seconds).")
    if series and series.get("segment"):
        # One part of ONE continuous video: it must flow on from the part before and into the part after.
        scenes = series.get("scenes") or max(3, min(6, round(duration_s / 10)))              # a part of 40-80 s: 4-6 scenes of about 25 words (3 parts at most); Pro says how many
        user = (f"Create part {series['index']} of {series['total']} of ONE continuous video titled \"{series['title']}\" about {series['topic']}.\n"
                f"Audience: {audience}.\n"
                f"This part teaches only: {series['this']}\n"
                f"Length: exactly {scenes} scenes and about {words} spoken words in total (about {duration_s} seconds).")
        if series.get("beats"):
            user += "\nThe whole video was outlined first. Write exactly one scene for each beat of THIS part, in this order, keeping its heading and template:\n" + series["beats"]
        if series["previous"]:
            user += ("\nAlready covered in earlier parts (do NOT repeat, build on it): " + " | ".join(series["previous"][-4:])
                     + "\nDo NOT start with a title scene and do not greet or say welcome: continue straight on; the first scene links to what was just taught in a few words.")
        else:
            user += "\nThe first scene is a title scene that hooks the student with a question or a surprising fact."
        if series["next"]:
            user += f"\nNo quiz scene and no summary scene in this part. The last scene ends with one sentence that leads into: {series['next']}."
        else:
            user += "\nThis is the last part: it ends with a quiz scene and then a summary scene."
    elif series:
        user += (f"\nThis is episode {series['index']} of {series['total']} in the video course \"{series['title']}\" on {series['topic']}."
                 f"\nThis episode teaches only: {series['this']}")
        if series["previous"]:
            user += ("\nEarlier episodes already covered (do NOT repeat them, build on them): " + " | ".join(series["previous"])
                     + "\nThe first scene must connect to the previous episode in one short sentence.")
        if series["next"]:
            user += f"\nThe last scene must end with a one-line teaser for the next episode: {series['next']}."
        else:
            user += "\nThis is the final episode: finish with a recap and one small challenge."
    if MODE_HINTS.get(mode):
        user += "\n" + MODE_HINTS[mode]
    if mode == "revise":
        from .srs import weak_focus
        user += "\n" + (weak_focus() or "No weak spots are recorded yet, so revise the main ideas of the concept.")
    # What makes the content good, in as few words as possible: a student should learn something new from every scene.
    user += ("\nQuality bar: every scene adds NEW information, with specific facts, real numbers and one concrete example (never vague phrases such as "
             "'it helps a lot'); the narration is 2-3 full sentences of about 25 words that explain, not just announce the heading; never repeat a heading, "
             "an example, a point or a piece of code that was already shown. Define every technical term the first time it is used. "
             + ("This is a technical topic: use the precise terms and real values, and show it with code, a network (boxes and arrows) or a graph scene. "
                "Use an everyday comparison only if it is exact and at most once in the whole video; never build the video around an object such as a book, a cake or a seesaw. "
                if technical else "Use an everyday comparison only when it is exact, and at most twice in the whole video. ")
             + "Every fact must be true: if you are not sure of a detail, leave it out.")
    lang = language_of(concept)
    if lang and subject_of(concept)[1]:
        user += f"\nThe learner asked for {lang}: every code scene uses code_lang \"{lang}\" and valid {lang} syntax."
    elif subject_of(concept)[1] and not subject_of(concept)[0]:
        user += "\nNo programming language was named: use Python for the code scenes (code_lang \"python\")."
    if series and series.get("segment") and series.get("library"):
        user += "\n" + series["library"]
    elif not series:
        seen_before = memory.context(concept)                    # what the learner already has on this subject
        if seen_before:
            user += "\n" + seen_before
    if subject_of(concept)[1]:
        user += ("\nProgramming: build up in small steps: a minimal snippet, then the same idea with a variation or traced with real values, then the pitfall "
                 "or the cost. Every code scene shows DIFFERENT code that builds on the one before. Show only the lines that matter: never repeat a class or "
                 "main() skeleton. The code is correct, runnable and uses meaningful names.")
    asked = content.sub_questions(concept) if not series else []
    if asked:
        user += "\nThe learner asked " + str(len(asked)) + " questions. Answer every one of them, in this order, each with its own scene(s) and the real explanation: " + " ".join(f"({i}) {q}?" for i, q in enumerate(asked, 1))
    if series and series.get("taught"):
        user += "\nAlready taught in earlier parts or videos (do NOT repeat these headings, points, examples or code; build on them and go further):\n" + series["taught"]
    if duration_s >= 45 and not (series and series.get("segment") and series.get("next")):
        user += ("\nAlso fill common_mistakes with one or two beliefs students often get wrong about this concept, each with the correct fact "
                 "(wrong: at most 14 words, right: at most 14 words). Leave it empty if there are none.")
    if extra:
        user += ("\nThe student attached a photo or a document. This is what a computer read from it (it may contain mistakes, and it may be only a list of "
                 "topics): treat it as the student's own notes or question. Use what is relevant to THIS lesson to decide what to teach and which examples to use, "
                 "but never copy it as a list and never mention it in the narration:\n" + extra)
    if context:
        user += ("\nReference material from the knowledge base or the uploaded PDF. Use it for correct facts, numbers and terms, "
                 "but explain in your own simple words. Ignore anything not about the concept:\n" + context)
    if previous_error:
        user += f"\n\nYour previous lesson plan had a problem: {previous_error}. Write a better one."
    # No Ollama `format`: constrained decoding made this call 2-4x slower (see llm.py). The schema goes in the prompt instead.
    return llm.stream_chat(
        [{"role": "system", "content": llm.with_schema(*(lambda sp: (sp[0], LessonPlan, sp[1]))(system_prompt(concept)))}, {"role": "user", "content": user}],
        {"temperature": 0.4}, expected_tokens=max(350, duration_s * 12), on_progress=on_progress, on_text=on_text)


def scene_target(duration_s: int) -> int:
    """About how many scenes a lesson of this length has (the planner is asked for this many)."""
    return 4 if duration_s <= 40 else 5 if duration_s <= 55 else 6 if duration_s <= 75 else 7



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
