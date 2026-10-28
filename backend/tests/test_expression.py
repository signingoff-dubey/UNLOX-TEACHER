import wave

import pytest

from app import config, expression, tts


def test_each_kind_of_scene_has_its_own_delivery():
    assert expression.tone_for_scene("title", "Why DSA?") == "excited"
    assert expression.tone_for_scene("quiz", "Which one?") == "curious"
    assert expression.tone_for_scene("summary", "Summary") == "calm"
    assert expression.tone_for_scene("compare", "Common mistakes") == "serious" and expression.tone_for_scene("compare", "Arrays vs lists") == "warm"
    assert expression.tone_for_scene("code", "Bubble sort") == "calm" and expression.tone_for_scene("flow", "Steps") == "warm"


def test_a_sentence_is_delivered_the_way_its_words_call_for():
    assert expression.sentence_tone("How would you put them in order?", "warm") == "curious"
    assert expression.sentence_tone("Imagine you have a hundred toys!", "warm") == "excited"
    assert expression.sentence_tone("Imagine you have a hundred toys on the floor", "warm") == "excited"       # a hook, even without the mark
    assert expression.sentence_tone("Simple.", "warm") == "emphasis" and expression.sentence_tone("Not quite.", "calm") == "emphasis"
    assert expression.sentence_tone("Be careful: never reuse the same index twice.", "warm") == "serious"
    assert expression.sentence_tone("A stack keeps the last item you added on top of the pile.", "calm") == "calm"
    assert expression.sentence_tone("Wow, that was close!", "serious") == "serious"                            # a warning stays a warning


def test_pauses_follow_the_sentence_and_stay_short():
    q, plain = expression.pause_after("Why?", "curious"), expression.pause_after("It swaps them.", "warm")
    assert q > plain and 0.1 <= plain <= 0.4 and q <= 0.5                                                      # room to think after a question, never a long gap
    assert all(0.8 <= t["length"] <= 1.2 and 0.7 <= t["noise"] <= 1.4 for t in expression.TONES.values())    # inside the range where the voices stay clean


def test_the_cache_key_changes_with_the_tone_and_the_switch(monkeypatch):
    monkeypatch.setattr(config, "TTS_EXPRESSIVE", True)
    assert expression.key("excited") != expression.key("calm") and expression.key(None) == expression.key("warm")
    monkeypatch.setattr(config, "TTS_EXPRESSIVE", False)
    assert expression.key("excited") == "flat"                                                                 # switched off: one flat clip per text, as before


def test_expressive_speech_has_pauses_between_sentences(monkeypatch, tmp_path):
    from app.languages import get
    model = tts.PIPER_DIR / (tts.Path(get("en").piper_voice).name + ".onnx")
    if not model.exists():
        pytest.skip("the English Piper voice is not installed here")
    monkeypatch.setattr(tts, "AUDIO_DIR", tmp_path)
    text = "Imagine a hundred toys! How would you sort them? Simple."
    monkeypatch.setattr(config, "TTS_EXPRESSIVE", False)
    flat = tts.synthesize(text, "en")
    monkeypatch.setattr(config, "TTS_EXPRESSIVE", True)
    rich = tts.synthesize(text, "en", tone="warm")
    assert flat.path != rich.path and rich.duration_s > 1.0 and abs(rich.duration_s - flat.duration_s) < 0.35 * flat.duration_s   # different clip, about the same length
    with wave.open(str(rich.path), "rb") as w:
        assert w.getnchannels() == 1 and w.getsampwidth() == 2
    again = tts.synthesize(text, "en", tone="warm")
    assert again.path == rich.path                                                                             # cached per text and tone
    assert tts.synthesize(text, "en", tone="calm").path != rich.path


def test_an_engine_that_cannot_be_expressive_falls_back_to_flat_speech(monkeypatch, tmp_path):
    class Old:
        config = type("C", (), {"sample_rate": 22050})()

        def synthesize(self, *a, **k):
            raise TypeError("old piper")

    out = tmp_path / "x.wav"
    assert tts._piper_expressive(Old(), "Hello there. How are you?", "warm", out) is False and not out.exists()
