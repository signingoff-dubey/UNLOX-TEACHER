import pytest

from app import config, knowledge
from app.ocr import ingest as I
from app.rag import search as S
from app.rag.chunker import Chunk
from app.rag.factcheck import unsupported
from app.rag.store import Collection
from tests.fakes import FakeEmbedder, FakeReranker
from tests.pdfs import make_pdf, set_toc

E, R = FakeEmbedder(), FakeReranker()


@pytest.fixture(autouse=True)
def dirs(tmp_path, monkeypatch):
    monkeypatch.setattr(S, "LIBRARY_DIR", tmp_path / "library")
    monkeypatch.setattr(S, "UPLOADS_DIR", tmp_path / "uploads")
    monkeypatch.setattr(config, "RAG_ENABLED", True)
    real = S.search
    monkeypatch.setattr(S, "search", lambda q, scope="library", k=8, **kw: real(q, scope, k, embedder=E, reranker=R))
    S.clear_cache()
    yield tmp_path
    I.wait_for_upgrades(10)
    S.clear_cache()


def lib_chunk(i, text):
    return Chunk(f"w{i}:0:0", f"w{i}", f"Article {i}", f"Article {i}", 0, 0, 0, "en", "wikipedia-simple",
                 "CC BY-SA 4.0", f"https://simple.wikipedia.org/{i}", "", False, text)


def test_retrieve_uses_new_search_when_library_exists(dirs):
    col = Collection(dirs / "library" / "index", E)
    col.add([lib_chunk(1, "Photosynthesis makes glucose from sunlight"), lib_chunk(2, "Rivers flow to the sea")])
    col.close()
    [p, *_] = knowledge.retrieve("photosynthesis glucose sunlight")
    assert (p.title, p.url, p.source) == ("Article 1", "https://simple.wikipedia.org/1", "wikipedia-simple")
    assert p.section == "" and 0 < p.score <= 1


def test_retrieve_upload_passages_cite_pages(dirs):
    path = make_pdf(dirs, ["Mitochondria are the powerhouse of the cell and make ATP energy. " * 12,
                           "Ribosomes make proteins inside the cell from amino acids. " * 12])
    info = I.ingest_pdf(path, "en", None, lambda s, p: None, unlimited=False, embedder=E)
    [p, *_] = knowledge.retrieve("mitochondria ATP energy", upload=info["sha"])
    assert p.source == "upload"
    assert p.section == "Pages 1–2, pp. 1–2"
    assert p.url == f"upload:{info['sha']}#page=1"


def test_retrieve_falls_back_to_kb(monkeypatch):
    class KB:
        def search(self, q):
            return [knowledge.Passage("Old", "", "text", "u", "wikipedia", 0.8)]
    monkeypatch.setattr(knowledge.KnowledgeBase, "get", classmethod(lambda cls: KB()))
    assert [p.title for p in knowledge.retrieve("anything")] == ["Old"]


def test_retrieve_never_raises(dirs, monkeypatch):
    Collection(dirs / "library" / "index", E).close()
    monkeypatch.setattr(S, "search", lambda *a, **k: (_ for _ in ()).throw(OSError("disk gone")))
    monkeypatch.setattr(knowledge.KnowledgeBase, "get", classmethod(lambda cls: None))
    assert knowledge.retrieve("x", upload="abc") == []


def test_pages_passages_reading_order(dirs):
    path = make_pdf(dirs, [f"Page {i} explains topic {i} in detail. " * 30 for i in range(1, 5)])
    set_toc(path, [[1, "Motion", 1], [1, "Energy", 3]])
    info = I.ingest_pdf(path, "en", None, lambda s, p: None, unlimited=False, embedder=E)
    got = knowledge.pages_passages(info["sha"], "pages 2-3")
    starts = [int(p.url.rsplit("=", 1)[1]) for p in got]
    assert got and starts == sorted(starts) and all(s <= 3 for s in starts)    # chunks overlapping pages 2-3
    energy = knowledge.pages_passages(info["sha"], "chapter 2")
    assert energy and all(p.section.startswith("Energy") for p in energy)
    assert knowledge.pages_passages(info["sha"], "")          # whole-book overview: the longest chapter
    assert knowledge.pages_passages("0000000000000000", "chapter 1") == []


def test_unsupported_flags_unrelated_sentence():
    passages = ["Plants make glucose by photosynthesis using sunlight and water."]
    sentences = ["Plants make glucose using sunlight.", "The Eiffel Tower is in Paris."]
    assert unsupported(sentences, passages, R) == [1]
    assert unsupported([], passages, R) == []
    assert unsupported(sentences, [], R) == [0, 1]


def test_rag_library_env_disables_library_path(dirs, monkeypatch):
    col = Collection(dirs / "library" / "index", E)
    col.add([lib_chunk(1, "Photosynthesis makes glucose from sunlight")])
    col.close()

    class KB:
        def search(self, q):
            return [knowledge.Passage("Old KB", "", "text", "u", "wikipedia", 0.8)]
    monkeypatch.setattr(knowledge.KnowledgeBase, "get", classmethod(lambda cls: KB()))
    monkeypatch.setenv("RAG_LIBRARY", "0")
    assert [p.title for p in knowledge.retrieve("photosynthesis")] == ["Old KB"]
    monkeypatch.setenv("RAG_LIBRARY", "1")
    assert knowledge.retrieve("photosynthesis")[0].title == "Article 1"
