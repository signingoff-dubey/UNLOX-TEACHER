"""Structure-aware chunking: sections from the TOC, ~350-token chunks with 50-token overlap.

Text is cut into pieces (sentences; whole tables and display equations), and pieces are packed into
chunks. Tables and equations are never split. Each piece remembers its page, so every chunk knows
which pages it came from, and the OCR upgrade can re-chunk one section at a time.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

from ..ocr.types import TocEntry

MAX_TOKENS = 350
OVERLAP = 50
WINDOW_PAGES = 10

_SENTENCE_END = re.compile(r"(?<=[.!?।॥])\s+")


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    title: str
    section: str
    section_idx: int
    page_start: int
    page_end: int
    lang: str
    source: str
    license: str
    url: str
    engine: str
    low_confidence: bool
    text: str


@dataclass
class _Piece:
    text: str
    tokens: int
    page: int
    low: bool
    para: int        # paragraph id: pieces of one paragraph are joined with spaces
    atomic: bool


Section = tuple[int, str, int, int]   # (section_idx, title, first_page, last_page)


def sections_from_toc(n_pages: int, toc: list[TocEntry]) -> list[Section]:
    tops = sorted({(e.page, e.title) for e in toc if e.level == 1 and 1 <= e.page <= n_pages})
    if not tops:
        return [(i, f"Pages {a}–{min(a + WINDOW_PAGES - 1, n_pages)}", a, min(a + WINDOW_PAGES - 1, n_pages))
                for i, a in enumerate(range(1, n_pages + 1, WINDOW_PAGES))]
    starts = [(1, "Front matter")] if tops[0][0] > 1 else []
    starts += tops
    out = []
    for i, (page, title) in enumerate(starts):
        end = starts[i + 1][0] - 1 if i + 1 < len(starts) else n_pages
        out.append((len(out), title, page, max(end, page)))
    return out


def _blocks(text: str) -> list[tuple[str, bool]]:
    """Split page text into (block, atomic) pairs: paragraphs, whole tables, whole display equations."""
    out: list[tuple[str, bool]] = []
    para: list[str] = []
    lines = text.splitlines()
    i = 0

    def flush() -> None:
        if para:
            out.append((" ".join(para), False))
            para.clear()

    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("|"):
            flush()
            table = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                table.append(lines[i].strip())
                i += 1
            out.append(("\n".join(table), True))
            continue
        if line.startswith("$$") or line.startswith("\\["):
            flush()
            close = "$$" if line.startswith("$$") else "\\]"
            eq = [line]
            closed = len(line) > 2 and line.endswith(close)
            i += 1
            while i < len(lines) and not closed:
                eq.append(lines[i].strip())
                closed = lines[i].strip().endswith(close)
                i += 1
            out.append(("\n".join(eq), True))
            continue
        if not line:
            flush()
        else:
            para.append(line)
        i += 1
    flush()
    return out


def _pieces(pages: list[tuple[int, str, bool]], count: Callable[[str], int]) -> list[_Piece]:
    pieces: list[_Piece] = []
    para_id = 0
    for page, text, low in pages:
        for block, atomic in _blocks(text):
            para_id += 1
            parts = [block] if atomic else [s for s in _SENTENCE_END.split(block) if s.strip()]
            for part in parts:
                pieces.append(_Piece(part.strip(), count(part), page, low, para_id, atomic))
    return pieces


def _join(pieces: list[_Piece]) -> str:
    out, last = [], None
    for p in pieces:
        if last is not None:
            out.append(" " if p.para == last.para and not p.atomic else "\n\n")
        out.append(p.text)
        last = p
    return "".join(out)


def chunk_section(doc_meta: dict, section: Section, pages: list[tuple[int, str, bool]],
                  count_tokens: Callable[[str], int], max_tokens: int = MAX_TOKENS,
                  overlap: int = OVERLAP) -> list[Chunk]:
    idx, title, _, _ = section
    pieces = _pieces(pages, count_tokens)
    groups: list[list[_Piece]] = []
    cur: list[_Piece] = []
    cur_tokens = 0
    fresh = 0                      # pieces in `cur` that are not carried-over overlap
    for p in pieces:
        if cur and fresh and cur_tokens + p.tokens > max_tokens:
            groups.append(cur)
            carry: list[_Piece] = []
            carried = 0
            for q in reversed(cur):
                if q.atomic or carried >= overlap or carried + q.tokens > max_tokens // 2:
                    break
                carry.insert(0, q)
                carried += q.tokens
            cur, cur_tokens, fresh = carry, carried, 0
            if cur_tokens + p.tokens > max_tokens:      # overlap would overflow: drop it
                cur, cur_tokens = [], 0
        cur.append(p)
        cur_tokens += p.tokens
        fresh += 1
    if cur and fresh:
        groups.append(cur)

    return [
        Chunk(
            chunk_id=f"{doc_meta['doc_id']}:{idx}:{i}", doc_id=doc_meta["doc_id"], title=doc_meta["title"],
            section=title, section_idx=idx, page_start=min(p.page for p in g), page_end=max(p.page for p in g),
            lang=doc_meta.get("lang", ""), source=doc_meta.get("source", ""),
            license=doc_meta.get("license", ""), url=doc_meta.get("url", ""),
            engine=doc_meta.get("engine", ""), low_confidence=any(p.low for p in g), text=_join(g),
        )
        for i, g in enumerate(groups)
    ]
