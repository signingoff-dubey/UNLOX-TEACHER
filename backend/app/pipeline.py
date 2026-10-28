"""Concept -> plan -> translate -> narrate (audio first) -> timed lesson JSON for the renderer."""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
import logging
import threading
import time
import uuid
from typing import Callable

from . import config, vision
from .captions import time_captions, to_srt
from .languages import get as get_lang, words_per_sec
from .longplan import LONG_MIN, plan_long
from .planner import plan_lesson
from .director import direct
from .review import review as review_plan
from . import content, expression, facts
from .schema import LIST_FIELDS, TEXT_FIELDS, LessonPlan, normalize
from .translate import translate_batch
from .tts import synthesize

log = logging.getLogger(__name__)
LESSONS_DIR = config.MEDIA_DIR / "lessons"

Progress = Callable[[str, float], None]
FLASH_FACT_BUDGET_S = float(__import__("os").getenv("FLASH_FACT_BUDGET_S", "30"))      # Flash: the learner is already watching; Pro keeps twice FACTCHECK_BUDGET_S


def build_lesson(concept: str, languages: list[str], level: str = "beginner", duration_s: int = 60,
                 documents: list[str] | None = None, series: dict | None = None, focus: str = "",
                 images: list[str] | None = None, mode: str = "explain", progressive: bool = False,
                 plan: LessonPlan | None = None, quality: str = "flash", progress: Progress = lambda s, p: None) -> dict:       # `progress` last: jobs.submit appends it
    """Builds a lesson. `documents` holds uploaded PDFs (their sha): facts come from the first one before the
    library; with an empty concept or a `focus` like "chapter 4", the lesson teaches that part of the PDF."""
    concept = content.clean_topic(concept) if concept.strip() else concept          # never "Teach me about ..." in a title or a caption
    # Hold the GPU for the whole build: background OCR (Unlimited-OCR, ~6.8 GB) yields between pages
    # so the LLM and NLLB fit in 8 GB, and never reloads mid-lesson.
    quality = "pro" if quality == "pro" else "flash"
    with _gpu_slot():
        return _build(concept, languages, level, duration_s, documents or [], series, progress, focus, images or [], mode, progressive, plan, quality)


def _gpu_slot():
    try:
        from .gpu import big_slot
        return big_slot.hold("planner", urgent=True, shared=True)       # lessons share it (episodes of a course overlap); OCR waits for all of them
    except ImportError:                                   # OCR extras not installed
        import contextlib
        return contextlib.nullcontext()


def _build(concept: str, languages: list[str], level: str, duration_s: int, documents: list[str],
           series: dict | None, progress: Progress, focus: str, images: list[str], mode: str, progressive: bool,
           plan_override: LessonPlan | None = None, quality: str = "flash") -> dict:
    upload = documents[0] if documents else None
    if vision.pending(images):
        progress("Reading your photo", 0.03)                  # the learner did not have to wait for it: the lesson starts with it
    extra = vision.context(images)                            # what the attached photos show (read earlier by llava, or now)
    if series and extra and mode != "homework":
        extra = vision.relevant(extra, f"{series.get('this', '')} {series.get('title', '')} {concept}")     # this video gets only the part of the photo that is about it
    if not concept.strip() and not documents and extra:
        concept = vision.topics(images) or "the topic in the attached photo"
    t0 = time.perf_counter()
    langs = list(dict.fromkeys(languages))                    # English is just another option now
    if not langs:
        raise ValueError("Pick at least one language")
    for code in langs:
        get_lang(code)                                        # validate early

    # Progress bands: plan 2-55%, review 55-60%, then 60-98% shared by the languages.
    stage = "Reading the PDF and planning the lesson" if upload else "Finding facts and planning the lesson"
    last = [stage, 0.02]
    raw_progress = progress

    def progress(s: str, v: float, **extra) -> None:          # noqa: F811  remembers where it got to, so the job can be tagged later
        last[0], last[1] = s, v
        raw_progress(s, v, **extra) if extra else raw_progress(s, v)

    progress(stage, 0.02)
    wps = words_per_sec(langs)
    on_plan = lambda f: progress(stage, 0.02 + 0.40 * f)  # noqa: E731
    lesson_id = uuid.uuid4().hex[:10]
    out_dir = LESSONS_DIR / lesson_id

    if plan_override is not None:                             # a plan that was written by hand: no planner, director, review or fact check, everything after is the same
        plan, sources, preview = normalize(plan_override), [], None
        review_notes, fact_report = ["hand-written plan: it was not planned, directed, reviewed or fact-checked by the model"], None
        timings = {"plan_s": 0.0}
    else:
        # The first scenes are made while the planner is still writing, so the player can start at once (see streaming.py).
        preview = None
        on_text = None
        long_video = duration_s > LONG_MIN and config.LLM_BACKEND != "mock"
        pro = quality == "pro" and config.LLM_BACKEND != "mock"
        if progressive and config.LLM_BACKEND != "mock" and not pro:             # Flash shows the first scenes while the rest is still being written; Pro shows nothing until it is all planned
            from .longplan import parts_for
            from .planner import scene_target
            from .streaming import ScenePreview
            expected = parts_for(duration_s) * scene_target(round(duration_s / parts_for(duration_s))) if long_video else scene_target(duration_s)
            preview = ScenePreview(lesson_id, concept or "Your lesson", langs[0], langs[1:], langs, expected, lesson_path(lesson_id),
                                   on_first=lambda: raw_progress(last[0], last[1], lesson_id=lesson_id),
                                   reject=(lambda o: o.get("template") in ("summary", "quiz")) if long_video else None)      # part 1 of a long video has no quiz or summary
            on_text = preview.feed
        if pro:
            from .longplan import plan_pro
            progress("Planning the whole video", 0.02)
            plan, sources = plan_pro(concept, level, duration_s, upload, focus, wps, on_plan, extra, mode, course=series)
        elif long_video:
            plan, sources = plan_long(concept, level, duration_s, upload, focus, wps, on_plan, extra, mode, preview=preview)      # 1.5-4 min: planned in parts
        else:
            plan, sources = plan_lesson(concept, level=level, duration_s=duration_s, upload=upload, focus=focus, wps=wps,
                                        series=series, on_progress=on_plan, extra=extra, mode=mode, on_text=on_text, fast=on_text is not None)
        note = source_note(sources)
        for n in content.dedupe_plan(plan):                       # no repeated scene, code block or summary reaches the screen
            log.info("plan cleaned: %s", n)
        from .planner import subject_of
        for n in content.strip_analogies(plan, keep=1 if any(subject_of(concept)) else 2):      # one everyday comparison per technical video is enough
            log.info("plan cleaned: %s", n)
        progress("Designing the visuals", 0.43)
        plan, director_notes = direct(plan, concept, lambda f: progress("Designing the visuals", 0.43 + 0.13 * f))
        progress("Checking the lesson", 0.57)
        plan, review_notes = review_plan(plan, duration_s, wps)
        review_notes = director_notes + review_notes
        if preview is not None:                              # Flash: what the learner already watched stays as it was (same words, same voice), so the
            preview.drain()                                  # final video does not change under the player; only the fact check below may still correct it
            kept = keep_shown(plan, preview.shown())
            if kept:
                log.info("kept %d scenes as they were shown", kept)
        if series is not None:                               # the next video of the course is planned knowing this, and starts now: it does not wait for the fact check
            raw_progress("Checking the facts", 0.575, taught=content.taught_summary(plan), planned=True)
        fact_report = None
        if config.FACTCHECK and config.LLM_BACKEND != "mock":
            progress("Checking the facts", 0.575)
            budget = config.FACTCHECK_BUDGET_S * 2 if pro else min(config.FACTCHECK_BUDGET_S, FLASH_FACT_BUDGET_S)
            fact_report = facts.check_plan(plan, concept or plan.title, upload, budget_s=budget,
                                           progress=lambda f: progress("Checking the facts", 0.575 + 0.02 * f))
            review_notes = review_notes + fact_report.notes()
        timings = {"plan_s": round(time.perf_counter() - t0, 2)}

    out_dir.mkdir(parents=True, exist_ok=True)
    if preview is not None:
        preview.close()                                       # the scene being made finishes; from here the final save is the only writer

    note = source_note(sources)

    def make_track(code: str, report=lambda f: None) -> tuple[dict, float]:
        """One language: translate every string, then record the voice. Returns the track and the seconds it took."""
        t1 = time.perf_counter()
        scenes, translator = _translated_scenes(plan, code)
        # Untranslated text must not be read by a Hindi voice (English words with a Hindi accent): use the English voice.
        track = _narrate(scenes, code, report, voice_lang="en" if translator == "untranslated" else code)
        track["translator"] = translator
        track["source_note"] = note
        (out_dir / f"captions_{code}.srt").write_text(_track_srt(track), encoding="utf-8")
        return track, time.perf_counter() - t1

    first, rest = (langs[:1], langs[1:]) if progressive else (langs, [])
    tracks: dict[str, dict] = {}
    if len(first) == 1:
        code = first[0]
        name = get_lang(code).name
        progress(f"Translating to {name}" if code != "en" else "Preparing English", 0.60)
        tracks[code], timings[f"{code}_s"] = make_track(
            code, lambda f: progress(f"Recording {name} narration", 0.62 + 0.36 * f))
        timings[f"{code}_s"] = round(timings[f"{code}_s"], 2)
    else:
        # A course episode: every language now (the translation model is shared, so one after another; the voices overlap).
        translated: dict[str, tuple] = {}
        t_translate: dict[str, float] = {}
        for i, code in enumerate(langs):
            name = get_lang(code).name
            progress(f"Translating to {name}" if code != "en" else "Preparing English", 0.60 + 0.12 * i / len(langs))
            t1 = time.perf_counter()
            translated[code] = _translated_scenes(plan, code)
            t_translate[code] = time.perf_counter() - t1
        done_frac = {code: 0.0 for code in langs}

        def narrate_one(code: str) -> tuple[str, dict, float]:
            name = get_lang(code).name

            def report(f: float) -> None:
                done_frac[code] = f
                progress(f"Recording {name} narration", 0.72 + 0.26 * sum(done_frac.values()) / len(langs))

            t2 = time.perf_counter()
            scenes, translator = translated[code]
            track = _narrate(scenes, code, report, voice_lang="en" if translator == "untranslated" else code)
            track["translator"] = translator
            track["source_note"] = note
            return code, track, time.perf_counter() - t2

        with ThreadPoolExecutor(max_workers=min(len(langs), 4)) as pool:
            for code, track, secs in pool.map(narrate_one, langs):
                tracks[code] = track
                timings[f"{code}_s"] = round(t_translate[code] + secs, 2)
                (out_dir / f"captions_{code}.srt").write_text(_track_srt(track), encoding="utf-8")
        tracks = {code: tracks[code] for code in langs}          # keep the order the learner picked

    drafts = preview.drafts() if preview is not None else {}
    if drafts:                                         # the other languages as made while the video was written: watchable until their final version replaces them
        tracks = {c: tracks.get(c) or drafts[c] for c in langs if c in tracks or c in drafts}
    lesson = {
        "id": lesson_id,
        "concept": concept or (f"{focus} (PDF)" if focus else plan.title),
        "upload": upload,
        "focus": focus,
        "created": int(time.time()),
        "plan": plan.model_dump(),                    # English source plan: context for the tutor chat
        "documents": documents or [],
        "series": series,                             # set when this lesson is an episode of a playlist
        "review": review_notes,
        "facts": fact_report.summary() if fact_report else None,
        "quality": quality,
        "languages": tracks,
        "pending": [{"code": c, "name": get_lang(c).name, "native": get_lang(c).native} for c in rest],   # still being made, one by one
        "failed": [],
        "order": langs,
        "sources": sources,
        "timings": timings,
        "videos": {},
    }
    save_lesson(lesson)
    try:
        from . import studio
        if series is None:                     # a course episode gets them on demand (and episode 1 when the course is done): 5 x 14 tools would swamp the laptop
            studio.prebuild(lesson_id)         # flashcards, quiz, mind map... are written in the background from now on
    except Exception:  # noqa: BLE001  never let study tools break a finished lesson
        log.warning("could not queue the study tools for %s", lesson_id, exc_info=True)
    if rest:
        from . import jobs
        jobs.submit("langs", finish_languages, lesson_id, rest, make_track)      # the learner can already watch the first language
    progress("Ready", 1.0)
    log.info("Lesson %s built in %.1fs %s", lesson_id, time.perf_counter() - t0, timings)
    return lesson


def keep_shown(plan: LessonPlan, shown: list) -> int:
    """Put back the scenes the learner has already seen, matched by heading, in place of the reworked ones. Returns how many changed back."""
    key = lambda h: " ".join(str(h).lower().split())  # noqa: E731
    seen = {key(s.heading): s for s in shown}
    n = 0
    for i, s in enumerate(plan.scenes):
        old = seen.get(key(s.heading))
        if old is not None and old.model_dump() != s.model_dump():
            plan.scenes[i] = old
            n += 1
    return n


def resume_languages(lesson_id: str, progress: Progress = lambda s, p: None) -> dict:
    """After a restart: make the languages a saved lesson is still missing, from the English plan stored inside it. Each one is added as it is done."""
    lesson = load_lesson(lesson_id)
    codes = [p["code"] for p in lesson.get("pending", [])]
    if not codes or not lesson.get("plan"):
        return {"id": lesson_id}
    plan = LessonPlan.model_validate(lesson["plan"])
    note = source_note(lesson.get("sources", []))
    out_dir = LESSONS_DIR / lesson_id

    def make_track(code: str, report=lambda f: None) -> tuple[dict, float]:
        t1 = time.perf_counter()
        scenes, translator = _translated_scenes(plan, code)
        track = _narrate(scenes, code, report, voice_lang="en" if translator == "untranslated" else code)
        track["translator"] = translator
        track["source_note"] = note
        (out_dir / f"captions_{code}.srt").write_text(_track_srt(track), encoding="utf-8")
        return track, time.perf_counter() - t1

    log.info("Resuming lesson %s: %s", lesson_id, codes)
    return finish_languages(lesson_id, codes, make_track, progress)


_lesson_lock = threading.Lock()


LANG_WORKERS = int(__import__("os").getenv("LANG_WORKERS", "3"))       # languages in flight: the translator is shared (one batch at a time), the voices overlap


def finish_languages(lesson_id: str, codes: list[str], make_track, progress: Progress = lambda s, p: None) -> dict:
    """The other languages of a lesson, side by side: each is added to lesson.json as soon as it is ready, so the page shows it
    right away. Translation (GPU, shared model) takes turns behind its lock while the other languages' voices are being recorded."""
    def add(code: str, track: dict | None, secs: float, error: str = "") -> None:
        with _lesson_lock:
            lesson = load_lesson(lesson_id)
            lesson["pending"] = [p for p in lesson.get("pending", []) if p["code"] != code]
            if track is not None:
                lesson["languages"][code] = track
                lesson["languages"] = {c: lesson["languages"][c] for c in lesson.get("order", []) if c in lesson["languages"]}
                lesson["timings"][f"{code}_s"] = round(secs, 2)
            else:
                if lesson["languages"].get(code, {}).get("draft"):
                    lesson["languages"].pop(code)           # a draft of a language that then failed is not left behind
                lesson.setdefault("failed", []).append({"code": code, "name": get_lang(code).name, "error": error})
            save_lesson(lesson)

    def one(code: str) -> None:
        try:
            track, secs = make_track(code)
            add(code, track, secs)
        except Exception as e:  # noqa: BLE001  one language failing must not stop the rest
            log.error("lesson %s: language %s failed: %s", lesson_id, code, e, exc_info=True)
            add(code, None, 0.0, f"{type(e).__name__}: {e}")

    progress("Making " + ", ".join(get_lang(c).name for c in codes), 0.0)
    with ThreadPoolExecutor(max_workers=max(1, min(len(codes), LANG_WORKERS))) as pool:
        for k, _ in enumerate(pool.map(one, codes), 1):
            progress(f"{k} of {len(codes)} languages ready", k / max(len(codes), 1))
    progress("Ready", 1.0)
    return {"id": lesson_id}


def _scene_texts(scene) -> list[str]:
    """Every string of one scene that is translated (what _translated_scenes collects), for pre-caching."""
    s = scene.model_dump() if hasattr(scene, "model_dump") else scene
    return [s[f] for f in TEXT_FIELDS if s.get(f)] + [item for f in LIST_FIELDS for item in s.get(f, []) if item]


def _translated_scenes(plan: LessonPlan, lang: str) -> tuple[tuple[str, list[dict]], str]:
    """Translate every visible/spoken string in one batch, keeping the plan's structure."""
    scenes = [s.model_dump() for s in plan.scenes]
    for sc, ps in zip(scenes, plan.scenes):
        sc["tone"] = expression.tone_for_scene(ps.template, ps.heading)       # how the narrator should deliver this scene
    slots: list[tuple] = [("title",)]
    texts = [plan.title]
    for i, s in enumerate(scenes):
        for f in TEXT_FIELDS:
            slots.append((i, f)); texts.append(s[f])
        for f in LIST_FIELDS:
            for j, item in enumerate(s[f]):
                slots.append((i, f, j)); texts.append(item)
    translated, engine = translate_batch(texts, lang)
    reports: list[dict] | None = None
    if engine not in ("none", "untranslated") and lang != "en":
        # Catch the wrong script (mixed or Latin text) and a meaning that did not survive; repair what can be repaired.
        from . import fidelity
        from .translate import back_translate, retranslate_with_llm
        narration = {k for k, slot in enumerate(slots) if len(slot) == 2 and slot[1] == "narration"}
        translated, reports = fidelity.verify(
            texts, translated, lang, narration=narration,
            retranslate=lambda bad: retranslate_with_llm(bad, lang),
            back=(lambda t: back_translate(t, lang)) if config.BACKCHECK else None)
    title = plan.title
    for k, (slot, value) in enumerate(zip(slots, translated)):
        if slot == ("title",):
            title = value
        elif len(slot) == 2:
            scenes[slot[0]][slot[1]] = value
            if reports is not None and slot[1] == "narration":
                scenes[slot[0]]["fidelity"] = reports[k]
        else:
            scenes[slot[0]][slot[1]][slot[2]] = value
    return (title, scenes), engine


def _narrate(translated: tuple[str, list[dict]], lang: str, on_progress=lambda f: None, voice_lang: str | None = None) -> dict:
    """Narration first: each scene lasts exactly as long as its voice plus a short pause."""
    title, scenes = translated
    start = 0.0
    engines = set()
    for k, s in enumerate(scenes):
        on_progress(k / max(len(scenes), 1))
        speech = synthesize(s["narration"], voice_lang or lang, tone=s.get("tone"))
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
    path = lesson_path(lesson["id"])
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(lesson, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)                                          # pages that poll the lesson never read half a file


def load_lesson(lesson_id: str) -> dict:
    return json.loads(lesson_path(lesson_id).read_text(encoding="utf-8"))
