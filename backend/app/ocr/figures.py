"""The pictures inside a PDF (diagrams, graphs, photos, formulas drawn as images), found and cut out so llava can say what they show.

Text extraction and OCR never see them: a diagram of the water cycle is a bitmap with a few labels, and a lesson about the water cycle
needs it. Page-sized pictures are skipped (that is a scanned page, OCR reads those), so are tiny ones (bullets, rules, icons) and pictures
that repeat on several pages (a logo in every header). Each picture is described once; the description is kept next to the page.
"""
from __future__ import annotations

import io
import logging
import os
from collections import Counter

import fitz

log = logging.getLogger(__name__)

MIN_SIDE = 100              # pixels: smaller pictures are decoration
MIN_COVER = 0.02            # of the page area (as drawn)
MAX_COVER = 0.80            # more than this is a scanned page, not a figure
REPEAT_PAGES = 3            # the same picture on this many pages is a logo or a header
MAX_FIGURES = int(os.getenv("PDF_MAX_FIGURES", "40"))
SEND_SIDE = 1024            # llava looks at about this many pixels anyway


def find(doc: fitz.Document) -> list[dict]:
    """Every figure of the document, first occurrence only: [{"page", "xref", "bbox", "w", "h"}] in page order."""
    found: list[dict] = []
    for pno in range(doc.page_count):
        page = doc[pno]
        area = abs(page.rect)
        if not area:
            continue
        try:
            infos = page.get_image_info(xrefs=True)
        except Exception as e:  # noqa: BLE001  a damaged page has no figures
            log.warning("could not list the images of page %d: %s", pno + 1, e)
            continue
        for info in infos:
            xref = info.get("xref")
            if not xref:
                continue
            box = fitz.Rect(info["bbox"]) & page.rect
            cover = abs(box) / area
            if min(info.get("width", 0), info.get("height", 0)) < MIN_SIDE or not MIN_COVER <= cover <= MAX_COVER:
                continue
            found.append({"page": pno + 1, "xref": xref, "bbox": [round(v, 1) for v in box], "w": info["width"], "h": info["height"]})
    pages_of = Counter(f["xref"] for f in found)
    seen: set[int] = set()
    out = []
    for f in found:
        if pages_of[f["xref"]] >= REPEAT_PAGES or f["xref"] in seen:
            continue
        seen.add(f["xref"])
        out.append(f)
    return out


def png_of(doc: fitz.Document, xref: int) -> bytes:
    """One picture as an RGB PNG no larger than SEND_SIDE (CMYK, transparency and huge scans handled)."""
    pix = fitz.Pixmap(doc, xref)
    if pix.alpha or (pix.colorspace is not None and pix.colorspace.n != 3):
        pix = fitz.Pixmap(fitz.csRGB, pix)
    from PIL import Image
    im = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
    im.thumbnail((SEND_SIDE, SEND_SIDE))
    out = io.BytesIO()
    im.save(out, "PNG")
    return out.getvalue()


def order(figs: list[dict], focus_pages: list[int]) -> list[dict]:
    """The pictures the student asked about first, then front to back; capped so a picture book cannot keep the GPU for an hour."""
    focus = set(focus_pages)
    return sorted(figs, key=lambda f: (f["page"] not in focus, f["page"]))[:MAX_FIGURES]
