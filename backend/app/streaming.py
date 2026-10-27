"""Scenes that appear while the lesson is still being written.

The planner streams its JSON token by token. As soon as one scene object is complete, it is cleaned, translated, voiced and published to
`lesson.json` (marked `building`), so the player can start on scene 1 a few seconds after the click and scenes are added as they are made.
The finished plan then goes through the director and the reviewer as before; voices and translations of the scenes already made are
cached, so the final pass is quick. The preview stops writing before the final lesson is saved, so the two never overwrite each other.
"""
from __future__ import annotations

import json
import logging
import queue
import re
import threading
import time
from pathlib import Path
from typing import Callable

log = logging.getLogger(__name__)


def extract_scenes(text: str) -> tuple[str, list[dict]]:
    """The title and the scene objects that are already complete in a (possibly unfinished) plan JSON."""
    title = ""
    m = re.search(r'"title"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
    if m:
        try:
            title = json.loads('"' + m.group(1) + '"')
        except ValueError:
            title = m.group(1)
    key = re.search(r'"scenes"\s*:\s*\[', text)
    if not key:
        return title, []
    scenes: list[dict] = []
    depth, start, in_str, esc = 0, -1, False, False
    for i in range(key.end(), len(text)):
        c = text[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c == "{":
            if depth == 0:
                start = i
            depth += 1
        elif c == "}" and depth:
            depth -= 1
            if depth == 0 and start >= 0:
                try:
                    obj = json.loads(text[start:i + 1])
                    if isinstance(obj, dict):
                        scenes.append(obj)
                except ValueError:
                    pass
                start = -1
        elif c == "]" and depth == 0:
            break
    return title, scenes


class ScenePreview:
    """Builds the first language of a lesson scene by scene while the planner is still writing. One worker thread, in order."""

    def __init__(self, lesson_id: str, concept: str, lang: str, rest: list[str], langs: list[str], expected: int, path: Path,
                 on_first: Callable[[], None] = lambda: None) -> None:
        self.id, self.concept, self.lang, self.rest, self.langs, self.expected, self.path = lesson_id, concept, lang, rest, langs, expected, path
        self.on_first = on_first
        self.created = int(time.time())
        self.title = concept
        self._q: queue.Queue = queue.Queue()
        self._lock = threading.Lock()
        self._gen = 0
        self._seen = 0
        self._closed = False
        self._pp: list = []                    # ScenePlan objects made so far (after cleaning)
        self._track: dict | None = None
        self._announced = False
        self._thread = threading.Thread(target=self._run, name="scene-preview", daemon=True)
        self._thread.start()

    # ---- fed by the planner's token stream
    def feed(self, text: str) -> None:
        title, scenes = extract_scenes(text)
        with self._lock:
            if self._closed:
                return
            if title:
                self.title = title
            if len(scenes) < self._seen:                       # the planner started over (a retry): forget what was shown
                self._gen += 1
                self._seen = 0
                self._pp, self._track = [], None
            new = scenes[self._seen:]
            self._seen = len(scenes)
            gen = self._gen
        for obj in new:
            self._q.put((gen, obj))

    def add_scenes(self, objs: list[dict]) -> None:
        """Scenes that are already complete (a finished part of a long video), after everything fed so far, in order."""
        with self._lock:
            if self._closed:
                return
            gen = self._gen
            self._seen += len(objs)
        for obj in objs:
            self._q.put((gen, obj))

    def close(self, wait: float = 20.0) -> None:
        """No more writes after this returns (waits for the scene being made, so the final save is the last word)."""
        with self._lock:
            self._closed = True
        self._q.put(None)
        self._thread.join(timeout=wait)

    # ---- the worker
    def _run(self) -> None:
        while True:
            item = self._q.get()
            if item is None:
                return
            gen, obj = item
            if gen != self._gen or self._closed:
                continue
            try:
                self._one(gen, obj)
            except Exception as e:  # noqa: BLE001  a scene that cannot be previewed is simply made in the final pass
                log.warning("preview of a scene failed: %s", e)

    def _one(self, gen: int, obj: dict) -> None:
        from .languages import get as get_lang
        from .pipeline import _narrate, _translated_scenes
        from .schema import LessonPlan, ScenePlan, normalize
        sp = ScenePlan.model_validate(obj)
        if not self._pp:
            fresh = normalize(LessonPlan(title=self.title, scenes=[sp])).scenes             # may add the title scene in front
        else:
            lead = ScenePlan(template="title", heading="x", narration="x")
            both = normalize(LessonPlan(title=self.title, scenes=[lead, sp])).scenes
            if len(both) < 2:                                                               # no narration: nothing to show
                return
            fresh = [both[-1]]
        (title, scenes), engine = _translated_scenes(LessonPlan(title=self.title, scenes=fresh), self.lang)
        part = _narrate((title, scenes), self.lang, voice_lang="en" if engine == "untranslated" else self.lang)
        with self._lock:
            if self._closed or gen != self._gen:
                return
            if self._track is None:
                lang = get_lang(self.lang)
                self._track = {"lang": self.lang, "name": lang.name, "native": lang.native, "title": title, "scenes": [], "duration_s": 0.0,
                               "tts_engines": [], "translator": engine, "source_note": ""}
            offset = self._track["duration_s"]
            for s in part["scenes"]:
                s["start_s"] = round(s["start_s"] + offset, 3)
            self._track["scenes"].extend(part["scenes"])
            self._track["duration_s"] = round(offset + part["duration_s"], 3)
            self._track["tts_engines"] = sorted(set(self._track["tts_engines"]) | set(part["tts_engines"]))
            self._pp.extend(fresh)
            self._publish()
        if not self._announced:
            self._announced = True
            self.on_first()

    def _publish(self) -> None:
        from .languages import get as get_lang
        draft = {
            "id": self.id, "concept": self.concept, "upload": None, "focus": "", "created": self.created,
            "plan": {"title": self.title, "scenes": [s.model_dump() for s in self._pp]},
            "documents": [], "series": None, "review": [], "languages": {self.lang: self._track},
            "pending": [{"code": c, "name": get_lang(c).name, "native": get_lang(c).native} for c in self.rest],
            "failed": [], "order": self.langs, "sources": [], "timings": {}, "videos": {},
            "building": True, "scenes_total": max(self.expected, len(self._pp)),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(draft, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)                              # a poller never reads half a file
