"""HTTP API. Run with:  uvicorn app.main:app --port 8000  (from the backend folder)."""
from __future__ import annotations

import importlib.util
import logging
from typing import Literal

import requests
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import config, jobs, translate, tts
from .exporter import export_mp4
from .languages import LANGUAGES
from .pipeline import LESSONS_DIR, build_lesson, load_lesson

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("visual-teacher")


@asynccontextmanager
async def lifespan(_: FastAPI):
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


class LessonRequest(BaseModel):
    concept: str = Field(min_length=2, max_length=200)
    languages: list[str] = ["hi", "te"]
    level: Literal["beginner", "intermediate"] = "beginner"
    duration_s: int = Field(60, ge=30, le=90)      # target video length
    # Reserved for the document (RAG/OCR) service: ids of uploaded PDFs to teach from.
    documents: list[str] = []


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
        "translate": {"backend": config.TRANSLATE_BACKEND, "model": config.INDICTRANS2_MODEL,
                      "toolkit_installed": importlib.util.find_spec("IndicTransToolkit") is not None},
        "tts": {"engine": config.TTS_ENGINE, "fallback": config.TTS_FALLBACK,
                "piper_voices": sorted(p.stem for p in tts.PIPER_DIR.glob("*.onnx")),
                "parler_installed": importlib.util.find_spec("parler_tts") is not None,
                "parler_model": config.PARLER_MODEL},
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
    return jobs.submit("lesson", build_lesson, req.concept.strip(), req.languages, req.level, req.duration_s, req.documents)


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str) -> dict:
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "No such job")
    return job


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
