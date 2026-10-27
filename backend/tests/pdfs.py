"""Build small test PDFs: text pages, scanned (image-only) pages, and scans with a junk text layer."""
from __future__ import annotations

from pathlib import Path

import fitz

LOREM = ("Photosynthesis is the process by which green plants use sunlight, water and carbon dioxide "
         "to make glucose and release oxygen. It happens in the chloroplasts of leaf cells.")


def _image_of_text(text: str) -> bytes:
    """Render text onto a page, then return it as a PNG, i.e. a 'scan' with no text layer."""
    src = fitz.open()
    page = src.new_page()
    page.insert_textbox(fitz.Rect(50, 50, 545, 790), text, fontsize=14)
    png = page.get_pixmap(dpi=200).tobytes("png")
    src.close()
    return png


def make_pdf(tmp_path: Path, pages: list, name: str = "doc.pdf") -> Path:
    """pages: str -> text page; "image" -> scan of LOREM; ("image", text) -> scan of `text`;
    ("image", text, junk) -> scan of `text` with an invisible junk text layer on top."""
    doc = fitz.open()
    for spec in pages:
        page = doc.new_page()
        if isinstance(spec, str) and spec != "image":
            page.insert_textbox(fitz.Rect(50, 50, 545, 790), spec, fontsize=11)
            continue
        text = LOREM if spec == "image" else spec[1]
        page.insert_image(page.rect, stream=_image_of_text(text))
        if isinstance(spec, tuple) and len(spec) == 3:
            page.insert_textbox(fitz.Rect(50, 50, 545, 790), spec[2], fontsize=8, render_mode=3)
    path = tmp_path / name
    doc.save(path)
    doc.close()
    return path


def set_toc(path: Path, toc: list[list]) -> None:
    doc = fitz.open(path)
    doc.set_toc(toc)
    doc.saveIncr()
    doc.close()
