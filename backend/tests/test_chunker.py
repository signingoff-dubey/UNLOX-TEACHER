from app.ocr.types import TocEntry
from app.rag.chunker import chunk_section, sections_from_toc
from tests.fakes import FakeEmbedder

count = FakeEmbedder.count_tokens
META = {"doc_id": "d1", "title": "Biology", "lang": "en", "source": "upload", "license": "", "url": ""}


def sentences(n, start=0):
    return " ".join(f"Sentence {i} talks about cell number {i} and its parts." for i in range(start, start + n))


def test_chunks_respect_max_tokens_and_overlap():
    text = sentences(200)  # 2,000 words
    chunks = chunk_section(META, (0, "Cells", 1, 1), [(1, text, False)], count)
    assert len(chunks) > 3
    assert all(count(c.text) <= 350 for c in chunks)
    for a, b in zip(chunks, chunks[1:]):
        tail = a.text.split()[-40:]
        assert " ".join(tail) in b.text


def test_markdown_table_is_atomic():
    table = "\n".join(["| organ | function |", "|---|---|"] + [f"| organ{i} | does thing {i} |" for i in range(12)])
    text = sentences(30) + "\n\n" + table + "\n\n" + sentences(30, 30)
    chunks = chunk_section(META, (0, "Organs", 1, 1), [(1, text, False)], count, max_tokens=120, overlap=20)
    holders = [c for c in chunks if "| organ0 |" in c.text]
    assert len(holders) == 1
    assert "| organ11 |" in holders[0].text


def test_display_equation_is_atomic():
    eq = "$$\nE = mc^2\n+ a + b\n+ c + d\n+ e\n$$"
    text = sentences(20) + "\n\n" + eq + "\n\n" + sentences(20, 20)
    chunks = chunk_section(META, (0, "Energy", 1, 1), [(1, text, False)], count, max_tokens=60, overlap=10)
    holders = [c for c in chunks if "E = mc^2" in c.text]
    assert all("+ e" in c.text for c in holders)


def test_pages_tracked():
    chunks = chunk_section(META, (2, "Ch", 5, 6), [(5, sentences(40), False), (6, sentences(40, 40), False)], count)
    assert chunks[0].page_start == 5
    assert chunks[-1].page_end == 6
    assert chunks[0].chunk_id == "d1:2:0"
    assert chunks[0].section == "Ch" and chunks[0].section_idx == 2


def test_sections_fallback_windows():
    assert sections_from_toc(25, []) == [(0, "Pages 1–10", 1, 10), (1, "Pages 11–20", 11, 20),
                                         (2, "Pages 21–25", 21, 25)]


def test_sections_from_toc_top_level():
    toc = [TocEntry(1, "Intro", 1), TocEntry(2, "Sub", 2), TocEntry(1, "Cells", 4)]
    assert sections_from_toc(9, toc) == [(0, "Intro", 1, 3), (1, "Cells", 4, 9)]


def test_toc_starting_late_gets_front_matter_section():
    toc = [TocEntry(1, "Chapter 1", 5)]
    assert sections_from_toc(8, toc) == [(0, "Front matter", 1, 4), (1, "Chapter 1", 5, 8)]


def test_low_confidence_propagates():
    chunks = chunk_section(META, (0, "Ch", 1, 2), [(1, sentences(5), False), (2, sentences(5, 5), True)], count)
    assert chunks[-1].low_confidence is True
