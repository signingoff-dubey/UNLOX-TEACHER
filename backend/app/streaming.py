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
                 on_first: Callable[[], None] = lambda: None, reject: Callable[[dict], bool] | None = None) -> None:
        self.id, self.concept, self.lang, self.rest, self.langs, self.expected, self.path = lesson_id, concept, lang, rest, langs, expected, path
        self.on_first = on_first
        self.reject = reject                   # scenes the finished plan will not contain (a quiz or summary in the first part of a long video) are not shown
        self.created = int(time.time())
        self.title = concept
        self._q: queue.Queue = queue.Queue()
        self._lock = threading.Lock()
        self._gen = 0
        self._seen = 0
        self._main = {"seen": 0, "skip": 0, "reject": reject}      # the first (or only) part, fed through feed()
        self._closed = False
        self._pp: list = []                    # ScenePlan objects made so far (after cleaning)
        self._track: dict | None = None
        self._announced = False
        self._pre_q: queue.Queue = queue.Queue()
        self._drafts: dict[str, dict] = {}
        self._thread = threading.Thread(target=self._run, name="scene-preview", daemon=True)
        self._thread.start()
        self._pre = threading.Thread(target=self._pre_run, name="scene-precache", daemon=True)
        self._pre.start()

    # ---- the other languages: each finished scene is translated and voiced too, so their tabs fill in while the video is made
    #      (a draft track per language; translations and clips are cached, so the final pass then finds most of it ready)
    def _pre_run(self) -> None:
        from .languages import get as get_lang
        from .pipeline import _narrate, _translated_scenes
        from .schema import LessonPlan
        while True:
            item = self._pre_q.get()
            if item is None:
                return
            if self._closed or not self.rest:
                continue
            for code in self.rest:
                if self._closed:
                    break
                try:
                    (title, scenes), engine = _translated_scenes(LessonPlan(title=self.title, scenes=item), code)
                    part = _narrate((title, scenes), code, voice_lang="en" if engine == "untranslated" else code)
                except Exception as e:  # noqa: BLE001  a draft is a bonus: the final pass makes the language anyway
                    log.info("draft %s scene skipped: %s", code, e)
                    continue
                with self._lock:
                    if self._closed:
                        return
                    track = self._drafts.get(code)
                    if track is None:
                        lang = get_lang(code)
                        track = self._drafts[code] = {"lang": code, "name": lang.name, "native": lang.native, "title": title, "scenes": [],
                                                      "duration_s": 0.0, "tts_engines": [], "translator": engine, "source_note": "", "draft": True}
                    offset = track["duration_s"]
                    for s in part["scenes"]:
                        s["start_s"] = round(s["start_s"] + offset, 3)
                    track["scenes"].extend(part["scenes"])
                    track["duration_s"] = round(offset + part["duration_s"], 3)
                    track["tts_engines"] = sorted(set(track["tts_engines"]) | set(part["tts_engines"]))
                    self._publish()

    def drafts(self) -> dict[str, dict]:
        """The other languages as far as they were made while the video was written (shown until their final version is ready)."""
        with self._lock:
            return {c: t for c, t in self._drafts.items() if t["scenes"]}

    # ---- fed by the planner's token stream
    def feed(self, text: str) -> None:
        self._feed(self._main, text)

    def stream(self, reject: Callable[[dict], bool] | None = None) -> Callable[[str], None]:
        """A token stream of its own for a later part of a long video: its scenes go after everything fed so far."""
        state = {"seen": 0, "skip": 0, "reject": reject}
        return lambda text: self._feed(state, text)

    def _feed(self, state: dict, text: str) -> None:
        title, scenes = extract_scenes(text)
        with self._lock:
            if self._closed:
                return
            if title and state is self._main:
                self.title = title
            if len(scenes) < state["seen"]:                   # the planner started over (a retry): what is on screen stays, the new answer carries on after it
                state["skip"] = max(state["skip"], state["seen"])
                state["seen"] = 0
            base = state["seen"]
            new = scenes[base:]
            state["seen"] = len(scenes)
            if state is self._main:
                self._seen = max(self._seen, state["seen"])
            gen = self._gen
        reject = state["reject"]
        for k, obj in enumerate(new):
            if base + k < state["skip"]:
                continue
            if reject is None or not reject(obj):
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
        self._pre_q.put(None)
        self._thread.join(timeout=wait)

    # ---- the worker
    def _run(self) -> None:
        while True:
            item = self._q.get()
            if item is None:
                return
            gen, obj = item
            if gen != self._gen or self._closed:
                self._q.task_done()
                continue
            try:
                self._one(gen, obj)
            except Exception as e:  # noqa: BLE001  a scene that cannot be previewed is simply made in the final pass
                log.warning("preview of a scene failed: %s", e)
            finally:
                self._q.task_done()

    def drain(self, timeout: float = 30.0) -> None:
        """Wait (at most `timeout` s) until every scene the planner has written so far is on screen."""
        deadline = time.monotonic() + timeout
        while self._q.unfinished_tasks and time.monotonic() < deadline:
            time.sleep(0.1)

    def shown(self) -> list:
        """The scenes as the learner has seen them (after cleaning), in order."""
        with self._lock:
            return [s.model_copy(deep=True) for s in self._pp]

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
        self._pre_q.put(fresh)
        if not self._announced:
            self._announced = True
            self.on_first()

    def _publish(self) -> None:
        from .languages import get as get_lang
        draft = {
            "id": self.id, "concept": self.concept, "upload": None, "focus": "", "created": self.created,
            "plan": {"title": self.title, "scenes": [s.model_dump() for s in self._pp]},
            "documents": [], "series": None, "review": [],
            "languages": {c: t for c, t in ({self.lang: self._track} | self._drafts).items() if t and t["scenes"]},
            "pending": [{"code": c, "name": get_lang(c).name, "native": get_lang(c).native} for c in self.rest],
            "failed": [], "order": self.langs, "sources": [], "timings": {}, "videos": {},
            "building": True, "scenes_total": max(self.expected, len(self._pp)),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(draft, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)                              # a poller never reads half a file
