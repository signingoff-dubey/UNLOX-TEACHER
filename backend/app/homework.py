"""Homework answers as a Markdown file that is written while you watch.

The student picks "Homework" and attaches the homework as a PDF or a photo. Nothing guesses whether a file is homework:
the choice is theirs. The questions are read out of the text (PDF pages, or what llava read from the photo), then every
question gets an answer with the working. The file is saved after each answer, so the browser shows it growing.
"""
from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from pathlib import Path

from pydantic import BaseModel, Field

from . import config, llm, vision

log = logging.getLogger(__name__)

HW_DIR = config.MEDIA_DIR / "homework"
HW_DIR.mkdir(parents=True, exist_ok=True)
MAX_QUESTIONS = 30
_lock = threading.Lock()


class Questions(BaseModel):
    questions: list[str] = Field(description="Every question or exercise in the homework, in order, each as one string")


def _dir(hid: str) -> Path:
    if not hid.isalnum():
        raise ValueError("bad homework id")
    return HW_DIR / hid


def load(hid: str) -> dict:
    """Status plus the Markdown written so far."""
    d = _dir(hid)
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    md = d / "answers.md"
    meta["markdown"] = md.read_text(encoding="utf-8") if md.exists() else ""
    return meta


def list_all(limit: int = 20) -> list[dict]:
    out = []
    for f in HW_DIR.glob("*/meta.json"):
        try:
            out.append(json.loads(f.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    return sorted(out, key=lambda m: m.get("created", 0), reverse=True)[:limit]


def _save(hid: str, meta: dict, markdown: str | None = None) -> None:
    d = _dir(hid)
    with _lock:
        (d / "meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        if markdown is not None:
            (d / "answers.md").write_text(markdown, encoding="utf-8")


def start(concept: str, documents: list[str], images: list[str]) -> dict:
    hid = uuid.uuid4().hex[:10]
    _dir(hid).mkdir(parents=True, exist_ok=True)
    meta = {"id": hid, "title": concept.strip() or "Homework", "status": "queued", "done": 0, "total": 0, "created": int(time.time()),
            "documents": documents, "images": images, "error": None}
    _save(hid, meta, "")
    return meta


def source_text(documents: list[str], images: list[str], limit: int = 14000) -> str:
    """The homework as text: every page of the PDFs, then what the photos show."""
    parts: list[str] = []
    for sha in documents:
        try:
            from .ocr.ingest import load_page, read_info
            info = read_info(sha)
            for p in range(1, (info or {}).get("pages", 0) + 1):
                rec = load_page(sha, p)
                if rec and rec.text.strip():
                    parts.append(rec.text.strip())
        except Exception as e:  # noqa: BLE001
            log.warning("could not read pages of %s: %s", sha, e)
    ctx = vision.context(images, limit)
    if ctx:
        parts.append(ctx)
    return "\n\n".join(parts)[:limit]


def extract_questions(text: str) -> list[str]:
    """The questions, in order. Long homework is read in pieces so nothing is cut off."""
    if config.LLM_BACKEND == "mock":
        return [l.strip() for l in text.splitlines() if l.strip().endswith("?")][:MAX_QUESTIONS] or ["Describe the main idea."]
    chunks = [text[i:i + 6500] for i in range(0, len(text), 6500)][:3] or [text]
    found: list[str] = []
    for chunk in chunks:
        user = ("This is a student's homework (from a PDF or a photo, so there may be reading mistakes). List every question or exercise in it, "
                "in order. Join the parts (a), (b), (c) of one question into that question. Copy the wording, fix obvious reading mistakes. "
                "If there are no clear questions, list the tasks the student is asked to do. Maximum 30.\n\n" + chunk)
        try:
            got = llm.ask_json(Questions, user, options={"temperature": 0.1, "num_predict": 1200}, retries=1, timeout=240, expected_tokens=400)
        except Exception as e:  # noqa: BLE001
            log.warning("question extraction failed on a chunk: %s", e)
            continue
        for q in got.questions:
            q = " ".join(q.split())
            if len(q) > 3 and q.lower() not in (x.lower() for x in found):
                found.append(q)
    return found[:MAX_QUESTIONS]


ANSWER_SYSTEM = ("You write the answer key for a student's homework, like a patient teacher. Start with the final answer in bold. "
                 "Then show the working step by step in short lines, and end with one sentence on why it works. Plain text maths "
                 "(for example x^2, sqrt(5)). Markdown only for bold and lists. Be correct before being short; if the question is unclear, "
                 "say what you assumed.")


def answer(question: str, background: str) -> str:
    if config.LLM_BACKEND == "mock":
        return f"**Answer:** (sample) {question}"
    user = f"Question:\n{question}\n\nThe rest of the homework, for context:\n{background[:2500]}"
    return llm.stream_chat([{"role": "system", "content": ANSWER_SYSTEM}, {"role": "user", "content": user}],
                           {"temperature": 0.2, "num_predict": 600}, timeout=240, expected_tokens=300).strip()


def build(hid: str, progress=lambda s, p: None) -> dict:
    meta = load(hid)
    meta.pop("markdown", None)
    meta["status"] = "reading"
    _save(hid, meta)
    progress("Reading the homework", 0.05)
    try:
        text = source_text(meta["documents"], meta["images"])
        if not text.strip():
            raise ValueError("There was no readable text in the homework (a scanned PDF may still be being read: try again in a minute)")
        if meta["title"] == "Homework":
            meta["title"] = vision.topics(meta["images"]) or "Homework"
        questions = extract_questions(text)
        if not questions:
            raise ValueError("No questions could be found in the homework")
        meta.update(status="writing", total=len(questions), done=0)
        md = (f"# Homework answers: {meta['title']}\n\n> Written on this computer by the Chanakya AI. Use it to check your work "
              "and learn the method, and check the answers yourself before you hand them in.\n\n")
        _save(hid, meta, md)
        for i, q in enumerate(questions, 1):
            progress(f"Answering question {i} of {len(questions)}", 0.1 + 0.85 * (i - 1) / len(questions))
            md += f"## Question {i}\n\n> {q}\n\n{answer(q, text)}\n\n---\n\n"
            meta["done"] = i
            _save(hid, meta, md)
        meta["status"] = "done"
        _save(hid, meta, md)
        progress("Ready", 1.0)
    except Exception as e:  # noqa: BLE001
        meta.update(status="error", error=f"{type(e).__name__}: {e}")
        _save(hid, meta)
        raise
    return {"id": hid}
