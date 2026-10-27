import pytest

from app.rag import search as S
from app.rag.chunker import Chunk
from app.rag.store import Collection
from tests.fakes import FakeEmbedder, FakeReranker

E, R = FakeEmbedder(), FakeReranker()


def mk(doc, i, text, low=False):
    return Chunk(f"{doc}:0:{i}", doc, doc, "S", 0, i + 1, i + 1, "en", doc, "", "", "", low, text)


@pytest.fixture
def dirs(tmp_path, monkeypatch):
    monkeypatch.setattr(S, "LIBRARY_DIR", tmp_path / "library")
    monkeypatch.setattr(S, "UPLOADS_DIR", tmp_path / "uploads")
    S.clear_cache()
    yield tmp_path
    S.clear_cache()


def fill(path, doc, texts):
    c = Collection(path, E)
    c.add([mk(doc, i, t) if isinstance(t, str) else mk(doc, i, t[0], low=t[1]) for i, t in enumerate(texts)])
    c.close()


def run(query, scope, k=8):
    return S.search(query, scope, k, embedder=E, reranker=R)


def test_rrf_orders_by_combined_rank():
    assert S.rrf([["a", "b"], ["b", "c"]])[0][0] == "b"


def test_upload_first_library_max_two(dirs):
    fill(dirs / "library" / "index", "lib", [f"photosynthesis in leaves fact {i}" for i in range(10)])
    fill(dirs / "uploads" / "abc" / "index", "up", [f"photosynthesis in leaves page {i}" for i in range(10)])
    hits = run("photosynthesis leaves", "both:abc", k=8)
    scopes = [h.scope for h in hits]
    assert len(hits) == 8
    assert scopes.count("library") <= 2
    assert scopes == sorted(scopes, key=lambda s: s != "upload:abc")


def test_low_confidence_downweighted(dirs):
    fill(dirs / "uploads" / "abc" / "index", "up", [("gravity pulls mass", True), ("gravity pulls mass", False)])
    hits = run("gravity pulls mass", "upload:abc")
    assert [h.chunk.low_confidence for h in hits] == [False, True]


def test_irrelevant_upload_returns_library_only(dirs):
    fill(dirs / "library" / "index", "lib", ["photosynthesis makes glucose in plants", "the moon orbits earth"])
    fill(dirs / "uploads" / "abc" / "index", "up", ["cricket bat and ball", "the wicket keeper"])
    hits = run("photosynthesis", "both:abc")
    assert hits and all(h.scope == "library" for h in hits)


def test_missing_collection_returns_empty(dirs):
    assert run("anything", "upload:nope") == []
    assert run("anything", "library") == []


def test_bad_scope_raises(dirs):
    with pytest.raises(ValueError):
        run("x", "everything")
