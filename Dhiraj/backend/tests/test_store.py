import numpy as np
import pytest

from app.rag.chunker import Chunk
from app.rag.store import Collection
from tests.fakes import FakeEmbedder


def mk(i, text, section=0, low=False):
    return Chunk(f"d:{section}:{i}", "d", "Book", f"S{section}", section, i + 1, i + 1, "en", "upload", "", "",
                 "tesseract", low, text)


@pytest.fixture
def col(tmp_path):
    c = Collection(tmp_path / "c", FakeEmbedder())
    c.add([mk(0, "Mitochondria produce energy for the cell."),
           mk(1, "The French Revolution began in 1789."),
           mk(2, "Photosynthesis happens in chloroplasts of leaves.", section=1)])
    return c


def test_keyword_finds_exact_term(col):
    assert col.keyword("chloroplasts", 5)[0][0] == "d:1:2"


def test_vector_finds_shared_words(col):
    q = FakeEmbedder().query("energy of the cell mitochondria")
    assert col.vector(q, 1)[0][0] == "d:0:0"


def test_get_round_trips_fields(col):
    [c] = col.get(["d:0:1"])
    assert c.text == "The French Revolution began in 1789." and c.page_start == 2


def test_delete_section_removes_from_both_indexes(col):
    col.delete_section("d", 1)
    assert col.keyword("chloroplasts", 5) == []
    q = FakeEmbedder().query("photosynthesis chloroplasts leaves")
    assert "d:1:2" not in [cid for cid, _ in col.vector(q, 5)]
    assert col.count() == 2


def test_reopen_keeps_data(col, tmp_path):
    again = Collection(tmp_path / "c", FakeEmbedder())
    assert again.count() == 3
    assert again.keyword("revolution", 1)[0][0] == "d:0:1"
    assert again.meta["embed_model"] == "fake-embedder"


def test_fts_query_with_quotes_and_symbols_does_not_raise(col):
    assert isinstance(col.keyword('what is "AC/DC"? (part-2) AND OR NOT *', 5), list)
    assert col.keyword("", 5) == []


def test_empty_collection_searches_return_empty(tmp_path):
    c = Collection(tmp_path / "e", FakeEmbedder())
    assert c.keyword("x", 3) == [] and c.vector(np.ones(384, np.float32), 3) == []


@pytest.mark.slow
def test_cross_script_query_still_hits_vector(tmp_path):
    from app.rag.embed import Embedder
    from app.rag.paths import EMBED_DIR
    e = Embedder(EMBED_DIR)
    c = Collection(tmp_path / "x", e)
    c.add([mk(0, "पौधे प्रकाश संश्लेषण द्वारा सूर्य के प्रकाश से अपना भोजन बनाते हैं।"),
           mk(1, "The Mughal emperor Akbar ruled from 1556."),
           mk(2, "Cricket is played with a bat and ball.")])
    hits = [cid for cid, _ in c.vector(e.query("photosynthesis in plants"), 3)]
    assert hits[0] == "d:0:0"


def test_re_adding_chunk_replaces_old_vector(col):
    col.add([mk(0, "Gravity pulls objects toward the earth.")])     # same id d:0:0, new text
    assert col.count() == 3
    assert col.index.ntotal == 3
    assert col.keyword("mitochondria", 5) == []
    assert col.get(["d:0:0"])[0].text.startswith("Gravity")


def test_fts_keeps_indic_words_whole(tmp_path):
    c = Collection(tmp_path / "hi", FakeEmbedder())
    c.add([mk(0, "प्रकाश संश्लेषण पौधों में होता है"), mk(1, "प्रकाश की गति बहुत तेज होती है")])
    terms = {r[0] for r in c.db.execute("SELECT term FROM chunks_fts_vocab")}
    assert {"प्रकाश", "संश्लेषण"} <= terms
    assert c.keyword("संश्लेषण", 5)[0][0] == "d:0:0"
    assert [cid for cid, _ in c.keyword("संश्लेषण", 5)] == ["d:0:0"]


def test_keyword_ignores_stopwords(col):
    assert col.keyword("why do we have the", 5) == []
    assert col.keyword("why does the cell need mitochondria", 5)[0][0] == "d:0:0"


def test_rebuild_fts_upgrades_old_tokenizer(tmp_path):
    import sqlite3
    path = tmp_path / "old"
    path.mkdir()
    db = sqlite3.connect(path / "chunks.sqlite")
    db.execute("CREATE VIRTUAL TABLE chunks_fts USING fts5(text, title, tokenize='unicode61 remove_diacritics 0')")
    db.commit()
    db.close()
    c = Collection(path, FakeEmbedder())
    c.add([mk(0, "प्रकाश संश्लेषण")])
    c.rebuild_fts()
    assert [cid for cid, _ in c.keyword("संश्लेषण", 5)] == ["d:0:0"]
    assert "tokenchars" in c.db.execute("SELECT sql FROM sqlite_master WHERE name='chunks_fts'").fetchone()[0]
