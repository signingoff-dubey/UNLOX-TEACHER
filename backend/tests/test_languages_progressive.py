from app import pipeline
from app.languages import detect_text_language


def test_typed_text_language_comes_from_its_script():
    assert detect_text_language("चुंबक लोहे को क्यों खींचता है?") == "hi"
    assert detect_text_language("चुंबक लोहे को क्यों खींचता है?", prefer="mr") == "mr"
    assert detect_text_language("అయస్కాంతం ఇనుమును ఎందుకు ఆకర్షిస్తుంది?") == "te"
    assert detect_text_language("காந்தம் இரும்பை ஏன் ஈர்க்கிறது?") == "ta"
    assert detect_text_language("Why do magnets attract iron?") == "en"


def test_languages_are_added_one_by_one_and_a_failure_does_not_stop_the_rest(monkeypatch):
    lesson = {"id": "abc", "languages": {"en": {"lang": "en"}}, "pending": [{"code": "hi"}, {"code": "te"}, {"code": "ta"}],
              "failed": [], "order": ["en", "hi", "te", "ta"], "timings": {}}
    saved = []
    monkeypatch.setattr(pipeline, "load_lesson", lambda _id: lesson)
    monkeypatch.setattr(pipeline, "save_lesson", lambda l: saved.append((list(l["languages"]), [p["code"] for p in l["pending"]])))

    def make_track(code, report=lambda f: None):
        if code == "te":
            raise RuntimeError("voice missing")
        return {"lang": code}, 1.5

    pipeline.finish_languages("abc", ["hi", "te", "ta"], make_track)
    assert saved[0] == (["en", "hi"], ["te", "ta"])             # Hindi is visible as soon as it is done
    assert list(lesson["languages"]) == ["en", "hi", "ta"]       # order the learner picked, Telugu skipped
    assert lesson["pending"] == [] and lesson["failed"][0]["code"] == "te"
