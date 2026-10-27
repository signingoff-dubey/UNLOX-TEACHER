"""Concept -> plan -> translate -> narrate (audio first) -> timed lesson JSON for the renderer."""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
import logging
import time
import uuid
from typing import Callable

from . import config
from .captions import time_captions, to_srt
from .languages import get as get_lang, words_per_sec
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
    wps = words_per_sec(langs)
    plan = plan_lesson(concept, level=level, duration_s=duration_s, context=context, wps=wps,
                       on_progress=lambda f: progress("Planning the lesson", 0.02 + 0.53 * f))
    progress("Checking the lesson", 0.56)
    plan, review_notes = review_plan(plan, duration_s, wps)
    timings = {"plan_s": round(time.perf_counter() - t0, 2)}

    lesson_id = uuid.uuid4().hex[:10]
    out_dir = LESSONS_DIR / lesson_id
    out_dir.mkdir(parents=True, exist_ok=True)

    # Stage A: translate every language (one shared model, so one after another).
    translated: dict[str, tuple] = {}
    t_translate: dict[str, float] = {}
    for i, code in enumerate(langs):
        name = get_lang(code).name
        progress(f"Translating to {name}" if code != "en" else "Preparing English", 0.60 + 0.12 * i / len(langs))
        t1 = time.perf_counter()
        translated[code] = _translated_scenes(plan, code)
        t_translate[code] = time.perf_counter() - t1

    # Stage B: record the voices of all languages at the same time (voices run on CPU, one per language).
    done_frac = {code: 0.0 for code in langs}

    def narrate_one(code: str) -> tuple[str, dict, float]:
        name = get_lang(code).name

        def report(f: float) -> None:
            done_frac[code] = f
            progress(f"Recording {name} narration", 0.72 + 0.26 * sum(done_frac.values()) / len(langs))

        t2 = time.perf_counter()
        scenes, translator = translated[code]
        track = _narrate(scenes, code, report)
        track["translator"] = translator
        return code, track, time.perf_counter() - t2

    tracks: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=min(len(langs), 4)) as pool:
        for code, track, secs in pool.map(narrate_one, langs):
            tracks[code] = track
            timings[f"{code}_s"] = round(t_translate[code] + secs, 2)
            (out_dir / f"captions_{code}.srt").write_text(_track_srt(track), encoding="utf-8")
    tracks = {code: tracks[code] for code in langs}          # keep the order the learner picked

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
