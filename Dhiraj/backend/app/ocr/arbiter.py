"""Combine the two OCR engines page by page.

Tesseract reads every scanned page first (fast, CPU). Unlimited-OCR reads it again later (GPU, better
layout, tables and equations). For each page we keep Unlimited-OCR's text unless it shows a known
failure: a repetition loop, a word count far from a confident Tesseract read, or the wrong script /
non-words. When the two disagree a lot, the page is marked low-confidence so retrieval trusts it less.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from rapidfuzz import fuzz

from .types import EngineResult

LOOP_NGRAM = 30
LOOP_TIMES = 3
CONFIDENT_TESS = 80.0
LENGTH_RATIO = (0.5, 2.0)
QUALITY_MARGIN = 0.10
LOW_AGREEMENT = 0.6

LATIN = (0x0041, 0x024F)
SCRIPTS: dict[str, tuple[int, int]] = {
    "en": LATIN,
    "hi": (0x0900, 0x097F), "mr": (0x0900, 0x097F),
    "bn": (0x0980, 0x09FF), "gu": (0x0A80, 0x0AFF), "ta": (0x0B80, 0x0BFF),
    "te": (0x0C00, 0x0C7F), "kn": (0x0C80, 0x0CFF), "ml": (0x0D00, 0x0D7F),
}

_WORD = re.compile(r"\w+", re.UNICODE)


@dataclass
class Decision:
    text: str
    engine: str
    agreement: float | None
    low_confidence: bool
    reason: str


def has_repetition_loop(text: str, n: int = LOOP_NGRAM, times: int = LOOP_TIMES) -> bool:
    """True if any run of n tokens appears `times` or more (the model got stuck repeating itself)."""
    tokens = text.split()
    if len(tokens) < n * times:
        return False
    counts: dict[tuple[str, ...], int] = {}
    for i in range(len(tokens) - n + 1):
        gram = tuple(tokens[i:i + n])
        counts[gram] = counts.get(gram, 0) + 1
        if counts[gram] >= times:
            return True
    return False


def script_validity(text: str, lang: str) -> float:
    """Share of letters that belong to the language's script (Latin also counts for Indic pages)."""
    lo, hi = SCRIPTS.get(lang, LATIN)
    letters = [ord(c) for c in text if c.isalpha()]
    if not letters:
        return 0.0
    ok = sum(1 for o in letters if lo <= o <= hi or (lang != "en" and LATIN[0] <= o <= LATIN[1]))
    return ok / len(letters)


def lexicon_hit_rate(text: str, lexicon: set[str] | None) -> float | None:
    if not lexicon:
        return None
    words = [w.lower() for w in _WORD.findall(text) if not w.isdigit()]
    if not words:
        return 0.0
    return sum(1 for w in words if w in lexicon) / len(words)


def _native_share(text: str, lang: str) -> float:
    """Share of letters in the language's own script (Latin transliteration of Hindi scores low)."""
    lo, hi = SCRIPTS.get(lang, LATIN)
    letters = [ord(c) for c in text if c.isalpha()]
    return sum(1 for o in letters if lo <= o <= hi) / len(letters) if letters else 0.0


def agreement(a: str, b: str) -> float:
    norm = lambda s: " ".join(s.lower().split())  # noqa: E731
    return fuzz.ratio(norm(a), norm(b)) / 100.0


def choose(tess: EngineResult, uni: EngineResult | None, lang: str,
           lexicon: set[str] | None = None) -> Decision:
    if uni is None or not uni.text.strip():
        return Decision(tess.text, "tesseract", None, False, "no Unlimited-OCR text yet")

    agree = agreement(tess.text, uni.text)
    low = agree < LOW_AGREEMENT

    def keep_tess(reason: str) -> Decision:
        return Decision(tess.text, "tesseract", agree, low, reason)

    if has_repetition_loop(uni.text):
        return keep_tess("Unlimited-OCR repetition loop")

    tess_words, uni_words = len(tess.text.split()), len(uni.text.split())
    if (tess.confidence or 0) >= CONFIDENT_TESS and tess_words:
        ratio = uni_words / tess_words
        if not LENGTH_RATIO[0] <= ratio <= LENGTH_RATIO[1]:
            return keep_tess(f"word count ratio {ratio:.2f} vs confident Tesseract")

    # For Indic pages, a transliterated (Latin) read is a wrong read, so compare native-script shares.
    measure = _native_share if lang != "en" else script_validity
    if measure(tess.text, lang) - measure(uni.text, lang) >= QUALITY_MARGIN:
        return keep_tess("Unlimited-OCR has the wrong script")

    t_lex, u_lex = lexicon_hit_rate(tess.text, lexicon), lexicon_hit_rate(uni.text, lexicon)
    if t_lex is not None and u_lex is not None and t_lex - u_lex >= QUALITY_MARGIN:
        return keep_tess("Unlimited-OCR has more non-words")

    return Decision(uni.text, "unlimited", agree, low, "Unlimited-OCR preferred")
