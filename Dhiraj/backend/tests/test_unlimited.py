import fitz
import pytest

from app.ocr.unlimited import remove_det, split_pages


def test_remove_det_strips_markers_and_images():
    raw = ("<|det|>title [1,2,3,4]<|/det|>Heading\n"
           "<|det|>image [5,6,7,8]<|/det|>x\n"
           "<|det|>text [9,9,9,9]<|/det|>Body line")
    assert remove_det(raw) == "Heading\n\nBody line"


def test_remove_det_keeps_continuation_lines_in_block():
    raw = "<|det|>text [1,1,1,1]<|/det|>line one\nline two\n<|det|>table [2,2,2,2]<|/det|>| a | b |"
    assert remove_det(raw) == "line one\nline two\n\n| a | b |"


def test_split_pages_on_page_markers():
    assert split_pages("<PAGE>\nfirst\n<PAGE>\nsecond", 2) == ["first", "second"]
    assert split_pages("only one page", 2) is None


@pytest.mark.gpu
def test_ocr_reads_rendered_text(tmp_path):
    from app.ocr.triage import render_png
    from app.ocr.unlimited import UnlimitedOCR
    from tests.pdfs import make_pdf

    with fitz.open(make_pdf(tmp_path, [("image", "The mitochondria is the powerhouse of the cell.")])) as doc:
        png = render_png(doc[0], 200)
    ocr = UnlimitedOCR()
    ocr.load()
    try:
        [result] = ocr.ocr([png])
    finally:
        ocr.unload()
    assert result.engine == "unlimited"
    assert "mitochondria" in result.text.lower()
