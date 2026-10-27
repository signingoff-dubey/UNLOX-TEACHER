"""Light exports of a lesson for slow connections and shared classroom computers: subtitles on their own, a narration-only "podcast",
and a spoken clip for each glossary term. They reuse what a lesson already has (the captions and the voice recordings); nothing is
re-written by a model."""
from __future__ import annotations

import hashlib
import logging
import re
import subprocess
import wave
from pathlib import Path

from . import config
from .pipeline import LESSONS_DIR, load_lesson
from .tts import synthesize

log = logging.getLogger(__name__)
RATE = 22050


# ------------------------------------------------------------------ subtitles on their own
def _srt_time_to_vtt(srt: str) -> str:
    return "WEBVTT\n\n" + re.sub(r"(\d\d:\d\d:\d\d),(\d\d\d)", r"\1.\2", srt.replace("\r\n", "\n"))


def transcript(lesson: dict, lang: str) -> str:
    """The narration as plain text: the title, then each scene's heading and what is said."""
    track = lesson["languages"][lang]
    parts = [track["title"], ""]
    for s in track["scenes"]:
        parts += [s["heading"], s["narration"], ""]
    return "\n".join(parts).strip() + "\n"


def subtitles(lesson_id: str, lang: str, fmt: str = "srt") -> tuple[str, str, str]:
    """(text, media type, file name) of the lesson's subtitles in one language, as srt, vtt or a plain transcript."""
    lesson = load_lesson(lesson_id)
    if lang not in lesson["languages"]:
        raise KeyError(lang)
    srt_path = LESSONS_DIR / lesson_id / f"captions_{lang}.srt"
    if fmt == "txt":
        return transcript(lesson, lang), "text/plain; charset=utf-8", f"{lesson_id}_{lang}.txt"
    if srt_path.exists():
        srt = srt_path.read_text(encoding="utf-8")
    else:                                                  # a lesson still being made has no file yet: build it from the scenes
        from .captions import to_srt
        track = lesson["languages"][lang]
        srt = to_srt([{**c, "start": c["start"] + s["start_s"], "end": c["end"] + s["start_s"]} for s in track["scenes"] for c in s["captions"]])
    if fmt == "vtt":
        return _srt_time_to_vtt(srt), "text/vtt; charset=utf-8", f"{lesson_id}_{lang}.vtt"
    return srt, "application/x-subrip; charset=utf-8", f"{lesson_id}_{lang}.srt"


# ------------------------------------------------------------------ narration only
def _silence(path: Path, seconds: float) -> Path:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(RATE)
        w.writeframes(b"\x00\x00" * int(RATE * seconds))
    return path


def _audio_file(url: str) -> Path:
    name = Path(url).name
    return config.MEDIA_DIR / "audio" / name


def podcast(lesson_id: str, lang: str, fmt: str = "mp3", progress=lambda s, p: None) -> dict:
    """One audio file with the whole narration in order (a short pause between scenes). mp3 is small enough for a slow connection; wav needs no codec."""
    if fmt not in ("mp3", "wav"):
        raise ValueError("format must be mp3 or wav")
    lesson = load_lesson(lesson_id)
    track = lesson["languages"].get(lang)
    if track is None:
        raise KeyError(lang)
    files = [_audio_file(s["audio_url"]) for s in track["scenes"] if s.get("audio_url")]
    files = [f for f in files if f.exists()]
    if not files:
        raise ValueError("This lesson has no recorded narration to export")
    out_dir = LESSONS_DIR / lesson_id
    gap = _silence(out_dir / "_gap.wav", config.SCENE_PADDING_S)
    out = out_dir / f"podcast_{lang}.{fmt}"
    inputs: list[str] = []
    for k, f in enumerate(files):
        inputs += ["-i", str(f)] + (["-i", str(gap)] if k < len(files) - 1 else [])
    n = len(files) * 2 - 1
    chain = "".join(f"[{i}:a]aresample={RATE},aformat=channel_layouts=mono[a{i}];" for i in range(n)) + "".join(f"[a{i}]" for i in range(n)) + f"concat=n={n}:v=0:a=1[out]"
    codec = ["-c:a", "libmp3lame", "-b:a", "64k"] if fmt == "mp3" else ["-c:a", "pcm_s16le"]
    progress("Joining the narration", 0.3)
    proc = subprocess.run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", chain, "-map", "[out]", *codec, str(out)], capture_output=True, text=True)
    gap.unlink(missing_ok=True)
    if proc.returncode != 0:
        raise RuntimeError("ffmpeg failed: " + proc.stderr[-300:])
    progress("Done", 1.0)
    return {"url": f"/media/lessons/{lesson_id}/{out.name}", "seconds": round(track["duration_s"], 1), "bytes": out.stat().st_size}


# ------------------------------------------------------------------ hear a word
def say_term(term: str, lang: str) -> dict:
    """A spoken clip of one glossary term in the lesson's language. The voice engine caches it by text, so asking again is free."""
    term = " ".join(term.split())[:120]
    if not term:
        raise ValueError("Nothing to say")
    speech = synthesize(term, lang)
    return {"url": f"/media/audio/{speech.path.name}", "seconds": round(speech.duration_s, 2), "engine": speech.engine,
            "key": hashlib.sha1(f"{lang}|{term}".encode()).hexdigest()[:10]}
