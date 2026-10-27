"""A digital PDF page as clean Markdown, and the check that tells a usable text layer from a broken one.

Why Markdown and not OCR for pages that have a text layer: the text layer IS the document's own text (measured on a test PDF with known
text: 98.8 to 100 % identical to the original, against 68 to 100 % for OCR, which also reads two columns across each other), it takes
milliseconds instead of about a second per page, and Markdown keeps what the planner and the search need: headings (`##`), lists, bold
and real table rows. OCR stays for scanned pages and for pages whose text layer is broken (`looks_garbled`).
"""
from __future__ import annotations

import logging
import re

import fitz

log = logging.getLogger(__name__)

_LIGATURES = {"ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl", "ﬅ": "st", "ﬆ": "st"}
_INVISIBLE = dict.fromkeys(map(ord, "­​‎‏⁠﻿"), None)        # soft hyphen, zero-width and direction marks
_PUA = re.compile("[-]")
_CAMEL = re.compile(r"[a-z][A-Z]")
_ODD = re.compile(r"[A-Za-z][\"\[\]{}^~|`][A-Za-z]|[A-Za-z]'(?![stdm]\b|re\b|ll\b|ve\b)[A-Za-z]")


def clean(text: str) -> str:
    """Ligatures to letters, invisible characters out, words broken at a line end joined, runs of blank lines shortened."""
    for k, v in _LIGATURES.items():
        text = text.replace(k, v)
    text = text.translate(_INVISIBLE).replace(" ", " ")
    text = re.sub(r"([a-z]{2,})-\n([a-z]{2,})", r"\1\2", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _letters(text: str) -> int:
    return sum(c.isalnum() for c in text)


def looks_garbled(text: str, lang: str | None = None) -> bool:
    """True when a text layer cannot be trusted: fonts without a proper Unicode mapping give (cid:12) marks, private-use boxes, or, for
    the old Indian-language fonts (Kruti Dev, Shusha ...), Latin gibberish such as 'ekWuhVj dksf'kdk' where Devanagari should be."""
    t = text.strip()
    if not t:
        return False
    if "(cid:" in t or t.count("�") + len(_PUA.findall(t)) > max(2, 0.02 * len(t)):
        return True
    words = [w for w in t.split() if len(w) >= 3]
    if len(words) >= 5:
        odd = sum(1 for w in words if _CAMEL.search(w) or _ODD.search(w))
        if odd / len(words) > 0.25:
            return True
    if lang and lang != "en" and len(t) >= 60:                  # the document is in an Indian language but the layer is Latin
        alpha = [c for c in t if c.isalpha()]
        if alpha and sum(c.isascii() for c in alpha) / len(alpha) > 0.85:
            from ..languages import LANGUAGES
            if lang in LANGUAGES:
                return True
    return False


def _tidy(md: str) -> str:
    md = re.sub(r"^(#{1,6}) \*\*(.+?)\*\*[ \t]*$", r"\1 \2", md, flags=re.M)          # "## **Title**" -> "## Title"
    md = re.sub(r"^(#{1,6}) (.+?)[ \t]+$", r"\1 \2", md, flags=re.M)
    return clean(md)


def page_markdown(doc: fitz.Document, index: int) -> str:
    """Page `index` (0-based) as Markdown. Falls back to the plain text layer when the converter is missing, fails, or lost words."""
    plain = clean(doc[index].get_text("text"))
    try:
        from pymupdf4llm.helpers.pymupdf_rag import to_markdown          # the rule-based converter: no OCR, no model, deterministic
    except ImportError:
        return plain
    try:
        md = _tidy(to_markdown(doc, pages=[index], ignore_images=True, write_images=False, show_progress=False, force_text=True))
    except Exception as e:  # noqa: BLE001  one odd page must not stop an upload
        log.warning("Markdown conversion of page %d failed (%s); using the plain text layer", index + 1, e)
        return plain
    if not md.strip() or _letters(md) < 0.9 * _letters(plain):           # it dropped text: the plain layer is the safer read
        return plain
    return md
