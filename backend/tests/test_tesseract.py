import fitz

from app.ocr.tesseract import dpi_for, ocr_image, ocr_pdf, tess_langs
from app.ocr.triage import render_png
from tests.pdfs import make_pdf


def test_tess_langs_maps_codes():
    assert tess_langs(None) == "eng"
    assert tess_langs("en") == "eng"
    assert tess_langs("hi") == "eng+hin"
    assert {tess_langs(c) for c in ["te", "ta", "ml", "mr", "kn", "bn", "gu"]} == {
        "eng+tel", "eng+tam", "eng+mal", "eng+mar", "eng+kan", "eng+ben", "eng+guj"}


def _scan(tmp_path, text, name="s.pdf"):
    with fitz.open(make_pdf(tmp_path, [("image", text)], name)) as doc:
        return render_png(doc[0], 300)


def test_ocr_reads_rendered_text(tmp_path):
    r = ocr_image(_scan(tmp_path, "The mitochondria is the powerhouse of the cell."), "eng")
    assert r.engine == "tesseract"
    assert "mitochondria" in r.text.lower()
    assert r.confidence > 60


def test_ocr_pdf_streams_every_page(tmp_path):
    pdf = make_pdf(tmp_path, [("image", f"Page number {i} about gravity.") for i in range(4)], "multi.pdf")
    got = dict(ocr_pdf(str(pdf), [1, 2, 3, 4], "eng", 200, workers=2))
    assert set(got) == {1, 2, 3, 4}
    assert "gravity" in got[3].text.lower()


def test_ocr_pdf_skips_blank_pages_and_reports_bad_ones(tmp_path):
    pdf = make_pdf(tmp_path, [("image", "Gravity pulls things down."), ""], "blank.pdf")
    got = dict(ocr_pdf(str(pdf), [1, 2, 99], "eng", 200, workers=2))
    assert got[2].text == "" and got[2].confidence == 100.0
    assert "gravity" in got[1].text.lower()
    assert isinstance(got[99], Exception)                 # a page that does not exist fails alone


def test_dpi_is_lower_for_latin_than_indic():
    assert dpi_for("en") < dpi_for("hi")
