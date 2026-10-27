"""HTTP API. Run with:  uvicorn app.main:app --port 8000  (from the backend folder)."""
from __future__ import annotations

import importlib.util
import logging
from typing import Literal

import requests
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import config, jobs, knowledge, routes_rag, stt, translate, tts
from .exporter import export_mp4
from .ocr.ingest import upload_status
from .languages import LANGUAGES
from .pipeline import LESSONS_DIR, build_lesson, load_lesson

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("visual-teacher")


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        knowledge.KnowledgeBase.get()          # load the index once, not on the first lesson
    except Exception as e:
        log.error("Knowledge base failed to load: %s", e)
    if config.PRELOAD:
        log.info("Preloading translation and voice models…")
        try:
            translate.preload()
        except Exception as e:  # keep serving; lessons fall back per language
            log.error("Translation model failed to preload: %s", e)
        tts.preload()
        log.info("Models ready")
    yield


app = FastAPI(title="Visual Teacher", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])
app.include_router(routes_rag.router)        # PDF uploads + OCR status + hybrid search


class LessonRequest(BaseModel):
    # Either a concept, or an uploaded PDF (upload=<sha>) with an optional focus such as "chapter 4" or
    # "pages 120-135". A concept plus a PDF searches that PDF first. `documents` is the same thing as a list.
    concept: str = Field("", max_length=200)
    languages: list[str] = Field(default_factory=lambda: ["en"], min_length=1, max_length=9)
    level: Literal["beginner", "intermediate"] = "beginner"
    duration_s: int = Field(60, ge=30, le=90)      # target video length
    upload: str | None = Field(None, pattern=r"^[0-9a-f]{16}$")
    focus: str = Field("", max_length=100)
    documents: list[str] = []


class PlaylistRequest(BaseModel):
    topic: str = Field(min_length=2, max_length=200)
    languages: list[str] = Field(default_factory=lambda: ["en"], min_length=1, max_length=9)
    level: Literal["beginner", "intermediate"] = "beginner"
    duration_s: int = Field(60, ge=30, le=90)         # per episode
    episodes: int = Field(5, ge=5, le=8)
    documents: list[str] = []


class PlaylistExportRequest(BaseModel):
    lang: str = "en"
    height: int = 720


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    lang: str = "en"
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
    if len(concept) < 2 and not documents:
        raise HTTPException(400, "Type a concept, or attach a PDF")
    for d in documents:
        if upload_status(d) is None:
            raise HTTPException(404, "That PDF upload was not found")
    return jobs.submit("lesson", build_lesson, concept, req.languages, req.level, req.duration_s, documents, None,
                       req.focus.strip())


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
    pl = playlist.start(req.topic.strip(), req.languages, req.level, req.duration_s, req.episodes, req.documents)
    job = jobs.submit("playlist", playlist.build, pl["id"])
    return {"playlist": pl, "job": job}


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
        res = chat.ask(lesson_id, req.message.strip(), req.lang, req.time_s, req.history)
        if req.speak:
            res["audio_url"] = chat.speak(res["reply"], req.lang)
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
