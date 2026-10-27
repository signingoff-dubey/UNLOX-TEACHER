"""HTTP API. Run with:  uvicorn app.main:app --port 8000  (from the backend folder)."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import logging
import threading
import time
from typing import Literal

import requests
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import config, homework, jobs, knowledge, routes_rag, stt, translate, tts, vision
from .exporter import export_mp4
from .ocr.ingest import upload_status
from .languages import LANGUAGES
from .metaworld import MetaSave
from .pipeline import LESSONS_DIR, build_lesson, load_lesson

config.MEDIA_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                    handlers=[logging.StreamHandler(), logging.FileHandler(config.MEDIA_DIR / "backend.log", encoding="utf-8")])  # the file is how to see why a step failed
log = logging.getLogger("chanakya")


def _warm_up() -> None:
    """Load the translation model, every voice, speech recognition and the language model now, so nobody waits for them later."""
    t0 = time.perf_counter()
    log.info("Warming up the models...")
    for name, fn in (("translation", translate.preload), ("voices", tts.preload), ("speech recognition", stt.preload)):
        try:
            fn()
        except Exception as e:  # noqa: BLE001  keep serving; each feature falls back on its own
            log.error("Warm-up of %s failed: %s", name, e)
    try:
        requests.post(f"{config.OLLAMA_URL}/api/chat", json={
            "model": config.OLLAMA_MODEL, "messages": [{"role": "user", "content": "hi"}], "stream": False,
            "keep_alive": config.OLLAMA_KEEP_ALIVE, "options": config.ollama_options({"num_predict": 1})}, timeout=120)
    except requests.RequestException as e:
        log.warning("Warm-up of the language model failed: %s", e)
    log.info("Models ready in %.1fs", time.perf_counter() - t0)


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        knowledge.KnowledgeBase.get()          # load the index once, not on the first lesson
    except Exception as e:
        log.error("Knowledge base failed to load: %s", e)
    if config.PRELOAD:
        threading.Thread(target=_warm_up, name="warm-up", daemon=True).start()      # the server answers while the models load
    try:
        from . import resume
        resume.on_startup()                                                       # finish what a crash or a dead battery cut short
    except Exception as e:  # noqa: BLE001  never stop the server over it
        log.error("Resume after restart failed: %s", e)
    yield


app = FastAPI(title="Chanakya", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])
app.include_router(routes_rag.router)        # PDF uploads + OCR status + hybrid search


class LessonRequest(BaseModel):
    # Either a concept, or an uploaded PDF (upload=<sha>) with an optional focus such as "chapter 4" or
    # "pages 120-135". A concept plus a PDF searches that PDF first. `documents` is the same thing as a list.
    concept: str = Field("", max_length=200)
    languages: list[str] = Field(default_factory=lambda: ["en"], min_length=1, max_length=9)
    level: Literal["beginner", "intermediate"] = "beginner"
    duration_s: int = Field(60, ge=30, le=240)     # target video length (over 90 s is planned in parts)
    upload: str | None = Field(None, pattern=r"^[0-9a-f]{16}$")
    focus: str = Field("", max_length=100)
    documents: list[str] = []
    images: list[str] = Field(default_factory=list, max_length=4)       # ids from POST /api/images
    mode: Literal["study", "homework", "explain", "revise"] = "explain"


class PlaylistRequest(BaseModel):
    topic: str = Field("", max_length=200)
    languages: list[str] = Field(default_factory=lambda: ["en"], min_length=1, max_length=9)
    level: Literal["beginner", "intermediate"] = "beginner"
    duration_s: int = Field(60, ge=30, le=240)        # per episode
    episodes: int = Field(0, ge=0, le=8)                # 0 = the AI decides: one video per concept (concepts.py)
    documents: list[str] = []
    images: list[str] = Field(default_factory=list, max_length=4)
    mode: Literal["study", "homework", "explain"] = "explain"


class PlaylistExportRequest(BaseModel):
    lang: str = "en"
    height: int = 720


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    lang: str = "en"                  # the language to answer in, or "auto": the language the question is written in
    watching: str = "en"              # the language of the video being watched
    time_s: float = 0                 # where the learner is in the video, so the tutor knows the current scene
    history: list[dict] = []          # [{"role": "user"|"assistant", "content": "..."}]
    speak: bool = False               # also return the reply as a voice clip (audio_url)


class ExportRequest(BaseModel):
    lang: str = "en"
    height: int = 720             # output height: 720 (default, 1280x720) or 1080 (1920x1080 "boost")


def _ollama_loaded() -> list[dict]:
    """Models currently in Ollama and how much of each sits in GPU memory (shows layer offload)."""
    try:
        ps = requests.get(f"{config.OLLAMA_URL}/api/ps", timeout=2).json().get("models", [])
        return [{"model": m["name"], "gpu_percent": round(100 * m.get("size_vram", 0) / max(m.get("size", 1), 1))} for m in ps]
    except requests.RequestException:
        return []


@app.get("/api/health")
def health() -> dict:
    try:
        tags = requests.get(f"{config.OLLAMA_URL}/api/tags", timeout=2).json()
        models = [m["name"] for m in tags.get("models", [])]
        ollama = {"ok": config.OLLAMA_MODEL in models, "models": models}
    except requests.RequestException:
        ollama = {"ok": False, "models": []}
    return {
        "llm": {"backend": config.LLM_BACKEND, "model": config.OLLAMA_MODEL, "ollama": ollama},
        "knowledge": knowledge.status(),
        "translate": {"backend": config.TRANSLATE_BACKEND,
                      "model": {"nllb": config.NLLB_MODEL, "indictrans2": config.INDICTRANS2_MODEL}.get(
                          config.TRANSLATE_BACKEND, config.OLLAMA_MODEL),
                      "toolkit_installed": importlib.util.find_spec(
                          "IndicTransToolkit" if config.TRANSLATE_BACKEND == "indictrans2" else "transformers") is not None},
        "tts": {"engine": config.TTS_ENGINE, "fallback": config.TTS_FALLBACK,
                "piper_voices": sorted(p.stem for p in tts.PIPER_DIR.glob("*.onnx")),
                "parler_installed": importlib.util.find_spec("parler_tts") is not None,
                "parler_model": config.PARLER_MODEL},
        "stt": {"model": config.STT_MODEL, "ready": stt.available()},
        "render": {"web_dir_ok": (config.WEB_DIR / "render.mjs").exists(),
                   "node_modules_ok": (config.WEB_DIR / "node_modules" / "@remotion" / "renderer").exists()},
        "device": config.torch_device(),
        "gpu": {"torch": config.torch_device(), "onnx_providers": config.ort_providers(),
                "ollama_num_gpu": config.OLLAMA_NUM_GPU if config.DEVICE != "cpu" else 0,
                "ollama_loaded": _ollama_loaded()},
    }


@app.get("/api/languages")
def languages() -> list[dict]:
    return [{"code": l.code, "name": l.name, "native": l.native, "piper": bool(l.piper_voice)}
            for l in LANGUAGES.values()]


@app.post("/api/lessons")
def create_lesson(req: LessonRequest) -> dict:
    unknown = [c for c in req.languages if c not in LANGUAGES]
    if unknown:
        raise HTTPException(400, f"Unsupported languages: {unknown}")
    concept = req.concept.strip()
    documents = ([req.upload] if req.upload else []) + [d for d in req.documents if d != req.upload]
    if len(concept) < 2 and not documents and not req.images:
        raise HTTPException(400, "Type a concept, or attach a PDF or a photo")
    for d in documents:
        if upload_status(d) is None:
            raise HTTPException(404, "That PDF upload was not found")
    return jobs.submit("lesson", build_lesson, concept, req.languages, req.level, req.duration_s, documents, None,
                       req.focus.strip(), req.images, req.mode, True)       # True: one language at a time


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str) -> dict:
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "No such job")
    return job


@app.get("/api/knowledge/search")
def knowledge_search(q: str, k: int = 5) -> list[dict]:
    """Inspect retrieval directly (handy for tuning and for showing judges how RAG works)."""
    kb = knowledge.KnowledgeBase.get()
    if not kb:
        raise HTTPException(404, "Knowledge base not built. Run backend/scripts/build_knowledge.py")
    return [p.__dict__ for p in kb.search(q, k=k)]


@app.get("/api/lessons")
def list_lessons(limit: int = 20) -> list[dict]:
    """Recent lessons, newest first (for the history list and demo backups)."""
    out = []
    for path in LESSONS_DIR.glob("*/lesson.json"):
        try:
            lesson = load_lesson(path.parent.name)
        except (ValueError, OSError):
            continue
        if lesson.get("series"):                    # episodes of a playlist are listed under the playlist, not here
            continue
        out.append({"id": lesson["id"], "concept": lesson["concept"], "created": lesson["created"],
                    "languages": list(lesson["languages"]), "videos": list(lesson["videos"])})
    return sorted(out, key=lambda l: l["created"], reverse=True)[:limit]


@app.get("/api/lessons/{lesson_id}")
def get_lesson(lesson_id: str) -> dict:
    try:
        return load_lesson(lesson_id)
    except (FileNotFoundError, ValueError):
        raise HTTPException(404, "No such lesson")


@app.post("/api/playlists")
def create_playlist(req: PlaylistRequest) -> dict:
    from . import playlist
    unknown = [c for c in req.languages if c not in LANGUAGES]
    if unknown:
        raise HTTPException(400, f"Unsupported languages: {unknown}")
    topic = req.topic.strip()
    if len(topic) < 2 and not req.documents and not req.images:
        raise HTTPException(400, "Type a topic, or attach a PDF or a photo")
    topic = topic or ("Homework help" if req.mode == "homework" else "Your document" if req.documents else "Your photo")
    pl = playlist.start(topic, req.languages, req.level, req.duration_s, req.episodes, req.documents, req.images, req.mode)
    job = jobs.submit("playlist", playlist.build, pl["id"])
    return {"playlist": pl, "job": job}


class HomeworkRequest(BaseModel):
    concept: str = Field("", max_length=200)
    documents: list[str] = []
    images: list[str] = Field(default_factory=list, max_length=4)


@app.post("/api/images")
async def upload_image(file: UploadFile = File(...)) -> dict:
    """A photo (homework, a textbook page, a diagram). llava reads it in a background job; the job result is its text and topic."""
    data = await file.read()
    try:
        sha = vision.save(data)
    except vision.ImageError as e:
        raise HTTPException(400, str(e))
    return jobs.submit("vision", vision.describe, sha)


@app.get("/api/images/{sha}")
def get_image(sha: str) -> FileResponse:
    try:
        return FileResponse(vision.path_of(sha))
    except (vision.ImageError, FileNotFoundError):
        raise HTTPException(404, "No such image")


@app.post("/api/homework")
def create_homework(req: HomeworkRequest) -> dict:
    """Start the Markdown answer file for a homework (PDF and/or photos). The student chose Homework: nothing guesses it."""
    if not req.documents and not req.images:
        raise HTTPException(400, "Attach the homework as a PDF or a photo")
    for d in req.documents:
        if upload_status(d) is None:
            raise HTTPException(404, "That PDF upload was not found")
    meta = homework.start(req.concept, req.documents, req.images)
    return {"homework": meta, "job": jobs.submit("homework", homework.build, meta["id"])}


@app.get("/api/homework")
def list_homework(limit: int = 20) -> list[dict]:
    return homework.list_all(limit)


@app.get("/api/homework/{hid}")
def get_homework(hid: str) -> dict:
    try:
        return homework.load(hid)
    except (FileNotFoundError, ValueError):
        raise HTTPException(404, "No such homework")


@app.get("/api/homework/{hid}/download")
def download_homework(hid: str) -> PlainTextResponse:
    try:
        meta = homework.load(hid)
    except (FileNotFoundError, ValueError):
        raise HTTPException(404, "No such homework")
    return PlainTextResponse(meta["markdown"], media_type="text/markdown; charset=utf-8",
                             headers={"Content-Disposition": f'attachment; filename="homework-answers-{hid}.md"'})


@app.get("/api/playlists")
def playlists(limit: int = 20) -> list[dict]:
    from . import playlist
    return playlist.list_playlists(limit)


@app.get("/api/playlists/{playlist_id}")
def get_playlist(playlist_id: str) -> dict:
    from . import playlist
    try:
        return playlist.load(playlist_id)
    except (FileNotFoundError, ValueError):
        raise HTTPException(404, "No such playlist")


@app.post("/api/playlists/{playlist_id}/export")
def export_playlist(playlist_id: str, req: PlaylistExportRequest) -> dict:
    from . import playlist
    if req.lang not in LANGUAGES:
        raise HTTPException(400, "Unsupported language")
    return jobs.submit("export", playlist.export_all, playlist_id, req.lang, 1080 if req.height == 1080 else 720)


@app.post("/api/lessons/{lesson_id}/chat")
def chat_about_lesson(lesson_id: str, req: ChatRequest) -> dict:
    from . import chat
    try:
        res = chat.ask(lesson_id, req.message.strip(), req.lang, req.time_s, req.history, req.watching)
        if req.speak:
            res["audio_url"] = chat.speak(res["reply"], res["lang"])
        return res
    except FileNotFoundError:
        raise HTTPException(404, "No such lesson")
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(503, str(e))


class StudioRequest(BaseModel):
    kind: Literal["flashcards", "quiz", "mindmap", "studyguide", "faq", "glossary", "timeline"]
    lang: str = "en"
    size: Literal["few", "standard", "more"] = "standard"
    difficulty: Literal["easy", "medium", "hard"] = "medium"


def _lang(code: str) -> str:
    if code not in LANGUAGES:
        raise HTTPException(400, f"Unsupported language '{code}'")
    return code


@app.get("/api/lessons/{lesson_id}/studio")
def study_status(lesson_id: str, lang: str = "en", size: Literal["few", "standard", "more"] = "standard",
                 difficulty: Literal["easy", "medium", "hard"] = "medium") -> dict:
    """Which study tools of this lesson are ready, and how far along the others are. Also starts building them in the background."""
    from . import studio
    get_lesson(lesson_id)
    studio.prebuild(lesson_id)
    return {"tools": studio.status(lesson_id, _lang(lang), size, difficulty)}


@app.post("/api/lessons/{lesson_id}/studio")
def study_request(lesson_id: str, req: StudioRequest) -> dict:
    """The learner wants this tool now: it jumps the build queue. Returns its state; poll GET .../studio for progress."""
    from . import studio
    get_lesson(lesson_id)
    return studio.request(lesson_id, req.kind, _lang(req.lang), req.size, req.difficulty)


@app.get("/api/lessons/{lesson_id}/studio/{kind}")
def study_result(lesson_id: str, kind: str, lang: str = "en", size: str = "standard", difficulty: str = "medium") -> dict:
    from . import studio
    get_lesson(lesson_id)
    res = studio.cached(lesson_id, kind, _lang(lang), size, difficulty) if kind in studio.KINDS else None
    if res is None:
        raise HTTPException(404, "Not made yet")
    return res


class RewardEvent(BaseModel):
    type: Literal["lesson_complete", "course_complete", "quiz_correct", "quiz_wrong", "card_known", "tutor_question",
                  "study_tool_open", "metaverse_points"]
    day: str = ""                          # the browser's local date, yyyy-mm-dd
    lesson_id: str = ""
    course_id: str = ""
    lang: str = "en"
    card_id: str = ""
    tool: str = ""
    first_try: bool = True
    points: int = Field(0, ge=0, le=100000)


@app.get("/api/rewards")
def rewards_state(day: str = "") -> dict:
    """Score, streak, level, daily goal, week and badges for the dashboard."""
    from . import rewards
    return rewards.summary(None, day)


@app.post("/api/rewards/event")
def rewards_event(ev: RewardEvent) -> dict:
    """One learning event (lesson finished, quiz answer, flashcard known...). Returns the XP gained and any new badges."""
    from . import rewards
    return rewards.award(ev.model_dump(), ev.day)


@app.get("/api/rewards/history")
def rewards_history(day: str = "", days: int = 126) -> list[dict]:
    """Per-day XP and activity, oldest first, for the progress page."""
    from . import rewards
    return rewards.history(day, days)


# ------------------------------------------------------------------ light exports, bundles, papers, teach-back
class PodcastRequest(BaseModel):
    lang: str = "en"
    format: Literal["mp3", "wav"] = "mp3"


@app.get("/api/lessons/{lesson_id}/subtitles")
def subtitles_download(lesson_id: str, lang: str = "en", fmt: Literal["srt", "vtt", "txt"] = "srt"):
    """The captions on their own (srt or vtt), or the narration as a plain transcript. Tiny files for slow connections."""
    from fastapi.responses import Response
    from . import exports
    get_lesson(lesson_id)
    try:
        text, kind, name = exports.subtitles(lesson_id, lang, fmt)
    except KeyError:
        raise HTTPException(404, f"This lesson has no '{lang}' version")
    return Response(text, media_type=kind, headers={"Content-Disposition": f'attachment; filename="{name}"'})


@app.post("/api/lessons/{lesson_id}/podcast")
def podcast(lesson_id: str, req: PodcastRequest) -> dict:
    """The narration of one language as one audio file (mp3 or wav). A job: poll /api/jobs/{id}; its result has the url."""
    from . import exports
    lesson = get_lesson(lesson_id)
    if req.lang not in lesson["languages"]:
        raise HTTPException(404, f"This lesson has no '{req.lang}' version")
    return jobs.submit("export", exports.podcast, lesson_id, req.lang, req.format)


class SayRequest(BaseModel):
    term: str = Field(max_length=120)
    lang: str = "en"


@app.post("/api/lessons/{lesson_id}/say")
def say(lesson_id: str, req: SayRequest) -> dict:
    """A spoken clip of one word or term in the lesson's language (the glossary's "hear it" button). Cached, so asking again is instant."""
    from . import exports
    get_lesson(lesson_id)
    _lang(req.lang)
    try:
        return exports.say_term(req.term, req.lang)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/lessons/{lesson_id}/bundle")
def bundle_download(lesson_id: str):
    """The whole lesson as one `.chanakya.zip`: the lesson, its narration, captions and a player that opens in any browser with no server."""
    from fastapi.responses import FileResponse
    from . import bundle
    get_lesson(lesson_id)
    try:
        path = bundle.export_bundle(lesson_id)
    except bundle.BundleError as e:
        raise HTTPException(409, str(e))
    return FileResponse(path, media_type="application/zip", filename=f"{lesson_id}.chanakya.zip")


@app.post("/api/bundle/import")
async def bundle_import(file: UploadFile = File(...)) -> dict:
    """Add a lesson from a `.chanakya.zip` made on another computer."""
    import tempfile
    from . import bundle
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        total = 0
        while chunk := await file.read(1 << 20):
            total += len(chunk)
            if total > bundle.MAX_BYTES:
                raise HTTPException(413, "The bundle is too large.")
            tmp.write(chunk)
    try:
        return {"id": bundle.import_bundle(Path(tmp.name))}
    except bundle.BundleError as e:
        raise HTTPException(400, str(e))
    finally:
        Path(tmp.name).unlink(missing_ok=True)


class PaperRequest(BaseModel):
    lesson_id: str
    mcq: int = Field(8, ge=0, le=25)
    short: int = Field(4, ge=0, le=25)
    long: int = Field(1, ge=0, le=25)
    level: Literal["beginner", "intermediate"] = "beginner"
    lang: str = "en"
    title: str = Field("", max_length=120)


@app.post("/api/papers")
def create_paper(req: PaperRequest) -> dict:
    """A question paper (or, with fewer questions, a worksheet) from a lesson. A job: its result is the paper; open /api/papers/{id}/html to print it."""
    from . import paper
    get_lesson(req.lesson_id)
    _lang(req.lang)
    if not (req.mcq + req.short + req.long):
        raise HTTPException(400, "Ask for at least one question")
    return jobs.submit("export", paper.generate, req.lesson_id, {"mcq": req.mcq, "short": req.short, "long": req.long}, req.level, req.lang, req.title)


@app.get("/api/papers/{paper_id}")
def get_paper(paper_id: str) -> dict:
    from . import paper
    try:
        return paper.load(paper_id)
    except (OSError, ValueError):
        raise HTTPException(404, "No such paper")


@app.get("/api/papers/{paper_id}/html")
def paper_html(paper_id: str, key: bool = False):
    """The printable page: the student's copy, or with key=true the teacher's copy with the answers."""
    from fastapi.responses import HTMLResponse
    from . import paper
    try:
        return HTMLResponse(paper.render_html(paper.load(paper_id), key))
    except (OSError, ValueError):
        raise HTTPException(404, "No such paper")


class TeachBackRequest(BaseModel):
    text: str = Field(max_length=4000)


@app.post("/api/lessons/{lesson_id}/teachback")
def teachback_check(lesson_id: str, req: TeachBackRequest) -> dict:
    """The learner explains the lesson back; returns a score and the key points they missed (embedding similarity, no judging model)."""
    from . import teachback
    get_lesson(lesson_id)
    try:
        return teachback.check(lesson_id, req.text)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/jobs")
def recent_jobs(limit: int = 20) -> list[dict]:
    """The latest jobs, kept across restarts (what was interrupted shows as such)."""
    from . import resume
    return resume.recent(max(1, min(limit, 100)))


class ReviewAnswer(BaseModel):
    card_id: str
    quality: int = Field(4, ge=0, le=5)
    day: str = ""


@app.get("/api/review/due")
def review_due(day: str = "", limit: int = 20) -> dict:
    """The cards (flashcards and quiz questions of every lesson) to review today, scheduled by SM-2."""
    from . import srs
    return srs.due(day or None, limit)


@app.get("/api/review/stats")
def review_stats(day: str = "") -> dict:
    from . import srs
    return srs.stats(day or None)


@app.post("/api/review/answer")
def review_answer(req: ReviewAnswer) -> dict:
    """How well the learner remembered a card (0 forgot ... 5 easy). Returns when it comes back."""
    from . import srs
    try:
        return srs.review(req.card_id, req.quality, req.day or None)
    except KeyError:
        raise HTTPException(404, "No such card")


class WeakAnswer(BaseModel):
    lesson_id: str
    question: str = Field(max_length=400)
    correct: bool
    day: str = ""


@app.post("/api/weak/answer")
def weak_answer(req: WeakAnswer) -> dict:
    """A quiz answer. Wrong ones are remembered per topic; right ones clear them. A "Revise" lesson then focuses on what is left."""
    from . import srs
    if req.correct:
        srs.log_right(req.lesson_id, req.question)
    else:
        try:
            topic = load_lesson(req.lesson_id).get("concept", "")
        except (OSError, ValueError):
            topic = ""
        srs.log_wrong(req.lesson_id, req.question, topic, req.day or None)
    return {"weak": srs.weak_spots()}


@app.get("/api/weak")
def weak_list() -> dict:
    from . import srs
    return {"weak": srs.weak_spots(8)}


class ProfileRequest(BaseModel):
    name: str | None = Field(None, max_length=30)
    age: int | None = Field(None, ge=0, le=120)


@app.get("/api/profile")
def get_profile() -> dict:
    from . import rewards
    return rewards.profile()


@app.post("/api/profile")
def set_profile(req: ProfileRequest) -> dict:
    """The learner's name and age. The age is used to pitch lessons and tutor answers; it stays on this computer."""
    from . import rewards
    return rewards.set_profile(req.name, req.age)


class GoalRequest(BaseModel):
    goal: int = 50
    name: str | None = Field(None, max_length=30)


@app.post("/api/rewards/goal")
def rewards_goal(req: GoalRequest) -> dict:
    from . import rewards
    try:
        state = rewards.set_goal(req.goal)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return rewards.set_name(req.name) if req.name else state


class MetaQuizRequest(BaseModel):
    lesson_ids: list[str] = Field(min_length=1, max_length=12)       # one video, or every episode of a course
    focus: str | None = None                                         # the video being watched
    lang: str = "en"
    title: str = Field("", max_length=80)


@app.post("/api/metaquiz")
def meta_quiz(req: MetaQuizRequest) -> dict:
    """A metaverse world built from everything the AI wrote for these videos (lessons + every study tool)."""
    from . import metaquiz
    for i in req.lesson_ids:
        get_lesson(i)
    if req.lang not in LANGUAGES:
        raise HTTPException(400, f"Unsupported language '{req.lang}'")
    return jobs.submit("studio", metaquiz.build_world, req.lesson_ids, req.focus, req.lang, req.title.strip())


class MetaWorldRequest(BaseModel):
    topic: str = Field(min_length=2, max_length=120)
    lang: str = "en"


@app.post("/api/metaworld")
def meta_world(req: MetaWorldRequest) -> dict:
    """A metaverse world about any topic, written by the local model (data only)."""
    from . import metaworld
    if req.lang not in LANGUAGES:
        raise HTTPException(400, f"Unsupported language '{req.lang}'")
    return jobs.submit("studio", metaworld.build, req.topic.strip(), req.lang)


@app.get("/api/metaverse/save")
def metaverse_save_get() -> dict:
    """Points and purchases of the metaverse wardrobe, kept here so they survive another address or a cleared browser."""
    from . import metaworld
    return metaworld.load_save() or {}


@app.post("/api/metaverse/save")
def metaverse_save_set(save: MetaSave) -> dict:
    from . import metaworld
    return metaworld.store_save(save)


@app.post("/api/stt")
async def speech_to_text(request: Request, lang: str = "auto", lesson_id: str | None = None) -> dict:
    """Push-to-talk: the raw recording (webm/wav/ogg) is the request body. Returns {text, lang, duration_s}."""
    if lang != "auto" and lang not in LANGUAGES:
        raise HTTPException(400, f"Unsupported language '{lang}'")
    vocabulary = ""
    if lesson_id:
        try:
            lesson = load_lesson(lesson_id)
            vocabulary = lesson["plan"]["title"] + ". " + ", ".join(
                i for s in lesson["plan"]["scenes"] for i in s.get("items", [])[:3])[:300]
        except (FileNotFoundError, ValueError, KeyError):
            pass
    body = await request.body()
    try:
        return await run_in_threadpool(stt.transcribe, body, lang, vocabulary)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except stt.SttUnavailable as e:
        raise HTTPException(503, str(e))


@app.post("/api/lessons/{lesson_id}/export")
def export(lesson_id: str, req: ExportRequest) -> dict:
    get_lesson(lesson_id)
    return jobs.submit("export", export_mp4, lesson_id, req.lang, req.height)


app.mount("/media", StaticFiles(directory=config.MEDIA_DIR), name="media")
config.FONTS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/fonts", StaticFiles(directory=config.FONTS_DIR), name="fonts")

# Serve the built frontend (web/dist) so the demo needs only this one server.
_DIST = config.WEB_DIR / "dist"
if _DIST.exists():
    app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        f = (_DIST / path).resolve()
        if path and f.is_file() and _DIST.resolve() in f.parents:
            return FileResponse(f)
        return FileResponse(_DIST / "index.html")
