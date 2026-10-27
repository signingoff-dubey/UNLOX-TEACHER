"""HTTP API. Run with:  uvicorn app.main:app --port 8000  (from the backend folder)."""
from __future__ import annotations

import importlib.util
import logging
import threading

import requests
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import config, jobs, knowledge, routes_rag, translate, tts
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
    # The library path (hybrid search + reranker) costs ~7.5 s on first use; pay it in the background.
    threading.Thread(target=_warm_library, name="warm-library", daemon=True).start()
    if config.PRELOAD:
        log.info("Preloading translation and voice models…")
        try:
            translate.preload()
        except Exception as e:  # keep serving; lessons fall back per language
            log.error("Translation model failed to preload: %s", e)
        tts.preload()
        log.info("Models ready")
    yield


def _warm_library() -> None:
    """Load the e5 embedder and bge reranker before the first lesson, if the library index exists."""
    try:
        if not config.RAG_ENABLED or not knowledge._new_search_available(None):
            return
        from .rag.embed import shared_embedder
        from .rag.rerank import shared_reranker
        shared_embedder().query("warm up")
        shared_reranker().score("warm up", ["x"])
        log.info("Library search warmed up")
    except Exception as e:  # warm-up is an optimisation only
        log.warning("Library warm-up skipped: %s", e)


app = FastAPI(title="Visual Teacher", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])
app.include_router(routes_rag.router)        # PDF uploads + OCR status + hybrid search


class LessonRequest(BaseModel):
    # Either a concept, or an uploaded PDF (upload=<sha>) with an optional focus such as
    # "chapter 4" or "pages 120-135". A concept plus a PDF searches that PDF first.
    concept: str = Field("", max_length=200)
    languages: list[str] = ["hi", "te"]
    upload: str | None = Field(None, pattern=r"^[0-9a-f]{16}$")
    focus: str = Field("", max_length=100)


class ExportRequest(BaseModel):
    lang: str = "en"


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
        "render": {"web_dir_ok": (config.WEB_DIR / "render.mjs").exists(),
                   "node_modules_ok": (config.WEB_DIR / "node_modules" / "@remotion" / "renderer").exists()},
        "device": config.torch_device(),
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
    if len(concept) < 2 and not req.upload:
        raise HTTPException(400, "Type a concept, or attach a PDF")
    if req.upload and upload_status(req.upload) is None:
        raise HTTPException(404, "That PDF upload was not found")
    return jobs.submit("lesson", build_lesson, concept, req.languages, req.upload, req.focus.strip())


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
        out.append({"id": lesson["id"], "concept": lesson["concept"], "created": lesson["created"],
                    "languages": list(lesson["languages"]), "videos": list(lesson["videos"])})
    return sorted(out, key=lambda l: l["created"], reverse=True)[:limit]


@app.get("/api/lessons/{lesson_id}")
def get_lesson(lesson_id: str) -> dict:
    try:
        return load_lesson(lesson_id)
    except (FileNotFoundError, ValueError):
        raise HTTPException(404, "No such lesson")


@app.post("/api/lessons/{lesson_id}/export")
def export(lesson_id: str, req: ExportRequest) -> dict:
    get_lesson(lesson_id)
    return jobs.submit("export", export_mp4, lesson_id, req.lang)


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
