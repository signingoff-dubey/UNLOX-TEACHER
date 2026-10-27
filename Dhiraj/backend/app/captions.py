"""Caption timing. The script and the audio length are both known, so each caption chunk
gets a share of the scene's speech time proportional to its length. No alignment model needed."""
from __future__ import annotations

from .tts import split_sentences

MAX_CHARS = 70


def chunk_text(text: str, max_chars: int = MAX_CHARS) -> list[str]:
    chunks: list[str] = []
    for sentence in split_sentences(text):
        line = ""
        for word in sentence.split():
            if line and len(line) + 1 + len(word) > max_chars:
                chunks.append(line)
                line = word
            else:
                line = f"{line} {word}".strip()
        if line:
            chunks.append(line)
    return chunks


def time_captions(text: str, speech_s: float) -> list[dict]:
    chunks = chunk_text(text)
    total = sum(len(c) for c in chunks) or 1
    t, out = 0.0, []
    for c in chunks:
        dur = speech_s * len(c) / total
        out.append({"start": round(t, 3), "end": round(t + dur, 3), "text": c})
        t += dur
    return out


def to_srt(cues: list[dict]) -> str:
    def ts(s: float) -> str:
        ms = int(round(s * 1000))
        return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}"
    return "\n".join(f"{i}\n{ts(c['start'])} --> {ts(c['end'])}\n{c['text']}\n"
                     for i, c in enumerate(cues, 1))
