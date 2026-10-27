import fitz

from app.ocr.triage import classify_page, read_toc, render_png
from app.ocr.types import TocEntry
from tests.pdfs import make_pdf, set_toc


def kinds(path):
    with fitz.open(path) as doc:
        return [classify_page(p) for p in doc]


def test_text_page_is_digital(tmp_path):
    assert kinds(make_pdf(tmp_path, ["Photosynthesis " * 40])) == ["digital"]


def test_image_page_is_scanned(tmp_path):
    assert kinds(make_pdf(tmp_path, ["image"])) == ["scanned"]


def test_garbage_text_layer_is_scanned(tmp_path):
    junk = "~#@!%^ ¬¬ ¦¦ " * 30
    assert kinds(make_pdf(tmp_path, [("image", "anything", junk)])) == ["scanned"]


def test_toc_is_one_based(tmp_path):
    p = make_pdf(tmp_path, ["a " * 200, "b " * 200])
    set_toc(p, [[1, "Ch 1", 1], [1, "Ch 2", 2]])
    with fitz.open(p) as doc:
        assert read_toc(doc) == [TocEntry(1, "Ch 1", 1), TocEntry(1, "Ch 2", 2)]


def test_render_png_is_png(tmp_path):
    with fitz.open(make_pdf(tmp_path, ["image"])) as doc:
        assert render_png(doc[0], 100)[:8] == b"\x89PNG\r\n\x1a\n"
