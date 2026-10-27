"""Did the translation come out right? Two cheap checks after translating, and a repair for what fails.

1. Script check: the letters of a translated text should be in the language's own script. A Hindi sentence full of Latin letters, or
   with Gujarati letters in it (the "mixed scripts" failure seen with small translation models), is caught here. The script ranges are
   the OCR module's.
2. Back-translation: the text is translated back to English and compared with the original (shared content words). Two models that
   disagree wildly means the meaning probably got lost. Only when the NLLB model is available (it translates in both directions).

A text that fails the script check is translated again with the local language model; the better of the two is kept. Nothing here is
a judge that can change a lesson's meaning: it only replaces text that is plainly in the wrong script.
"""
from __future__ import annotations

import logging
import re
from typing import Callable

from .ocr.arbiter import LATIN, SCRIPTS

log = logging.getLogger(__name__)

MIN_NATIVE = 0.6          # share of letters that must be in the language's own script (short Latin terms such as "DNA" are fine)
MAX_FOREIGN = 0.02        # share of letters in some other Indic script
MIN_BACK = 0.18           # shared content words with the back-translation
_WORD = re.compile(r"[a-z]{4,}")
_STOP = {"that", "this", "with", "from", "have", "your", "they", "their", "there", "which", "will", "when", "what", "into", "also", "more", "than", "then", "them", "these", "those", "about"}


def script_report(text: str, lang: str) -> dict:
    """Shares of the letters of `text` that are in the language's script, in Latin, and in another Indic script."""
    own = SCRIPTS.get(lang, LATIN)
    letters = [ord(c) for c in text if c.isalpha()]
    if not letters:
        return {"letters": 0, "native": 1.0, "latin": 0.0, "foreign": 0.0}
    indic_other = [r for code, r in SCRIPTS.items() if code not in (lang, "en") and r != own]
    native = sum(1 for o in letters if own[0] <= o <= own[1])
    latin = sum(1 for o in letters if LATIN[0] <= o <= LATIN[1])
    foreign = sum(1 for o in letters if any(a <= o <= b for a, b in indic_other))
    n = len(letters)
    return {"letters": n, "native": native / n, "latin": latin / n, "foreign": foreign / n}


def script_ok(text: str, lang: str) -> bool:
    if lang == "en":
        return True
    r = script_report(text, lang)
    if r["letters"] < 6:                                  # too short to judge ("OK", a number, a symbol)
        return True
    return r["native"] >= MIN_NATIVE and r["foreign"] <= MAX_FOREIGN


def _content(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if w not in _STOP}


def overlap(original: str, back: str) -> float:
    """Share of the original's content words that survive the round trip (0..1)."""
    a, b = _content(original), _content(back)
    return 1.0 if not a else len(a & b) / len(a)


def verify(sources: list[str], translated: list[str], lang: str, *, narration: set[int] | None = None,
           retranslate: Callable[[list[str]], list[str]] | None = None,
           back: Callable[[list[str]], list[str] | None] | None = None) -> tuple[list[str], list[dict]]:
    """Checks every translated text. `retranslate` re-does the ones in the wrong script; `back` translates texts back to English.
    Returns the (repaired) translations and one report per text: {native, foreign, fixed, back (or None), low_back}."""
    if lang == "en":
        return list(translated), [{"native": 1.0, "foreign": 0.0, "fixed": False, "back": None, "low_back": False} for _ in translated]
    out = list(translated)
    reports = [{"native": 0.0, "foreign": 0.0, "fixed": False, "back": None, "low_back": False} for _ in out]
    bad = [i for i, t in enumerate(out) if sources[i].strip() and not script_ok(t, lang)]
    if bad and retranslate:
        try:
            again = retranslate([sources[i] for i in bad])
        except Exception as e:  # noqa: BLE001  a repair that cannot run must not stop the lesson
            log.warning("retranslation of %d texts failed: %s", len(bad), e)
            again = []
        for i, new in zip(bad, again):
            if new.strip() and script_report(new, lang)["native"] > script_report(out[i], lang)["native"]:
                out[i] = new
                reports[i]["fixed"] = True
    for i, t in enumerate(out):
        r = script_report(t, lang)
        reports[i].update(native=round(r["native"], 3), foreign=round(r["foreign"], 3))
    idx = sorted(narration if narration is not None else range(len(out)))
    idx = [i for i in idx if i < len(out) and sources[i].strip() and len(sources[i]) > 30]
    if back and idx:
        try:
            round_trip = back([out[i] for i in idx])
        except Exception as e:  # noqa: BLE001
            log.warning("back-translation failed: %s", e)
            round_trip = None
        if round_trip:
            for i, bt in zip(idx, round_trip):
                score = overlap(sources[i], bt)
                reports[i]["back"] = round(score, 2)
                reports[i]["low_back"] = score < MIN_BACK
    return out, reports


def summary(reports: list[dict]) -> dict:
    """One line for the lesson: how many texts were checked, repaired, and still doubtful."""
    return {"checked": len(reports), "repaired": sum(1 for r in reports if r["fixed"]),
            "wrong_script": sum(1 for r in reports if r["native"] < MIN_NATIVE and r["native"] + r.get("foreign", 0) > 0 and not r["fixed"]),
            "low_back_translation": sum(1 for r in reports if r["low_back"])}
