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
from .schema import LIST_FIELDS, TEXT_FIELDS, LessonPlan
from .translate import translate_batch
from .tts import synthesize

log = logging.getLogger(__name__)
LESSONS_DIR = config.MEDIA_DIR / "lessons"

Progress = Callable[[str, float], None]


def build_lesson(concept: str, languages: list[str], upload: str | None = None, focus: str = "",
                 progress: Progress = lambda s, p: None) -> dict:
    """Builds a lesson. With `upload` (a PDF's sha), facts come from that PDF first; with an empty
    concept or a `focus` like "chapter 4", the lesson teaches that part of the PDF."""
    # Hold the GPU for the whole build: background OCR (Unlimited-OCR, ~6.8 GB) yields between pages
    # so the LLM and NLLB fit in 8 GB, and never reloads mid-lesson.
    with _gpu_slot():
        return _build(concept, languages, upload, focus, progress)


def _gpu_slot():
    try:
        from .gpu import big_slot
        return big_slot.hold("planner", urgent=True)
    except ImportError:                                   # OCR extras not installed
        import contextlib
        return contextlib.nullcontext()


def _build(concept: str, languages: list[str], upload: str | None, focus: str, progress: Progress) -> dict:
    t0 = time.perf_counter()
    langs = list(dict.fromkeys(["en", *languages]))          # English is always included
    for code in langs:
        get_lang(code)                                        # validate early

    progress("Reading the PDF and planning the lesson" if upload else "Finding facts and planning the lesson", 0.05)
    plan, sources = plan_lesson(concept, upload=upload, focus=focus)
    note = source_note(sources)
    timings = {"plan_s": round(time.perf_counter() - t0, 2)}

    lesson_id = uuid.uuid4().hex[:10]
    out_dir = LESSONS_DIR / lesson_id
    out_dir.mkdir(parents=True, exist_ok=True)

    tracks = {}
    for i, code in enumerate(langs):
        base = 0.15 + 0.8 * i / len(langs)
        step = 0.8 / len(langs)
        progress(f"Translating to {get_lang(code).name}", base)
        t1 = time.perf_counter()
        scenes, translator = _translated_scenes(plan, code)
        progress(f"Recording {get_lang(code).name} narration", base + step * 0.4)
        tracks[code] = _narrate(scenes, code)
        tracks[code]["translator"] = translator
        tracks[code]["source_note"] = note
        timings[f"{code}_s"] = round(time.perf_counter() - t1, 2)
        (out_dir / f"captions_{code}.srt").write_text(_track_srt(tracks[code]), encoding="utf-8")

    lesson = {
        "id": lesson_id,
        "concept": concept or (f"{focus} (PDF)" if focus else plan.title),
        "upload": upload,
        "focus": focus,
        "created": int(time.time()),
        "languages": tracks,
        "sources": sources,
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


def _narrate(translated: tuple[str, list[dict]], lang: str) -> dict:
    """Narration first: each scene lasts exactly as long as its voice plus a short pause."""
    title, scenes = translated
    start = 0.0
    engines = set()
    for s in scenes:
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


def source_note(sources: list[dict]) -> str:
    """One short citation line for the recap scene, e.g. "Source: Science 8, Ch 3, pp. 41–44"."""
    if not sources:
        return ""
    top = sources[0]
    if top.get("source") == "upload" or str(top.get("url", "")).startswith("upload:"):
        where = f"{top['title']}, {top['section']}" if top.get("section") else top["title"]
        return f"Source: {where}"
    names = [s["title"] for s in sources[:3]]
    site = "Wikipedia" if "wikipedia" in str(top.get("source", "")) else top.get("source", "")
    return f"Sources: {', '.join(names)}" + (f" ({site})" if site else "")


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
