"""Study tools made from a lesson (flashcards, quiz, mind map, study guide, FAQ, glossary, timeline).

Modelled on NotebookLM's Studio panel: each tool is generated from the lesson itself (its English plan, plus passages from
the PDF it was made from), with a size and a difficulty the learner can change, and the result is cached per lesson.
The local LLM returns DATA ONLY (JSON that matches a schema, never code); the app draws it. Text is translated to the
lesson language afterwards with the same translator as the lessons.
"""
from __future__ import annotations

import heapq
import itertools
import json
import logging
import random
import re
import threading
from typing import Any, Callable

import requests
from pydantic import BaseModel, Field, ValidationError

from . import config, jobs
from .knowledge import retrieve
from .pipeline import LESSONS_DIR, load_lesson
from .translate import translate_batch

log = logging.getLogger(__name__)

KINDS = ("flashcards", "quiz", "mindmap", "studyguide", "faq", "glossary", "timeline")
Progress = Callable[[str, float], None]


# ------------------------------------------------------------------ schemas (what the model may return)
class Card(BaseModel):
    front: str = Field(description="A question or prompt, max 14 words")
    back: str = Field(description="The answer, max 30 words")


class Flashcards(BaseModel):
    cards: list[Card]


class Question(BaseModel):
    question: str
    options: list[str] = Field(description="Exactly 4 short options; one is correct")
    answer_index: int = Field(description="0-based index of the correct option")
    explanation: str = Field(description="One or two sentences: why that option is right")


class Quiz(BaseModel):
    questions: list[Question]


class MindMap(BaseModel):
    code: str = Field(description=(
        "A Mermaid mindmap, as plain text. First line: mindmap. Second line: the central topic, indented 2 spaces. Then 4-6 main ideas "
        "indented 4 spaces, each with 2-4 sub-ideas indented 6 spaces, and optional tiny notes indented 8 spaces. Short labels only "
        "(max 6 words), no punctuation, no brackets, no quotes, no icons or classes."))


# ---- Mermaid mindmap: the model types diagram text, we parse it into a tree and write it back out ourselves.
# What reaches the browser is therefore always our own clean output: no directives, links, callbacks or HTML.
_BAD = str.maketrans({c: " " for c in "()[]{}\"'`;:#<>&\\|%*_@!$^~=+/"})


def _label(text: str) -> str:
    return " ".join(text.translate(_BAD).split())[:44]


def parse_mindmap(code: str) -> dict:
    """Mermaid mindmap text -> {"root", "branches": [{label, children: [{label, details}]}]}. Raises ValueError if unusable."""
    rows: list[tuple[int, str]] = []
    for raw in code.replace("\t", "    ").splitlines():
        if not raw.strip() or raw.strip().lower() == "mindmap" or raw.strip().startswith(("%%", "::icon", ":::")):
            continue
        text = re.sub(r"^\w{0,12}(?=[(\[{])", "", raw.strip())          # "root((Topic))" / "id[Topic]" -> the bracketed label
        label = _label(text)
        if label:
            rows.append((len(raw) - len(raw.lstrip()), label))
    if len(rows) < 3:
        raise ValueError("mind map too small")
    root_indent, root = rows[0]
    stack = [(root_indent, 0)]                       # (indent, depth); the first row is the centre
    tree: list[tuple[int, str]] = []                 # (depth, label) below the centre
    for indent, label in rows[1:]:
        while len(stack) > 1 and indent <= stack[-1][0]:
            stack.pop()
        depth = stack[-1][1] + 1
        stack.append((indent, depth))
        tree.append((min(depth, 3), label))
    branches: list[dict] = []
    for depth, label in tree:
        if depth == 1:
            branches.append({"label": label, "children": []})
        elif branches and depth == 2:
            branches[-1]["children"].append({"label": label, "details": []})
        elif branches and branches[-1]["children"] and depth == 3:
            branches[-1]["children"][-1]["details"].append(label)
    branches = [b for b in branches if b["children"]][:6]
    for b in branches:
        b["children"] = b["children"][:4]
        for c in b["children"]:
            c["details"] = c["details"][:3]
    if len(branches) < 2:
        raise ValueError("mind map needs at least two branches")
    return {"root": root, "branches": branches}


def to_mermaid(tree: dict) -> str:
    """Canonical Mermaid text for a mind map tree (what the browser renders)."""
    out = ["mindmap", f"  root(({_label(tree['root']) or 'Topic'}))"]
    for b in tree["branches"]:
        out.append(f"    {_label(b['label'])}")
        for c in b["children"]:
            out.append(f"      {_label(c['label'])}")
            out.extend(f"        {_label(d)}" for d in c["details"])
    return "\n".join(out)


class Term(BaseModel):
    term: str
    meaning: str = Field(description="One plain sentence, max 25 words")


class StudyGuide(BaseModel):
    overview: str = Field(description="3-4 sentences: what this lesson is about and why it matters")
    key_points: list[str] = Field(description="5-7 short points, each a full sentence")
    terms: list[Term]
    review_questions: list[str] = Field(description="3-5 short-answer questions for self-testing")


class QA(BaseModel):
    question: str
    answer: str = Field(description="2-3 plain sentences")


class FAQ(BaseModel):
    items: list[QA]


class Glossary(BaseModel):
    terms: list[Term]


class Event(BaseModel):
    label: str = Field(description="Short title of the step or event, max 6 words")
    detail: str = Field(description="One sentence")


class Timeline(BaseModel):
    events: list[Event]


SCHEMAS: dict[str, type[BaseModel]] = {"flashcards": Flashcards, "quiz": Quiz, "mindmap": MindMap, "studyguide": StudyGuide,
                                       "faq": FAQ, "glossary": Glossary, "timeline": Timeline}
SIZES = {"few": 0, "standard": 1, "more": 2}
COUNTS = {"flashcards": (6, 10, 16), "quiz": (4, 6, 10), "faq": (4, 6, 8), "glossary": (6, 8, 12)}
DIFFICULTY = {
    "easy": "Easy: recall of the basic facts and definitions, in the simplest words.",
    "medium": "Medium: check understanding, so ask why and how, not only what.",
    "hard": "Hard: apply the ideas to a new situation or compare them; the wrong options must be tempting.",
}


def _count(kind: str, size: str) -> int:
    return COUNTS[kind][SIZES.get(size, 1)]


def _task(kind: str, size: str, difficulty: str) -> str:
    d = DIFFICULTY.get(difficulty, DIFFICULTY["medium"])
    if kind == "flashcards":
        return (f"Write exactly {_count(kind, size)} flashcards for studying this lesson. Front: a clear question or prompt. Back: the short answer. "
                f"Cover different ideas, no duplicates. {d}")
    if kind == "quiz":
        return (f"Write exactly {_count(kind, size)} multiple-choice questions. Each has exactly 4 options, one correct, plus a one- or two-sentence "
                f"explanation of why it is right. {d}")
    if kind == "mindmap":
        return ("Make a mind map of this lesson as a Mermaid mindmap in the `code` field. Example:\n"
                "mindmap\n  Photosynthesis\n    Inputs\n      Sunlight\n      Water\n    Outputs\n      Glucose\n      Oxygen\n"
                "Use short labels (2-5 words), never sentences.")
    if kind == "studyguide":
        return "Write a study guide: an overview, 5-7 key points, 5-8 important terms with meanings, and 3-5 review questions to test yourself."
    if kind == "faq":
        return f"Write {_count(kind, size)} frequently asked questions a curious student would ask about this topic, each with a short clear answer."
    if kind == "glossary":
        return f"List the {_count(kind, size)} most important terms from this lesson with a one-sentence plain definition each."
    return ("Put the main steps or events of this topic in the order they happen (or in the order you would learn them), 4-8 items, "
            "each with a short label and one sentence.")


# ------------------------------------------------------------------ source text
def lesson_text(lesson: dict) -> str:
    plan = lesson["plan"]
    lines = [f"LESSON: {plan['title']}"]
    for s in plan["scenes"]:
        lines.append(f"- {s['heading']}: {s['narration']}")
        for key in ("items", "left", "right"):
            if s.get(key):
                lines.append("  " + "; ".join(s[key]))
    return "\n".join(lines)


def source_text(lesson: dict) -> str:
    text = lesson_text(lesson)
    upload = (lesson.get("documents") or [lesson.get("upload")])[0]
    try:
        extra = retrieve(lesson.get("concept") or lesson["plan"]["title"], upload=upload)[:4]
    except Exception:  # noqa: BLE001  retrieval is optional
        extra = []
    if extra:
        text += "\n\nSOURCE PASSAGES (facts to rely on):\n" + "\n".join(f"- {p.title}: {p.text[:600]}" for p in extra)
    return text[:6000]


# ------------------------------------------------------------------ generation
# Rough size of each answer in tokens: the model's token stream is the progress bar.
EXPECTED_TOKENS = {"flashcards": 520, "quiz": 760, "mindmap": 260, "studyguide": 640, "faq": 480, "glossary": 420, "timeline": 320}


def _ask(kind: str, lesson: dict, size: str, difficulty: str, on_progress: Callable[[float], None] = lambda f: None) -> dict:
    schema = SCHEMAS[kind]
    system = ("You make study material for a student from the lesson below. Use only the lesson and its source passages: never invent facts. "
              "Write in simple English (it is translated later). Return ONLY JSON that matches the schema.")
    user = f"{source_text(lesson)}\n\nTASK: {_task(kind, size, difficulty)}"
    err = ""
    for attempt in range(2):
        try:
            r = requests.post(f"{config.OLLAMA_URL}/api/chat", json={
                "model": config.OLLAMA_MODEL, "stream": True, "keep_alive": config.OLLAMA_KEEP_ALIVE,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user + (f"\n\nFix this problem: {err}" if err else "")}],
                "format": schema.model_json_schema(),
                "options": config.ollama_options({"temperature": 0.3, "num_ctx": 4096}),
            }, timeout=300, stream=True)
            r.raise_for_status()
            parts, n = [], 0
            for line in r.iter_lines():
                if not line:
                    continue
                chunk = json.loads(line)
                parts.append(chunk.get("message", {}).get("content", ""))
                n += 1
                if n % 5 == 0:
                    on_progress(min(n / EXPECTED_TOKENS[kind], 0.97))
                if chunk.get("done"):
                    break
            on_progress(1.0)
            return clean(kind, schema.model_validate_json("".join(parts)).model_dump(), size)
        except requests.RequestException as e:
            raise RuntimeError(f"Cannot reach Ollama for study tools: {e}") from e
        except (ValidationError, ValueError) as e:
            err = f"invalid JSON ({str(e)[:200]})"
            log.warning("studio %s attempt %d: %s", kind, attempt + 1, err)
    raise RuntimeError("The model could not make that study tool. Try again.")


def _s(v: Any) -> str:
    return " ".join(str(v).split())


def clean(kind: str, data: dict, size: str = "standard") -> dict:
    """Repair what small models get wrong so the UI never has to."""
    if kind == "flashcards":
        seen, cards = set(), []
        for c in data["cards"]:
            front, back = _s(c["front"]), _s(c["back"])
            if front and back and front.lower() not in seen:
                seen.add(front.lower())
                cards.append({"front": front, "back": back})
        data = {"cards": cards[: _count(kind, size)]}
    elif kind == "quiz":
        out = []
        for q in data["questions"]:
            opts = [_s(o) for o in q["options"] if _s(o)]
            opts = list(dict.fromkeys(opts))[:4]
            if len(opts) < 3 or not 0 <= q["answer_index"] < len(q["options"]):
                continue
            right = _s(q["options"][q["answer_index"]])
            if right not in opts:
                continue
            random.Random(_s(q["question"])).shuffle(opts)       # models like to put the answer first
            out.append({"question": _s(q["question"]), "options": opts, "answer_index": opts.index(right),
                        "explanation": _s(q["explanation"])})
        data = {"questions": out[: _count(kind, size)]}
    elif kind == "mindmap":
        data = parse_mindmap(data["code"]) if "code" in data else parse_mindmap(to_mermaid(data))   # a tree is re-cleaned the same way
        data["mermaid"] = to_mermaid(data)
    elif kind == "studyguide":
        data = {"overview": _s(data["overview"]), "key_points": [_s(p) for p in data["key_points"] if _s(p)][:8],
                "terms": [{"term": _s(t["term"]), "meaning": _s(t["meaning"])} for t in data["terms"] if _s(t["term"])][:8],
                "review_questions": [_s(q) for q in data["review_questions"] if _s(q)][:5]}
    elif kind == "faq":
        data = {"items": [{"question": _s(i["question"]), "answer": _s(i["answer"])} for i in data["items"] if _s(i["question"]) and _s(i["answer"])][: _count(kind, size)]}
    elif kind == "glossary":
        data = {"terms": [{"term": _s(t["term"]), "meaning": _s(t["meaning"])} for t in data["terms"] if _s(t["term"]) and _s(t["meaning"])][: _count(kind, size)]}
    else:
        data = {"events": [{"label": _s(e["label"]), "detail": _s(e["detail"])} for e in data["events"] if _s(e["label"])][:8]}
    main = {"flashcards": "cards", "quiz": "questions", "mindmap": "branches", "studyguide": "key_points", "faq": "items",
            "glossary": "terms", "timeline": "events"}[kind]
    if not data[main]:
        raise ValueError("empty result")
    return data


def _mock(kind: str, lesson: dict, size: str) -> dict:
    """No-model output built from the lesson itself, so the whole feature can be tested offline."""
    scenes = [s for s in lesson["plan"]["scenes"] if s["template"] not in ("quiz",)]
    title = lesson["plan"]["title"]
    facts = [(s["heading"], s["narration"]) for s in scenes]
    if kind == "flashcards":
        return {"cards": [{"front": f"What should you know about {h}?", "back": n} for h, n in facts][: _count(kind, size)]}
    if kind == "quiz":
        heads = [h for h, _ in facts]
        qs = []
        for h, n in facts[: _count(kind, size)]:
            wrong = [x for x in heads if x != h][:3]
            if len(wrong) >= 2:
                qs.append({"question": f"Which topic is explained by: \"{n[:80]}\"?", "options": [h, *wrong], "answer_index": 0, "explanation": n})
        return clean("quiz", {"questions": qs}, size)
    if kind == "mindmap":
        return clean("mindmap", {"root": title, "branches": [{"label": h, "children": [{"label": i, "details": []} for i in (s["items"] or [n[:40]])[:3]]}
                                                              for (h, n), s in zip(facts, scenes)][:6]})
    if kind == "studyguide":
        return {"overview": " ".join(n for _, n in facts[:2]), "key_points": [n for _, n in facts][:6],
                "terms": [{"term": h, "meaning": n} for h, n in facts][:5], "review_questions": [f"Explain {h} in your own words." for h, _ in facts][:4]}
    if kind == "faq":
        return {"items": [{"question": f"What is {h}?", "answer": n} for h, n in facts][: _count(kind, size)]}
    if kind == "glossary":
        return {"terms": [{"term": h, "meaning": n} for h, n in facts][: _count(kind, size)]}
    return {"events": [{"label": h, "detail": n} for h, n in facts][:8]}


def _translate(data: Any, lang: str) -> tuple[Any, str]:
    """Translate every string in the structure in one batch, keeping its shape."""
    texts: list[str] = []

    def collect(x: Any) -> None:
        if isinstance(x, str):
            texts.append(x)
        elif isinstance(x, list):
            for i in x:
                collect(i)
        elif isinstance(x, dict):
            for k, v in x.items():
                if k not in ("answer_index",):
                    collect(v)

    collect(data)
    out, engine = translate_batch(texts, lang)
    it = iter(out)

    def rebuild(x: Any) -> Any:
        if isinstance(x, str):
            return next(it)
        if isinstance(x, list):
            return [rebuild(i) for i in x]
        if isinstance(x, dict):
            return {k: (v if k == "answer_index" else rebuild(v)) for k, v in x.items()}
        return x

    return rebuild(data), engine




# ------------------------------------------------------------------ the build queue
# Study tools are made in the background as soon as a video exists (low priority, so lesson generation is never slowed),
# and a tool the learner asks for jumps the queue. One worker: the local model does one thing at a time anyway.
ORDER = ("flashcards", "quiz", "mindmap", "studyguide", "glossary", "faq", "timeline")   # most useful first
DEFAULT_SIZE, DEFAULT_DIFFICULTY = "standard", "medium"
URGENT, BACKGROUND = 0, 5

Key = tuple[str, str, str, str, str]                       # (lesson id, kind, language, size, difficulty)
_state: dict[Key, dict] = {}
_waiters: dict[Key, threading.Event] = {}
_heap: list[tuple[int, int, Key]] = []
_seq = itertools.count()
_cv = threading.Condition()
_worker: threading.Thread | None = None
_prebuilt: set[str] = set()


def _path(lesson_id: str, kind: str, lang: str, size: str, difficulty: str):
    return LESSONS_DIR / lesson_id / f"studio2_{kind}_{lang}_{size}_{difficulty}.json"


def cached(lesson_id: str, kind: str, lang: str, size: str = DEFAULT_SIZE, difficulty: str = DEFAULT_DIFFICULTY) -> dict | None:
    p = _path(lesson_id, kind, lang, size, difficulty)
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
    except (OSError, ValueError):
        return None


def _set(key: Key, **kw: Any) -> None:
    with _cv:
        _state.setdefault(key, {"state": "queued", "progress": 0.0, "stage": "Waiting", "error": None}).update(kw)


def request(lesson_id: str, kind: str, lang: str = "en", size: str = DEFAULT_SIZE, difficulty: str = DEFAULT_DIFFICULTY,
            priority: int = URGENT) -> dict:
    """Ask for a tool. Already made: ready at once. Being made or waiting: it is moved up if the new request is more urgent."""
    if kind not in KINDS:
        raise ValueError(f"Unknown study tool '{kind}'")
    key: Key = (lesson_id, kind, lang, size, difficulty)
    if _path(lesson_id, kind, lang, size, difficulty).exists():
        return {"state": "ready", "progress": 1.0, "stage": "Ready", "error": None}
    with _cv:
        cur = _state.get(key)
        if cur and cur["state"] == "building":
            return dict(cur)
        if cur and cur["state"] == "queued" and cur.get("priority", BACKGROUND) <= priority:
            return dict(cur)
        _state[key] = {"state": "queued", "progress": 0.0, "stage": "Waiting its turn", "error": None, "priority": priority}
        _waiters.setdefault(key, threading.Event()).clear()
        heapq.heappush(_heap, (priority, next(_seq), key))
        global _worker
        if _worker is None or not _worker.is_alive():
            _worker = threading.Thread(target=_run, name="studio-queue", daemon=True)
            _worker.start()
        _cv.notify_all()
        return dict(_state[key])


def status(lesson_id: str, lang: str, size: str = DEFAULT_SIZE, difficulty: str = DEFAULT_DIFFICULTY) -> dict[str, dict]:
    out = {}
    for kind in KINDS:
        if _path(lesson_id, kind, lang, size, difficulty).exists():
            out[kind] = {"state": "ready", "progress": 1.0, "stage": "Ready", "error": None}
        else:
            s = _state.get((lesson_id, kind, lang, size, difficulty))
            out[kind] = ({k: s[k] for k in ("state", "progress", "stage", "error")} if s else
                         {"state": "none", "progress": 0.0, "stage": "", "error": None})
    return out


def prebuild(lesson_id: str) -> None:
    """Queue every study tool of a video (English, plus the first non-English language it was made in). Once per video."""
    with _cv:
        if lesson_id in _prebuilt:
            return
        _prebuilt.add(lesson_id)
    try:
        langs = list(load_lesson(lesson_id)["languages"])
    except (OSError, ValueError, KeyError):
        return
    other = next((c for c in langs if c != "en"), None)
    for lang in ["en", other] if other else ["en"]:
        for kind in ORDER:
            request(lesson_id, kind, lang, priority=BACKGROUND + (0 if lang == "en" else 1))


def ensure(lesson_id: str, kind: str, lang: str = "en", size: str = DEFAULT_SIZE, difficulty: str = DEFAULT_DIFFICULTY,
           timeout: float = 900) -> dict:
    """Request (urgently) and wait. Used by jobs that need a tool, such as the Meta quiz."""
    done = cached(lesson_id, kind, lang, size, difficulty)
    if done is not None:
        return done
    request(lesson_id, kind, lang, size, difficulty)
    key: Key = (lesson_id, kind, lang, size, difficulty)
    ev = _waiters.setdefault(key, threading.Event())
    if not ev.wait(timeout) and not _path(lesson_id, kind, lang, size, difficulty).exists():
        raise RuntimeError("Timed out waiting for the study tool")
    res = cached(lesson_id, kind, lang, size, difficulty)
    if res is None:
        raise RuntimeError(_state.get(key, {}).get("error") or "The study tool could not be made")
    return res


def _next() -> Key | None:
    """The most urgent waiting tool. Background work waits while a lesson or course is being made (they share the model)."""
    with _cv:
        while True:
            while _heap:
                prio, _, key = _heap[0]
                s = _state.get(key)
                if not s or s["state"] != "queued" or s.get("priority", BACKGROUND) != prio:
                    heapq.heappop(_heap)                         # stale entry: already built, or re-queued more urgently
                    continue
                if prio >= BACKGROUND and jobs.active("lesson", "playlist"):
                    break
                heapq.heappop(_heap)
                s["state"] = "building"
                return key
            _cv.wait(timeout=2.0)


def _run() -> None:
    while True:
        key = _next()
        if key is None:
            continue
        lesson_id, kind, lang, size, difficulty = key
        try:
            _set(key, stage="Writing it from the lesson", progress=0.02)
            _build(key)
        except Exception as e:  # noqa: BLE001  shown on the button; the learner can click again
            log.warning("study tool %s failed: %s", key, e)
            _set(key, state="error", error=f"{type(e).__name__}: {e}", stage="Failed")
        ev = _waiters.get(key)
        if ev:
            ev.set()


def _build(key: Key) -> None:
    lesson_id, kind, lang, size, difficulty = key
    lesson = load_lesson(lesson_id)
    en_path = _path(lesson_id, kind, "en", size, difficulty)
    if en_path.exists():
        data = json.loads(en_path.read_text(encoding="utf-8"))["data"]
    else:
        scale = 0.9 if lang == "en" else 0.75
        data = (_mock(kind, lesson, size) if config.LLM_BACKEND == "mock" else
                _ask(kind, lesson, size, difficulty, lambda f: _set(key, progress=round(0.02 + f * (scale - 0.02), 3), stage="Writing it from the lesson")))
        en_path.write_text(json.dumps({"kind": kind, "lang": "en", "size": size, "difficulty": difficulty, "translator": "none", "data": data},
                                      ensure_ascii=False, indent=1), encoding="utf-8")
    if lang == "en":
        _set(key, state="ready", progress=1.0, stage="Ready")
        return
    _set(key, progress=0.8, stage="Translating")
    if kind == "mindmap":                                       # translate the labels, then write the Mermaid text again
        out, engine = _translate({k: v for k, v in data.items() if k != "mermaid"}, lang)
        out = clean("mindmap", out)
    else:
        out, engine = _translate(data, lang)
    _path(lesson_id, kind, lang, size, difficulty).write_text(json.dumps(
        {"kind": kind, "lang": lang, "size": size, "difficulty": difficulty, "translator": engine, "data": out}, ensure_ascii=False, indent=1), encoding="utf-8")
    _set(key, state="ready", progress=1.0, stage="Ready")
