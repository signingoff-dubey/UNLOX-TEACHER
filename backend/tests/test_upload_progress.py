import fitz
import pytest

from app.ocr import ingest as I
from app.rag import search as S
from tests.fakes import FakeEmbedder
from tests.pdfs import make_pdf

E = FakeEmbedder()
TEXT = ("Newton's laws describe motion. The first law is about inertia and objects at rest. "
        "Force equals mass times acceleration according to the second law. ") * 4


@pytest.fixture(autouse=True)
def dirs(tmp_path, monkeypatch):
    monkeypatch.setattr(S, "UPLOADS_DIR", tmp_path / "uploads")
    monkeypatch.setattr(S, "LIBRARY_DIR", tmp_path / "library")
    S.clear_cache()
    yield tmp_path
    I.wait_for_upgrades(10)
    S.clear_cache()


def run(path):
    steps = []
    I.ingest_pdf(path, "en", None, lambda s, p: steps.append((s, p)), unlimited=False, embedder=E, notes=False, describer=False)
    return steps


def digital_pdf(tmp_path, pages=24):
    doc = fitz.open()
    for i in range(pages):
        p = doc.new_page()
        p.insert_text((72, 80), f"Chapter {i // 8 + 1}: motion", fontsize=22, fontname="hebo")
        p.insert_textbox(fitz.Rect(72, 110, 520, 400), TEXT, fontsize=11)
    path = tmp_path / "digital.pdf"
    doc.save(path)
    return path


def test_the_bar_moves_on_every_page_and_never_goes_back(tmp_path):
    steps = run(digital_pdf(tmp_path))
    values = [p for _, p in steps]
    assert values == sorted(values) and values[-1] == 1.0                      # one continuous run, never backwards
    reading = [(s, p) for s, p in steps if s.startswith("Reading page")]
    assert len(reading) == 24 and reading[-1][0] == "Reading page 24 of 24"   # a step for every page, not one long silence
    assert reading[0][1] < 0.05 and abs(reading[-1][1] - I.READ_HI) < 1e-9
    assert len({round(p, 4) for p in values}) >= 24 + 3                       # reading steps, then indexing steps, then the end
    assert [s for s, _ in steps if s.startswith("Indexing")]                  # indexing reports too (it used to be silent)
    assert I.READ_HI <= min(p for s, p in steps if s.startswith("Indexing")) <= I.INDEX_HI    # a digital PDF has no OCR band: indexing follows reading


def test_a_pdf_with_scanned_pages_has_an_ocr_band_between_reading_and_indexing(tmp_path):
    path = make_pdf(tmp_path, [TEXT, ("image", "Kepler found that planets move in elliptical orbits."), TEXT,
                               ("image", "Chlorophyll absorbs red and blue light."), TEXT, ("image", "Volcanoes erupt when magma rises.")])
    steps = run(path)
    values = [p for _, p in steps]
    assert values == sorted(values) and values[-1] == 1.0
    ocr = [p for s, p in steps if s.startswith("OCR ")]
    assert ocr and all(I.READ_HI <= p <= I.OCR_HI for p in ocr) and abs(max(ocr) - I.OCR_HI) < 1e-9
    assert all(p >= I.OCR_HI for s, p in steps if s.startswith("Indexing"))


def test_reading_pages_as_markdown_is_fast_enough_for_a_big_book(tmp_path):
    import time
    path = digital_pdf(tmp_path, pages=40)
    t = time.perf_counter()
    run(path)
    assert time.perf_counter() - t < 40 * 0.25 + 5        # well under the 0.38 s a page it took before the fast path (generous: CI machines vary)
