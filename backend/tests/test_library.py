import json
import sys
from pathlib import Path

from app.rag import search as S
from tests.fakes import FakeEmbedder, FakeReranker

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_library  # noqa: E402
from fetch_library import keep_record  # noqa: E402

WORDS = " ".join(f"word{i}" for i in range(250))


def test_keep_record_filters():
    assert keep_record(WORDS, "Physics")
    assert not keep_record("too short " * 20, "Physics")
    assert not keep_record(WORDS, "Mercury (disambiguation)")
    assert not keep_record(WORDS, "List of rivers of India")
    assert not keep_record("§ ¶ 1 2 3 4 ~ " * 100, "Noise")


def write_jsonl(path, rows):
    path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")


def test_build_small_library(tmp_path, monkeypatch):
    raw = tmp_path / "raw"
    raw.mkdir()
    write_jsonl(raw / "simple.jsonl", [
        {"doc_id": "w1", "source": "wikipedia-simple", "title": "Photosynthesis", "lang": "en", "url": "u1",
         "license": "CC BY-SA 4.0", "text": "Photosynthesis lets plants turn sunlight into glucose. " * 30},
        {"doc_id": "w2", "source": "wikipedia-simple", "title": "Moon", "lang": "en", "url": "u2",
         "license": "CC BY-SA 4.0", "text": "The Moon orbits the Earth every month. " * 30}])
    write_jsonl(raw / "indic.jsonl", [
        {"doc_id": "h1", "source": "wikipedia-hi", "title": "चंद्रमा", "lang": "hi", "url": "u3",
         "license": "CC BY-SA 4.0", "text": "चंद्रमा पृथ्वी का प्राकृतिक उपग्रह है। " * 30}])
    out = tmp_path / "index"
    n = build_library.build(raw, out, ["simple", "indic", "missing"], FakeEmbedder(), log=lambda *_: None)
    assert n > 2
    assert (tmp_path / "lexicon_en.txt").read_text(encoding="utf-8").split()[0] in {"photosynthesis", "the"}
    assert (tmp_path / "lexicon_hi.txt").exists()

    monkeypatch.setattr(S, "LIBRARY_DIR", tmp_path)
    S.clear_cache()
    try:
        hits = S.search("moon orbits earth", "library", embedder=FakeEmbedder(), reranker=FakeReranker())
        assert hits[0].chunk.title == "Moon" and hits[0].chunk.license == "CC BY-SA 4.0"
    finally:
        S.clear_cache()

    # Rebuilding swaps the index in place.
    assert build_library.build(raw, out, ["simple"], FakeEmbedder(), log=lambda *_: None) < n
    assert not (tmp_path / "index.new").exists() and not (tmp_path / "index.old").exists()


def test_ivfpq_path_is_searchable_and_read_only(tmp_path, monkeypatch):
    import pytest

    from app.rag.store import Collection
    monkeypatch.setattr(build_library, "NLIST", 2)
    monkeypatch.setattr(build_library, "PQ_BITS", 4)
    monkeypatch.setattr(build_library, "FLAT_BELOW", 0)
    raw = tmp_path / "raw"
    raw.mkdir()
    topics = ["moon orbit", "plant leaf", "river delta", "volcano magma", "atom nucleus", "cell membrane"]
    write_jsonl(raw / "simple.jsonl", [
        {"doc_id": f"w{i}", "source": "s", "title": f"T{i}", "lang": "en", "url": "", "license": "",
         "text": f"{topics[i % 6]} fact number {i}. " * 60} for i in range(60)])
    build_library.build(raw, tmp_path / "index", ["simple"], FakeEmbedder(), log=lambda *_: None)
    col = Collection(tmp_path / "index", FakeEmbedder())
    assert col.read_only and col.meta["index"].startswith("ivfpq")
    hits = col.vector(FakeEmbedder().query("volcano magma"), 5)
    assert hits and "volcano" in col.get([hits[0][0]])[0].text
    with pytest.raises(RuntimeError):
        col.delete_section("w1", 0)
    col.close()
