from app.ocr.arbiter import agreement, choose, has_repetition_loop, script_validity
from app.ocr.types import EngineResult

PARA = ("Plants make their own food by photosynthesis. Leaves contain chlorophyll which absorbs "
        "sunlight. Water comes from the roots and carbon dioxide enters through the stomata. ")
HINDI = "पौधे प्रकाश संश्लेषण द्वारा अपना भोजन बनाते हैं। पत्तियों में क्लोरोफिल होता है जो सूर्य का प्रकाश सोखता है। "
LONG = " ".join(f"{w}{i}" for i, w in enumerate(PARA.split() * 12))   # ~300 distinct words
HINDI_LATIN = "paudhe prakash sanshleshan dwara apna bhojan banate hain. pattiyon mein chlorophyll hota hai. "


def tess(text, conf=85.0):
    return EngineResult("tesseract", text, conf)


def uni(text):
    return EngineResult("unlimited", text, None)


def test_no_unlimited_keeps_tesseract():
    assert choose(tess(PARA), None, "en").engine == "tesseract"


def test_repetition_loop_rejected():
    loop = " ".join(f"w{i}" for i in range(40))
    d = choose(tess(LONG), uni(PARA + (loop + " ") * 10), "en")
    assert d.engine == "tesseract"
    assert "repetition" in d.reason
    assert has_repetition_loop((loop + " ") * 3)
    assert not has_repetition_loop(PARA * 2)


def test_length_mismatch_rejected_when_tess_confident():
    short = " ".join(LONG.split()[:100])
    d = choose(tess(LONG, 85), uni(short), "en")
    assert d.engine == "tesseract"
    assert "word count" in d.reason


def test_length_mismatch_ignored_when_tess_unsure():
    short = " ".join(LONG.split()[:100])
    assert choose(tess(LONG, 50), uni(short), "en").engine == "unlimited"


def test_wrong_script_loses():
    d = choose(tess(HINDI * 3, 70), uni(HINDI_LATIN * 3), "hi")
    assert d.engine == "tesseract"
    assert script_validity(HINDI, "hi") > 0.9


def test_default_prefers_unlimited():
    d = choose(tess(PARA.replace("chlorophyll", "chiorophyll")), uni(PARA), "en")
    assert d.engine == "unlimited"
    assert d.low_confidence is False


def test_low_agreement_flags_page():
    other = ("The French Revolution began in 1789 when citizens stormed the Bastille in Paris. "
             "It ended the monarchy and spread ideas of liberty and equality across Europe. ")
    d = choose(tess(PARA, 50), uni(other), "en")
    assert d.low_confidence is True
    assert agreement(PARA, other) < 0.6


def test_lexicon_hit_rate_counts_whole_indic_words():
    from app.ocr.arbiter import lexicon_hit_rate
    assert lexicon_hit_rate("प्रकाश संश्लेषण", {"प्रकाश", "संश्लेषण"}) == 1.0
    assert lexicon_hit_rate("प्रकाश xyz", {"प्रकाश"}) == 0.5
