"""Expression for the narrator: the same voice, delivered differently where the words call for it.

A neutral voice reads a hook, a question, a warning and a recap in one flat way. Piper has no "emotion" switch, but it does take, per call, a speaking
speed (`length_scale`), how much the pitch and rhythm vary (`noise_scale`, `noise_w_scale`) and a volume. Each sentence is spoken with the settings
that fit it and followed by a pause that fits it:

* a question is a little slower, more varied, and gets a longer pause so the student can think;
* an exclamation or a hook is quicker, brighter and more varied;
* a very short sentence is slowed down and stressed ("Not quite."), the way a teacher would;
* a recap is calm and steady, a common mistake is serious;
* everything else is warm: slightly more varied than the flat default.

The settings are multipliers on the voice's own defaults, kept inside the range where the voices stay clean. Voices that take no such settings (the Indic
ONNX voices) get the pauses and a very small speed change; Parler-TTS gets the tone as a plain-language style instruction, which it follows.
"""
from __future__ import annotations

import re

from . import config

VERSION = 2                       # part of the cache key of every clip: changing the delivery makes new audio instead of reusing the flat old clips

# multipliers on the voice's defaults, and the pause after a sentence in seconds
TONES: dict[str, dict[str, float]] = {
    "warm": {"length": 0.97, "noise": 1.10, "noise_w": 1.05, "volume": 1.00, "gap": 0.16},
    "excited": {"length": 0.90, "noise": 1.30, "noise_w": 1.15, "volume": 1.06, "gap": 0.12},
    "curious": {"length": 1.02, "noise": 1.25, "noise_w": 1.10, "volume": 1.00, "gap": 0.24},
    "calm": {"length": 1.04, "noise": 0.85, "noise_w": 0.95, "volume": 0.97, "gap": 0.20},
    "serious": {"length": 1.06, "noise": 0.80, "noise_w": 0.90, "volume": 1.00, "gap": 0.22},
    "emphasis": {"length": 1.12, "noise": 1.20, "noise_w": 1.05, "volume": 1.05, "gap": 0.26},
}

# for Parler-TTS, which takes a description of how to speak
DESCRIPTIONS = {
    "warm": "in a warm, friendly and expressive teaching voice",
    "excited": "very expressive and animated, with an excited, happy tone",
    "curious": "with an inquisitive, curious tone and a slightly rising intonation",
    "calm": "calm, steady and reassuring",
    "serious": "serious, clear and careful",
    "emphasis": "slow and emphatic, stressing the words",
}

_HOOK = re.compile(r"^(imagine|what if|did you know|picture this|guess what|wow|look at|here'?s the|now watch)\b", re.I)
_WARN = re.compile(r"\b(mistake|wrong|careful|never|do not|don't|avoid|beware|myth)\b", re.I)


def tone_for_scene(template: str, heading: str = "") -> str:
    """The overall delivery of a scene, from what kind of scene it is."""
    if template == "title":
        return "excited"
    if template == "quiz":
        return "curious"
    if template == "summary":
        return "calm"
    if template == "compare" and re.search(r"mistake|myth|wrong", heading, re.I):
        return "serious"
    if template in ("code", "graph"):
        return "calm"
    return "warm"


def sentence_tone(sentence: str, scene_tone: str = "warm") -> str:
    """The delivery of one sentence: its punctuation and wording decide, the scene's tone is the default."""
    s = sentence.strip()
    words = len(s.split())
    if s.endswith("?"):
        return "curious"
    if s.endswith("!") or _HOOK.match(s):
        return "excited" if scene_tone != "serious" else "serious"
    if words <= 4 and words >= 1:
        return "emphasis"
    if _WARN.search(s) and scene_tone not in ("excited",):
        return "serious"
    return scene_tone


def pause_after(sentence: str, tone: str) -> float:
    """Seconds of silence after a sentence: longer after a question, a colon or a short stressed line."""
    gap = TONES[tone]["gap"]
    s = sentence.rstrip()
    if s.endswith(("?", ":")):
        gap += 0.10                                        # a question leaves room to think
    elif s.endswith((";", "…")):
        gap += 0.04
    return gap


def enabled() -> bool:
    return config.TTS_EXPRESSIVE


def key(tone: str | None) -> str:
    """What goes into a clip's cache key: the tone, and the version of the delivery rules."""
    return f"{tone or 'warm'}|x{VERSION}" if enabled() else "flat"
