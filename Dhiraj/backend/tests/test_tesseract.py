import fitz

from app.ocr.tesseract import ocr_image, ocr_many, tess_langs
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


def test_ocr_many_returns_every_page(tmp_path):
    items = [(i, _scan(tmp_path, f"Page number {i} about gravity.", f"p{i}.pdf")) for i in range(4)]
    got = dict(ocr_many(items, "eng", workers=2))
    assert set(got) == {0, 1, 2, 3}
    assert "gravity" in got[2].text.lower()
