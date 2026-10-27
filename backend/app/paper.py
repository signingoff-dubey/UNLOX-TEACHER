"""Question papers and worksheets, made offline from a lesson (or from your own PDF through it) and printed from the browser.

The local model writes the questions as JSON only (MCQ, short answer, long answer, each with its answer). Everything else is ours: the
marks are fixed per kind (so the total is always right), sections are in order, the answer key is a separate copy, and the page is plain
HTML with print styles and the Noto fonts, so every Indian language prints correctly (use the browser's Print > Save as PDF).
"""
from __future__ import annotations

import html
import json
import logging
import re
import time
import uuid
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from . import config, llm
from .pipeline import load_lesson
from .translate import translate_batch

log = logging.getLogger(__name__)
PAPERS_DIR = config.MEDIA_DIR / "papers"
MARKS = {"mcq": 1, "short": 3, "long": 8}
SECTION = {"mcq": ("A", "Multiple choice", "Choose the correct answer."), "short": ("B", "Short answer", "Answer in two or three sentences."),
           "long": ("C", "Long answer", "Answer in detail. Use examples and steps where they help.")}


class PaperQ(BaseModel):
    kind: Literal["mcq", "short", "long"] = "short"
    question: str = Field("", description="The question, one or two sentences")
    options: list[str] = Field(default_factory=list, description="mcq only: exactly 4 short options")
    answer_index: int = Field(0, description="mcq only: 0-based index of the right option")
    answer: str = Field("", description="short and long: the model answer, or the points a good answer makes")


class PaperDoc(BaseModel):
    title: str = ""
    questions: list[PaperQ] = Field(default_factory=list)


_OPTION_MARK = re.compile(r"^\(?[A-Da-d1-4][\).:]\s+")


def clean(doc: PaperDoc, counts: dict[str, int]) -> list[PaperQ]:
    """Keeps only usable questions, in section order, never more than asked for."""
    out: list[PaperQ] = []
    for kind in ("mcq", "short", "long"):
        mine = []
        for q in doc.questions:
            q.question = " ".join(q.question.split())
            if q.kind != kind or len(q.question) < 8:
                continue
            if kind == "mcq":
                q.options = [_OPTION_MARK.sub("", " ".join(o.split())) for o in q.options if o.strip()][:4]      # the page numbers them itself
                if len(q.options) != 4 or len(set(q.options)) != 4 or not 0 <= q.answer_index < 4:
                    continue
            else:
                q.options, q.answer_index = [], 0
                q.answer = " ".join(q.answer.split())
            mine.append(q)
        out += mine[:counts.get(kind, 0)]
    return out


def source_text(lesson_id: str, limit: int = 5500) -> tuple[str, str]:
    """(title, the lesson's facts as text): what each scene says, plus the passages of the PDF it was made from."""
    lesson = load_lesson(lesson_id)
    plan = lesson.get("plan") or {}
    lines = [f"Topic: {lesson.get('concept', '')}"]
    for s in plan.get("scenes", []):
        lines.append(f"- {s.get('heading', '')}: {s.get('narration', '')}")
        if s.get("items"):
            lines.append("  Points: " + "; ".join(s["items"]))
    try:
        from .knowledge import retrieve
        upload = (lesson.get("documents") or [lesson.get("upload")])[0]
        for p in retrieve(lesson.get("concept", ""), upload=upload)[:4]:
            lines.append(f"Reference ({p.title}): {p.text}")
    except Exception as e:  # noqa: BLE001  the lesson alone is enough
        log.info("no reference passages for the paper: %s", e)
    return lesson.get("concept", "Paper"), "\n".join(lines)[:limit]


def _mock(text: str, counts: dict[str, int]) -> PaperDoc:
    facts = [ln[2:].split(": ", 1) for ln in text.splitlines() if ln.startswith("- ") and ": " in ln]
    qs = []
    for i in range(counts.get("mcq", 0)):
        h, n = facts[i % len(facts)] if facts else ("the topic", "It is explained in the lesson.")
        qs.append(PaperQ(kind="mcq", question=f"Which statement is about {h}?", options=[n[:60] or "A", "None of these", "All of these", "Not given"], answer_index=0))
    for kind in ("short", "long"):
        for i in range(counts.get(kind, 0)):
            h, n = facts[i % len(facts)] if facts else ("the topic", "It is explained in the lesson.")
            qs.append(PaperQ(kind=kind, question=f"Explain {h} in your own words.", answer=n))
    return PaperDoc(title="Practice paper", questions=qs)


def generate(lesson_id: str, counts: dict[str, int], level: str = "beginner", lang: str = "en", title: str = "", progress=lambda s, p: None) -> dict:
    """Writes the paper and saves it. `counts` is how many of each kind: {"mcq": 10, "short": 5, "long": 2}."""
    counts = {k: max(0, min(int(counts.get(k, 0)), 25)) for k in MARKS}
    if not sum(counts.values()):
        raise ValueError("Ask for at least one question")
    topic, text = source_text(lesson_id)
    progress("Writing the questions", 0.1)
    if config.LLM_BACKEND == "mock":
        doc = _mock(text, counts)
    else:
        ask = (f"Write a question paper on this topic for a {'beginner' if level == 'beginner' else 'intermediate'} student, using only the facts below.\n"
               f"Exactly {counts['mcq']} multiple-choice questions (kind \"mcq\", 4 options, answer_index), {counts['short']} short-answer questions (kind \"short\", with the answer) "
               f"and {counts['long']} long-answer questions (kind \"long\", with the points a good answer makes). Each question tests a different fact. No trick questions.\n\n{text}")
        doc = llm.ask_json(PaperDoc, ask, options={"temperature": 0.4, "num_predict": 1800}, timeout=300, expected_tokens=150 * sum(counts.values()),
                           on_progress=lambda f: progress("Writing the questions", 0.1 + 0.6 * f))
    qs = clean(doc, counts)
    if not qs:
        raise ValueError("The model did not write usable questions. Try again.")
    paper_title = title.strip() or (f"{doc.title.strip()}" if doc.title.strip() else f"{topic}: practice paper")
    # texts to translate, in a fixed order
    strings = [paper_title] + [x for q in qs for x in [q.question, q.answer, *q.options]]
    if lang != "en":
        progress("Translating the paper", 0.75)
        strings, _ = translate_batch(strings, lang)
    it = iter(strings)
    title_t = next(it)
    items = []
    for q in qs:
        d = {"kind": q.kind, "marks": MARKS[q.kind], "question": next(it), "answer": next(it), "options": [next(it) for _ in q.options], "answer_index": q.answer_index}
        items.append(d)
    paper = {"id": uuid.uuid4().hex[:10], "lesson_id": lesson_id, "lang": lang, "title": title_t, "created": int(time.time()), "topic": topic, "questions": items,
             "total_marks": sum(d["marks"] for d in items), "counts": {k: sum(1 for d in items if d["kind"] == k) for k in MARKS}}
    PAPERS_DIR.mkdir(parents=True, exist_ok=True)
    (PAPERS_DIR / f"{paper['id']}.json").write_text(json.dumps(paper, ensure_ascii=False, indent=1), encoding="utf-8")
    progress("Ready", 1.0)
    return paper


def load(paper_id: str) -> dict:
    if not paper_id.isalnum():
        raise ValueError("bad paper id")
    return json.loads((PAPERS_DIR / f"{paper_id}.json").read_text(encoding="utf-8"))


# ------------------------------------------------------------------ the printable page
def render_html(paper: dict, key: bool = False) -> str:
    """The paper as one printable HTML page. `key=True` is the teacher's copy: the right options marked and every answer written out."""
    e = html.escape
    parts: list[str] = []
    n = 0
    for kind in ("mcq", "short", "long"):
        qs = [q for q in paper["questions"] if q["kind"] == kind]
        if not qs:
            continue
        letter, name, how = SECTION[kind]
        parts.append(f'<section><h2>Section {letter}: {name} <small>({len(qs)} × {MARKS[kind]} = {len(qs) * MARKS[kind]} marks)</small></h2><p class="how">{how}</p>')
        for q in qs:
            n += 1
            block = f'<div class="q"><div class="qt"><b>{n}.</b> {e(q["question"])} <span class="m">[{q["marks"]}]</span></div>'
            if kind == "mcq":
                block += '<ol type="A" class="opts">' + "".join(
                    f'<li class="{"ok" if key and i == q["answer_index"] else ""}">{e(o)}</li>' for i, o in enumerate(q["options"])) + "</ol>"
            else:
                block += '<div class="lines">' + ('<i></i>' * (4 if kind == "short" else 12)) + "</div>"
            if key:
                block += f'<div class="ans"><b>Answer:</b> {e(q["options"][q["answer_index"]] if kind == "mcq" else q["answer"])}</div>'
            parts.append(block + "</div>")
        parts.append("</section>")
    copy = "Teacher's copy with answers" if key else "Student's copy"
    return f"""<!doctype html><html lang="{e(paper.get('lang', 'en'))}"><head><meta charset="utf-8"><title>{e(paper['title'])}</title>
<style>
@font-face{{font-family:"Noto Sans";src:url(/fonts/NotoSans.ttf);font-weight:100 900}}
@font-face{{font-family:"Noto Sans Devanagari";src:url(/fonts/NotoSansDevanagari.ttf);font-weight:100 900}}
@font-face{{font-family:"Noto Sans Telugu";src:url(/fonts/NotoSansTelugu.ttf);font-weight:100 900}}
@font-face{{font-family:"Noto Sans Kannada";src:url(/fonts/NotoSansKannada.ttf);font-weight:100 900}}
@font-face{{font-family:"Noto Sans Tamil";src:url(/fonts/NotoSansTamil.ttf);font-weight:100 900}}
@font-face{{font-family:"Noto Sans Malayalam";src:url(/fonts/NotoSansMalayalam.ttf);font-weight:100 900}}
@font-face{{font-family:"Noto Sans Bengali";src:url(/fonts/NotoSansBengali.ttf);font-weight:100 900}}
@font-face{{font-family:"Noto Sans Gujarati";src:url(/fonts/NotoSansGujarati.ttf);font-weight:100 900}}
body{{margin:0;color:#111;font:13pt/1.5 "Noto Sans","Noto Sans Devanagari","Noto Sans Telugu","Noto Sans Kannada","Noto Sans Tamil","Noto Sans Malayalam","Noto Sans Bengali","Noto Sans Gujarati","Nirmala UI",sans-serif}}
main{{max-width:780px;margin:0 auto;padding:24px}}h1{{font-size:20pt;margin:0 0 4px}}h2{{font-size:14pt;border-bottom:2px solid #111;padding-bottom:4px;margin:26px 0 4px}}h2 small{{font-weight:400;color:#444}}
.meta{{display:flex;justify-content:space-between;gap:20px;margin:10px 0;color:#333}}.meta span{{flex:1;border-bottom:1px solid #777;padding-bottom:2px}}
.how{{color:#555;margin:2px 0 10px}}.q{{margin:12px 0;break-inside:avoid}}.m{{float:right;color:#555}}.opts{{margin:4px 0 0;padding-left:30px}}.opts li{{margin:2px 0}}
.opts li.ok{{font-weight:700;text-decoration:underline}}.lines i{{display:block;border-bottom:1px solid #aaa;height:26px}}.ans{{margin-top:6px;padding:6px 10px;background:#eef6ee;border-left:4px solid #2f8335}}
.copy{{color:#777;font-size:10pt}}button{{position:fixed;right:16px;top:16px;padding:10px 16px;border:0;border-radius:99px;background:#111;color:#fff;font:600 13px system-ui;cursor:pointer}}
@media print{{button{{display:none}}main{{padding:0}}@page{{margin:16mm}}}}
</style></head><body><button onclick="window.print()">Print or save as PDF</button><main>
<h1>{e(paper['title'])}</h1><div class="copy">{copy} · {paper['total_marks']} marks</div>
<div class="meta"><span>Name:</span><span>Class:</span><span>Date:</span><span>Marks:       / {paper['total_marks']}</span></div>
{''.join(parts)}</main></body></html>"""
