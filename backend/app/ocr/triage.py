"""Decide per page whether the PDF already has usable text (digital) or needs OCR (scanned)."""
from __future__ import annotations

import fitz

from .markdown import looks_garbled
from .types import PageKind, TocEntry

MIN_CHARS = 40           # fewer extractable characters than this -> treat as scanned (a title page, a table or a figure page with a short caption is digital)
MIN_LETTER_RATIO = 0.6   # junk text layers from bad embedded OCR are mostly symbols
IMAGE_COVER = 0.8        # a page-sized picture with little text is a scan
IMAGE_PAGE_MAX_CHARS = 600


def classify_page(page: fitz.Page, lang: str | None = None) -> PageKind:
    text = page.get_text("text").strip()
    chars = [c for c in text if not c.isspace()]
    if len(text) < MIN_CHARS or not chars:
        return "scanned"
    if looks_garbled(text, lang):              # a font without a Unicode mapping: the text layer says gibberish, the picture is right
        return "scanned"
    if sum(c.isalpha() for c in chars) / len(chars) < MIN_LETTER_RATIO:
        return "scanned"
    if len(text) < IMAGE_PAGE_MAX_CHARS and _image_cover(page) > IMAGE_COVER:
        return "scanned"
    return "digital"


def _image_cover(page: fitz.Page) -> float:
    area = abs(page.rect)
    if not area:
        return 0.0
    covered = 0.0
    for info in page.get_image_info():
        covered += abs(fitz.Rect(info["bbox"]) & page.rect)
    return min(covered / area, 1.0)


def read_toc(doc: fitz.Document) -> list[TocEntry]:
    return [TocEntry(level, title.strip(), page) for level, title, page, *_ in doc.get_toc(simple=True)
            if page >= 1]


def render_png(page: fitz.Page, dpi: int) -> bytes:
    return page.get_pixmap(dpi=dpi).tobytes("png")
