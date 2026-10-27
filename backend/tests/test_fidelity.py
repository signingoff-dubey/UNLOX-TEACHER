from app import fidelity

HINDI = "पौधे सूरज की रोशनी से अपना भोजन बनाते हैं।"
MIXED = "पौधे સૂરજ ની રોશની સે ભોજન બનાતે હૈં"                 # Hindi words in Gujarati letters: the "mixed scripts" failure
LATIN = "Poudhe suraj ki roshni se apna bhojan banate hain"      # Hindi written in Latin letters


def test_script_report_tells_the_scripts_apart():
    ok = fidelity.script_report(HINDI, "hi")
    assert ok["native"] > 0.95 and ok["foreign"] == 0
    bad = fidelity.script_report(MIXED, "hi")
    assert bad["foreign"] > 0.4
    assert fidelity.script_report(LATIN, "hi")["latin"] > 0.9


def test_script_ok_accepts_short_terms_and_rejects_wrong_script():
    assert fidelity.script_ok(HINDI, "hi")
    assert fidelity.script_ok("पौधे DNA बनाते हैं", "hi")             # a short Latin term inside a Hindi sentence is fine
    assert fidelity.script_ok("OK", "hi") and fidelity.script_ok("12", "hi")
    assert not fidelity.script_ok(MIXED, "hi")
    assert not fidelity.script_ok(LATIN, "hi")
    assert fidelity.script_ok(LATIN, "en")


def test_overlap_counts_surviving_content_words():
    assert fidelity.overlap("Plants make food from sunlight and water", "plants produce food using sunlight and water") > 0.7
    assert fidelity.overlap("Plants make food from sunlight and water", "the cat sat on a mat today") == 0.0
    assert fidelity.overlap("a b", "anything") == 1.0                       # nothing to compare


def test_verify_repairs_the_wrong_script_and_flags_a_lost_meaning():
    sources = ["Plants make food from sunlight, water and air.", "Plants make food from sunlight, water and air.", "Hello"]
    translated = [HINDI, MIXED, "नमस्ते"]
    calls = []

    def retranslate(bad):
        calls.append(bad)
        return [HINDI for _ in bad]

    out, reports = fidelity.verify(sources, translated, "hi", narration={0, 1},
                                   retranslate=retranslate, back=lambda t: ["plants make food from sunlight water air", "the weather is cold today in the city"])
    assert calls == [[sources[1]]]                                          # only the bad one was redone
    assert out[1] == HINDI and reports[1]["fixed"] and not reports[0]["fixed"]
    assert reports[0]["back"] > 0.8 and not reports[0]["low_back"]
    assert reports[1]["back"] == 0.0 and reports[1]["low_back"]              # the repaired text still does not mean the same
    assert reports[2]["back"] is None                                        # short texts are not back-translated
    s = fidelity.summary(reports)
    assert s["checked"] == 3 and s["repaired"] == 1 and s["low_back_translation"] == 1


def test_a_repair_that_fails_leaves_the_text_and_english_is_untouched():
    out, reports = fidelity.verify(["Some longer sentence to translate here."], [MIXED], "hi", retranslate=lambda bad: 1 / 0)
    assert out == [MIXED] and not reports[0]["fixed"]
    assert fidelity.verify(["a"], ["a"], "en")[1][0]["native"] == 1.0
