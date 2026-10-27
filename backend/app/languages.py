"""Supported languages and the per-engine identifiers each one needs."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Language:
    code: str            # our short code, used in URLs and file names
    name: str            # English name
    native: str          # name in its own script (shown in the UI)
    flores: str          # IndicTrans2 / FLORES code
    piper_voice: str | None  # path inside rhasspy/piper-voices, without extension


LANGUAGES: dict[str, Language] = {
    l.code: l
    for l in [
        Language("en", "English", "English", "eng_Latn", "en/en_US/lessac/medium/en_US-lessac-medium"),
        Language("hi", "Hindi", "हिन्दी", "hin_Deva", "hi/hi_IN/priyamvada/medium/hi_IN-priyamvada-medium"),
        Language("te", "Telugu", "తెలుగు", "tel_Telu", "te/te_IN/padmavathi/medium/te_IN-padmavathi-medium"),
        Language("ml", "Malayalam", "മലയാളം", "mal_Mlym", "ml/ml_IN/meera/medium/ml_IN-meera-medium"),
        Language("mr", "Marathi", "मराठी", "mar_Deva", "mr/mr_IN/google/medium/mr_IN-google-medium"),
        # No Piper voices for kn/ta/gu: they use the CPU "indic" engine (AI4Bharat Indic-TTS ONNX), then Parler (GPU).
        Language("kn", "Kannada", "ಕನ್ನಡ", "kan_Knda", None),
        Language("ta", "Tamil", "தமிழ்", "tam_Taml", None),
        Language("bn", "Bengali", "বাংলা", "ben_Beng", "bn/bn_BD/google/medium/bn_BD-google-medium"),
        Language("gu", "Gujarati", "ગુજરાતી", "guj_Gujr", None),
    ]
}


# Measured speaking speed of each voice (English-plan words per second after translation). The lesson is sized for the
# slowest language picked, so no track runs past the length the learner asked for.
WORDS_PER_SEC = {"en": 2.7, "hi": 1.9, "mr": 1.8, "bn": 1.8, "gu": 1.8, "ta": 1.7, "kn": 1.7, "te": 1.6, "ml": 1.6}


def words_per_sec(codes: list[str]) -> float:
    return min((WORDS_PER_SEC.get(c, 1.8) for c in codes), default=2.3)


def get(code: str) -> Language:
    try:
        return LANGUAGES[code]
    except KeyError:
        raise ValueError(f"Unsupported language '{code}'. Choose from: {', '.join(LANGUAGES)}")
