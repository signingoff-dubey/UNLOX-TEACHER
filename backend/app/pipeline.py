"""Concept -> plan -> translate -> narrate (audio first) -> timed lesson JSON for the renderer."""
from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Callable

from . import config
from .captions import time_captions, to_srt
from .languages import get as get_lang
from .planner import plan_lesson
from .rag import retrieve_context
from .review import review as review_plan
from .schema import LIST_FIELDS, TEXT_FIELDS, LessonPlan
from .translate import translate_batch
from .tts import synthesize

log = logging.getLogger(__name__)
LESSONS_DIR = config.MEDIA_DIR / "lessons"

Progress = Callable[[str, float], None]


def build_lesson(concept: str, languages: list[str], level: str = "beginner", duration_s: int = 60,
                 documents: list[str] | None = None, progress: Progress = lambda s, p: None) -> dict:
    t0 = time.perf_counter()
    langs = list(dict.fromkeys(languages))                    # English is just another option now
    if not langs:
        raise ValueError("Pick at least one language")
    for code in langs:
        get_lang(code)                                        # validate early

    # Progress bands: plan 2-55%, review 55-60%, then 60-98% shared by the languages.
    progress("Planning the lesson", 0.02)
    context = retrieve_context(concept, documents or [])   # empty until the RAG service is connected
    plan = plan_lesson(concept, level=level, duration_s=duration_s, context=context,
                       on_progress=lambda f: progress("Planning the lesson", 0.02 + 0.53 * f))
    progress("Checking the lesson", 0.56)
    plan, review_notes = review_plan(plan)
    timings = {"plan_s": round(time.perf_counter() - t0, 2)}

    lesson_id = uuid.uuid4().hex[:10]
    out_dir = LESSONS_DIR / lesson_id
    out_dir.mkdir(parents=True, exist_ok=True)

    tracks = {}
    for i, code in enumerate(langs):
        base = 0.60 + 0.38 * i / len(langs)
        step = 0.38 / len(langs)
        name = get_lang(code).name
        progress(f"Translating to {name}" if code != "en" else "Preparing English", base)
        t1 = time.perf_counter()
        scenes, translator = _translated_scenes(plan, code)
        progress(f"Recording {name} narration", base + step * 0.25)
        tracks[code] = _narrate(scenes, code, lambda f, b=base, s=step, n=name: progress(f"Recording {n} narration", b + s * (0.25 + 0.75 * f)))
        tracks[code]["translator"] = translator
        timings[f"{code}_s"] = round(time.perf_counter() - t1, 2)
        (out_dir / f"captions_{code}.srt").write_text(_track_srt(tracks[code]), encoding="utf-8")

    lesson = {
        "id": lesson_id,
        "concept": concept,
        "created": int(time.time()),
        "plan": plan.model_dump(),                    # English source plan: context for the tutor chat
        "documents": documents or [],
        "review": review_notes,
        "languages": tracks,
        "timings": timings,
        "videos": {},
    }
    save_lesson(lesson)
    progress("Ready", 1.0)
    log.info("Lesson %s built in %.1fs %s", lesson_id, time.perf_counter() - t0, timings)
    return lesson


def _translated_scenes(plan: LessonPlan, lang: str) -> tuple[tuple[str, list[dict]], str]:
    """Translate every visible/spoken string in one batch, keeping the plan's structure."""
    scenes = [s.model_dump() for s in plan.scenes]
    slots: list[tuple] = [("title",)]
    texts = [plan.title]
    for i, s in enumerate(scenes):
        for f in TEXT_FIELDS:
            slots.append((i, f)); texts.append(s[f])
        for f in LIST_FIELDS:
            for j, item in enumerate(s[f]):
                slots.append((i, f, j)); texts.append(item)
    translated, engine = translate_batch(texts, lang)
    title = plan.title
    for slot, value in zip(slots, translated):
        if slot == ("title",):
            title = value
        elif len(slot) == 2:
            scenes[slot[0]][slot[1]] = value
        else:
            scenes[slot[0]][slot[1]][slot[2]] = value
    return (title, scenes), engine


def _narrate(translated: tuple[str, list[dict]], lang: str, on_progress=lambda f: None) -> dict:
    """Narration first: each scene lasts exactly as long as its voice plus a short pause."""
    title, scenes = translated
    start = 0.0
    engines = set()
    for k, s in enumerate(scenes):
        on_progress(k / max(len(scenes), 1))
        speech = synthesize(s["narration"], lang)
        engines.add(speech.engine)
        s["audio_url"] = f"/media/audio/{speech.path.name}"
        s["speech_s"] = round(speech.duration_s, 3)
        s["duration_s"] = round(speech.duration_s + config.SCENE_PADDING_S, 3)
        s["start_s"] = round(start, 3)
        s["captions"] = time_captions(s["narration"], speech.duration_s)
        start += s["duration_s"]
    language = get_lang(lang)
    return {
        "lang": lang,
        "name": language.name,
        "native": language.native,
        "title": title,
        "scenes": scenes,
        "duration_s": round(start, 3),
        "tts_engines": sorted(engines),
    }


def _track_srt(track: dict) -> str:
    cues = [{**c, "start": c["start"] + s["start_s"], "end": c["end"] + s["start_s"]}
            for s in track["scenes"] for c in s["captions"]]
    return to_srt(cues)


def lesson_path(lesson_id: str):
    if not lesson_id.isalnum():
        raise ValueError("bad lesson id")
    return LESSONS_DIR / lesson_id / "lesson.json"


def save_lesson(lesson: dict) -> None:
    lesson_path(lesson["id"]).write_text(json.dumps(lesson, ensure_ascii=False, indent=1), encoding="utf-8")


def load_lesson(lesson_id: str) -> dict:
    return json.loads(lesson_path(lesson_id).read_text(encoding="utf-8"))
