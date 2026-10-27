"""Study notes from a PDF, written as the pages are read, 30 pages at a time.

OCR reads about 6 pages a second, so a 30-page window is ready every ~5 seconds. Each window goes to the local model as
soon as its last page has been read, and comes back as a small JSON block (heading, key points, terms). The notes of a
whole book therefore appear while the book is still being read, instead of after it, and a 100-page PDF has all its notes
about a minute after the upload. The video lesson is then planned from these notes (a few KB), never from 1,000 pages.
Data only: the model returns JSON that matches a schema.
"""
from __future__ import annotations

import json
import logging
import queue
import threading
from pathlib import Path
from typing import Callable

import requests
from pydantic import BaseModel, Field, ValidationError

from .. import config

log = logging.getLogger(__name__)

WINDOW = 30                      # pages per block of notes
PAGE_CHARS = 230                 # how much of each page the model sees (30 pages is then ~7 KB)


class Term(BaseModel):
    term: str
    meaning: str = Field(description="One plain sentence")


class WindowNotes(BaseModel):
    heading: str = Field(description="What these pages are about, max 8 words")
    points: list[str] = Field(description="4-6 short study points, each a full sentence")
    terms: list[Term] = Field(default_factory=list, description="0-5 key terms with a plain meaning")


def windows(n_pages: int) -> list[tuple[int, int]]:
    """[(1, 30), (31, 60), ...] (the last one may be shorter)."""
    return [(a, min(a + WINDOW - 1, n_pages)) for a in range(1, n_pages + 1, WINDOW)]


def notes_dir(upload_dir: Path) -> Path:
    return upload_dir / "notes"


def load_notes(upload_dir: Path) -> list[dict]:
    out = []
    for f in sorted(notes_dir(upload_dir).glob("*.json"), key=lambda p: int(p.stem)):
        try:
            out.append(json.loads(f.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    return out


def window_text(pages: dict[int, str], first: int, last: int) -> str:
    """A fair sample of the window: the start of every page, cut at a sentence boundary."""
    parts = []
    for p in range(first, last + 1):
        t = " ".join(pages.get(p, "").split())
        if len(t) > PAGE_CHARS:
            t = (t[:PAGE_CHARS].rsplit(". ", 1)[0] + ".") if ". " in t[:PAGE_CHARS] else t[:PAGE_CHARS]
        if t:
            parts.append(f"[p{p}] {t}")
    return "\n".join(parts)


def ask_ollama(text: str, first: int, last: int) -> WindowNotes:
    system = ("You write study notes for a student from pages of a textbook. Use only the pages given: never invent facts. "
              "Write simple English. Return ONLY JSON that matches the schema.")
    user = f"Pages {first}-{last}:\n{text}\n\nWrite the study notes for these pages."
    r = requests.post(f"{config.OLLAMA_URL}/api/chat", json={
        "model": config.OLLAMA_MODEL, "stream": False, "keep_alive": config.OLLAMA_KEEP_ALIVE,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "format": WindowNotes.model_json_schema(), "options": config.ollama_options({"temperature": 0.2, "num_ctx": 4096}),
    }, timeout=240)
    r.raise_for_status()
    return WindowNotes.model_validate_json(r.json()["message"]["content"])


def heuristic(text: str, first: int, last: int) -> WindowNotes:
    """No model (mock backend): the first sentences of the window."""
    sentences = [s.strip() for s in text.replace("\n", " ").split(". ") if len(s.strip()) > 25][:5]
    return WindowNotes(heading=f"Pages {first}-{last}", points=sentences or [f"Pages {first} to {last}."])


class Digester:
    """One background worker that turns windows into notes, in the order they become ready."""

    def __init__(self, ask: Callable[[str, int, int], WindowNotes] | None = None) -> None:
        self._ask = ask
        self._q: queue.Queue[tuple[Path, int, int, int, str] | None] = queue.Queue()
        self._seen: set[tuple[str, int]] = set()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self.on_saved: Callable[[], None] = lambda: None

    def submit(self, upload_dir: Path, idx: int, first: int, last: int, text: str) -> None:
        out = notes_dir(upload_dir) / f"{idx}.json"
        with self._lock:
            key = (str(upload_dir), idx)
            if key in self._seen or out.exists():
                return
            self._seen.add(key)
            self._q.put((upload_dir, idx, first, last, text))
            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(target=self._run, name="pdf-notes", daemon=True)
                self._thread.start()

    def idle(self, timeout: float = 30) -> bool:
        """Wait until everything submitted so far has been written (tests, shutdown)."""
        self._q.join()
        return True

    def _run(self) -> None:
        while True:
            try:
                item = self._q.get(timeout=5)
            except queue.Empty:
                return
            upload_dir, idx, first, last, text = item
            try:
                self._write(upload_dir, idx, first, last, text)
            except Exception as e:  # noqa: BLE001  one bad window must not stop the rest
                log.warning("notes for pages %d-%d failed: %s", first, last, e)
                with self._lock:
                    self._seen.discard((str(upload_dir), idx))
            finally:
                self._q.task_done()

    def _write(self, upload_dir: Path, idx: int, first: int, last: int, text: str) -> None:
        if not text.strip():
            notes = WindowNotes(heading=f"Pages {first}-{last}", points=[])
        elif self._ask:
            notes = self._ask(text, first, last)
        elif config.LLM_BACKEND == "mock":
            notes = heuristic(text, first, last)
        else:
            from ..gpu import big_slot
            with big_slot.hold("notes", urgent=True):               # the book's background OCR steps aside for it, like for a lesson
                try:
                    notes = ask_ollama(text, first, last)
                except (ValidationError, ValueError):
                    notes = ask_ollama(text, first, last)           # one retry on bad JSON
        d = notes_dir(upload_dir)
        d.mkdir(parents=True, exist_ok=True)
        tmp = d / f"{idx}.json.tmp"
        tmp.write_text(json.dumps({"window": idx, "pages": [first, last], **notes.model_dump()}, ensure_ascii=False), encoding="utf-8")
        tmp.replace(d / f"{idx}.json")
        self.on_saved()


shared = Digester()


class WindowTracker:
    """Counts the pages each window is still waiting for; hands a window to the digester the moment it completes."""

    def __init__(self, upload_dir: Path, n_pages: int, pending: set[int], pages: dict[int, str], digester: Digester | None = None) -> None:
        self.dir = upload_dir
        self.pages = pages                                   # page number -> text so far (shared with the ingest loop)
        self.digester = digester or shared
        self.wins = windows(n_pages)
        self.waiting = {i: {p for p in range(a, b + 1) if p in pending} for i, (a, b) in enumerate(self.wins)}
        for i in self.waiting:
            if not self.waiting[i]:
                self._submit(i)

    def page_done(self, page: int) -> None:
        i = (page - 1) // WINDOW
        self.waiting[i].discard(page)
        if not self.waiting[i]:
            self._submit(i)

    def _submit(self, i: int) -> None:
        a, b = self.wins[i]
        self.digester.submit(self.dir, i, a, b, window_text(self.pages, a, b))


def progress(upload_dir: Path, n_pages: int) -> dict:
    return {"total": len(windows(n_pages)), "done": len(list(notes_dir(upload_dir).glob("*.json")))}


def reference(upload_dir: Path, budget: int = 9000) -> str:
    """All the notes so far as one block of text, in page order, for planning a lesson about the whole PDF."""
    parts = []
    for n in load_notes(upload_dir):
        terms = "; ".join(f"{t['term']}: {t['meaning']}" for t in n["terms"])
        parts.append(f"[pages {n['pages'][0]}-{n['pages'][1]}] {n['heading']}. " + " ".join(n["points"]) + (f" Terms: {terms}" if terms else ""))
    text = "\n\n".join(parts)
    if len(text) <= budget:
        return text
    keep = max(1, min(len(parts), budget // 90))                      # a long book: sample the windows evenly...
    if keep < len(parts):
        parts = [parts[round(i * (len(parts) - 1) / max(keep - 1, 1))] for i in range(keep)]   # first and last always included
    per = budget // len(parts) - 2                                    # ...and give each the same share
    return "\n\n".join(p[:per].rsplit(" ", 1)[0] if len(p) > per else p for p in parts)[:budget]
