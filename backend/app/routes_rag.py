"""HTTP routes for PDF uploads and retrieval. Mounted in main.py with app.include_router(router)."""
from __future__ import annotations

import os
import re
import shutil
import uuid
from dataclasses import asdict
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from . import jobs
from .languages import LANGUAGES
from .ocr.ingest import MAX_BYTES, UploadError, file_sha, ingest_pdf, upload_dir, upload_status, validate_pdf
from .rag import search as rag_search
from .rag.search import search

router = APIRouter()
_SHA = re.compile(r"^[0-9a-f]{16}$")


@router.post("/api/uploads")
def upload_pdf(file: UploadFile = File(...), lang: str | None = Form(None), focus: str | None = Form(None)) -> dict:
    if lang and lang not in LANGUAGES:
        raise HTTPException(400, f"Unsupported language '{lang}'")
    root = rag_search.UPLOADS_DIR
    root.mkdir(parents=True, exist_ok=True)
    tmp = root / f"tmp-{uuid.uuid4().hex}.pdf"
    try:
        size = 0
        with open(tmp, "wb") as out:
            while block := file.file.read(1 << 20):
                size += len(block)
                if size > MAX_BYTES:
                    raise HTTPException(413, "PDF is larger than 2 GB")
                out.write(block)
        try:
            validate_pdf(tmp)
        except UploadError as e:
            raise HTTPException(400, str(e)) from None
        dest = upload_dir(file_sha(tmp)) / "source.pdf"
        dest.parent.mkdir(parents=True, exist_ok=True)
        name = Path(file.filename or "").stem.strip()[:200]
        if name:
            (dest.parent / "name.txt").write_text(name, encoding="utf-8")
        if dest.exists():
            tmp.unlink()
        else:
            shutil.move(str(tmp), dest)
    finally:
        if tmp.exists():
            os.remove(tmp)
    return jobs.submit("upload", ingest_pdf, dest, lang, (focus or "").strip() or None)


@router.get("/api/uploads/{sha}")
def get_upload(sha: str) -> dict:
    if not _SHA.match(sha):
        raise HTTPException(400, "Bad upload id")
    status = upload_status(sha)
    if status is None:
        raise HTTPException(404, "No such upload")
    return status


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    scope: str = "library"
    k: int = Field(8, ge=1, le=50)


@router.post("/api/search")
def search_route(req: SearchRequest) -> list[dict]:
    try:
        rag_search.collection_path(req.scope.replace("both:", "upload:", 1))
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    return [{**asdict(h.chunk), "score": h.score, "scope": h.scope} for h in search(req.query, req.scope, req.k)]
