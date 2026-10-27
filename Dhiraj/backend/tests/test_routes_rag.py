import fitz
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import jobs, routes_rag
from app.rag import search as S
from app.rag.chunker import Chunk
from app.rag.search import Hit


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(S, "UPLOADS_DIR", tmp_path / "uploads")
    calls = []
    monkeypatch.setattr(jobs, "submit", lambda kind, fn, *a: calls.append((kind, a)) or {"id": "job1", "kind": kind})
    app = FastAPI()
    app.include_router(routes_rag.router)
    c = TestClient(app)
    c.calls = calls
    return c


def pdf_bytes():
    doc = fitz.open()
    doc.new_page().insert_text((50, 50), "Hello photosynthesis " * 20)
    data = doc.tobytes()
    doc.close()
    return data


def test_upload_returns_job(client, tmp_path):
    r = client.post("/api/uploads", files={"file": ("bio.pdf", pdf_bytes(), "application/pdf")},
                    data={"lang": "hi", "focus": "chapter 2"})
    assert r.status_code == 200 and r.json()["id"] == "job1"
    kind, (path, lang, focus) = client.calls[0]
    assert kind == "upload" and lang == "hi" and focus == "chapter 2"
    assert path.name == "source.pdf" and path.exists()
    assert (path.parent / "name.txt").read_text(encoding="utf-8") == "bio"
    assert not list((tmp_path / "uploads").glob("tmp-*"))


def test_upload_rejects_non_pdf_with_400(client, tmp_path):
    r = client.post("/api/uploads", files={"file": ("x.pdf", b"not a pdf", "application/pdf")})
    assert r.status_code == 400 and "Not a readable PDF" in r.json()["detail"]
    assert not list((tmp_path / "uploads").glob("tmp-*"))


def test_upload_rejects_unknown_language(client):
    r = client.post("/api/uploads", files={"file": ("b.pdf", pdf_bytes(), "application/pdf")}, data={"lang": "xx"})
    assert r.status_code == 400


def test_status_404_and_400(client):
    assert client.get("/api/uploads/0123456789abcdef").status_code == 404
    assert client.get("/api/uploads/../../etc").status_code in (400, 404)
    assert client.get("/api/uploads/NOTHEX").status_code == 400


def test_search_returns_hits(client, monkeypatch):
    chunk = Chunk("d:0:0", "d", "Book", "Ch", 0, 3, 4, "en", "upload", "", "", "tesseract", False, "text")
    monkeypatch.setattr(routes_rag, "search", lambda q, scope, k: [Hit(chunk, 0.9, scope)])
    r = client.post("/api/search", json={"query": "cells", "scope": "library", "k": 3})
    assert r.status_code == 200
    assert r.json()[0]["page_start"] == 3 and r.json()[0]["score"] == 0.9 and r.json()[0]["scope"] == "library"


def test_search_bad_scope_400(client):
    assert client.post("/api/search", json={"query": "x", "scope": "everything"}).status_code == 400
