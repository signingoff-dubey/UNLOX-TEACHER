import json
import shutil
import subprocess
import wave
import zipfile

import pytest

from app import bundle, exports


def make_wav(path, seconds=0.5, rate=22050):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
        w.writeframes(b"\x00\x01" * int(rate * seconds))


@pytest.fixture()
def world(tmp_path, monkeypatch):
    lessons, audio = tmp_path / "lessons", tmp_path / "audio"
    (lessons / "abc123").mkdir(parents=True)
    audio.mkdir()
    for n in ("a.wav", "b.wav"):
        make_wav(audio / n)
    scene = lambda h, f, st: {"template": "bullets", "heading": h, "narration": f"{h} is explained here.", "items": ["one", "two"], "audio_url": f"/media/audio/{f}",
                              "speech_s": 0.5, "duration_s": 1.0, "start_s": st, "captions": [{"start": 0.0, "end": 0.5, "text": h}]}
    lesson = {"id": "abc123", "concept": "Vaccines", "created": 1, "languages": {"en": {"lang": "en", "name": "English", "native": "English", "title": "Vaccines",
              "scenes": [scene("First", "a.wav", 0.0), scene("Second", "b.wav", 1.0)], "duration_s": 2.0, "tts_engines": ["x"]}},
              "pending": [], "videos": {"x": "y"}, "timings": {}}
    (lessons / "abc123" / "lesson.json").write_text(json.dumps(lesson), encoding="utf-8")
    (lessons / "abc123" / "captions_en.srt").write_text("1\n00:00:00,000 --> 00:00:00,500\nFirst\n", encoding="utf-8")
    monkeypatch.setattr(exports, "LESSONS_DIR", lessons)
    monkeypatch.setattr(exports, "load_lesson", lambda i: json.loads((lessons / i / "lesson.json").read_text(encoding="utf-8")))
    monkeypatch.setattr(exports.config, "MEDIA_DIR", tmp_path)
    return lessons, audio


def test_subtitles_in_three_formats(world):
    srt, kind, name = exports.subtitles("abc123", "en", "srt")
    assert "00:00:00,000 -->" in srt and name.endswith(".srt")
    vtt, kind, _ = exports.subtitles("abc123", "en", "vtt")
    assert vtt.startswith("WEBVTT") and "00:00:00.500" in vtt and kind.startswith("text/vtt")
    txt, _, _ = exports.subtitles("abc123", "en", "txt")
    assert "First is explained here." in txt and "Second" in txt
    with pytest.raises(KeyError):
        exports.subtitles("abc123", "hi")


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is not installed")
def test_podcast_joins_the_narration_with_pauses(world):
    out = exports.podcast("abc123", "en", "wav")
    path = world[0] / "abc123" / "podcast_en.wav"
    assert out["url"].endswith("podcast_en.wav") and path.exists()
    with wave.open(str(path), "rb") as w:
        seconds = w.getnframes() / w.getframerate()
    assert 1.4 < seconds < 1.8                                           # two 0.5 s scenes and one 0.5 s pause
    assert not (world[0] / "abc123" / "_gap.wav").exists()
    with pytest.raises(ValueError):
        exports.podcast("abc123", "en", "ogg")


def test_a_bundle_round_trips_into_another_computer(world, tmp_path):
    lessons, audio = world
    zip_path = bundle.export_bundle("abc123", lessons, audio)
    with zipfile.ZipFile(zip_path) as z:
        names = set(z.namelist())
        assert {"manifest.json", "lesson.json", "player.html", "README.txt", "audio/a.wav", "audio/b.wav", "captions_en.srt"} <= names
        portable = json.loads(z.read("lesson.json"))
        assert portable["languages"]["en"]["scenes"][0]["audio_url"] == "audio/a.wav"          # relative, so player.html works from a folder
        html = z.read("player.html").decode("utf-8")
        assert "Vaccines" in html and "First is explained here." in html and "</script><script" not in html.replace("</script>\n<script", "")
    other_lessons, other_audio = tmp_path / "other_lessons", tmp_path / "other_audio"
    new_id = bundle.import_bundle(zip_path, other_lessons, other_audio)
    assert new_id == "abc123"                                                                     # free here, so it keeps its id
    imported = json.loads((other_lessons / new_id / "lesson.json").read_text(encoding="utf-8"))
    assert imported["languages"]["en"]["scenes"][1]["audio_url"] == "/media/audio/b.wav" and imported["imported"] is True
    assert (other_audio / "a.wav").exists() and (other_lessons / new_id / "captions_en.srt").exists()
    again = bundle.import_bundle(zip_path, other_lessons, other_audio)                            # importing twice never overwrites
    assert again != new_id and (other_lessons / again / "lesson.json").exists()


def test_import_refuses_what_is_not_a_bundle(tmp_path):
    bad = tmp_path / "bad.zip"
    bad.write_bytes(b"not a zip")
    with pytest.raises(bundle.BundleError):
        bundle.import_bundle(bad, tmp_path / "l", tmp_path / "a")
    evil = tmp_path / "evil.zip"
    with zipfile.ZipFile(evil, "w") as z:
        z.writestr("manifest.json", json.dumps({"format": "chanakya-bundle"}))
        z.writestr("lesson.json", json.dumps({"id": "zzzz9", "languages": {"en": {"scenes": []}}}))
        z.writestr("audio/../../evil.wav", b"x")
        z.writestr("../escape.txt", b"x")
    bundle.import_bundle(evil, tmp_path / "l", tmp_path / "a")
    assert not (tmp_path / "evil.wav").exists() and not (tmp_path.parent / "escape.txt").exists() and not list((tmp_path / "a").glob("*evil*"))
    half = tmp_path / "l" / "half"
    half.mkdir(parents=True)
    (half / "lesson.json").write_text(json.dumps({"id": "half", "building": True, "languages": {}}), encoding="utf-8")
    with pytest.raises(bundle.BundleError):
        bundle.export_bundle("half", tmp_path / "l", tmp_path / "a")
