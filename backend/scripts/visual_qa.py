"""Multimodal visual QA: look at the frames of a rendered lesson with a local vision model and flag weak scenes.

    python scripts/visual_qa.py <lesson_id> [lang] [--model moondream]

Needs the lesson exported as MP4 first (720p). For each scene it grabs a frame near the end of the narration,
asks the vision model what is on screen and whether it is a picture or only words, and compares neighbours.
A scene is flagged when it looks like text only, or when two neighbouring scenes are described almost the same.
Runs fully offline through Ollama (moondream ~1.7 GB, llava:7b ~4.7 GB).
"""
from __future__ import annotations

import base64
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import config                                 # noqa: E402
from app.pipeline import LESSONS_DIR, load_lesson       # noqa: E402


def frame_b64(video: Path, at: float) -> str:
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "f.jpg"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{at:.2f}", "-i", str(video), "-frames:v", "1",
                        "-vf", "scale=640:-1", str(out)], check=True)
        return base64.b64encode(out.read_bytes()).decode()


def ask(model: str, image: str, question: str) -> str:
    r = requests.post(f"{config.OLLAMA_URL}/api/chat", json={
        "model": model, "stream": False, "keep_alive": "0",
        "messages": [{"role": "user", "content": question, "images": [image]}],
        "options": {"temperature": 0.1, "num_predict": 80},
    }, timeout=180)
    r.raise_for_status()
    return r.json()["message"]["content"].strip()


def words(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]{3,}", s.lower()) if w not in {"the", "and", "with", "that", "this", "image", "shows", "picture"}}


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    model = sys.argv[sys.argv.index("--model") + 1] if "--model" in sys.argv else "moondream"
    lesson_id, lang = args[0], (args[1] if len(args) > 1 else "en")
    lesson = load_lesson(lesson_id)
    video = LESSONS_DIR / lesson_id / f"lesson_{lang}_720p.mp4"
    if not video.exists():
        sys.exit(f"Export the lesson first: {video} is missing")
    scenes = lesson["languages"][lang]["scenes"]
    seen: list[tuple[str, str]] = []
    for i, s in enumerate(scenes):
        img = frame_b64(video, s["start_s"] + s["speech_s"] * 0.9)
        what = ask(model, img, "Describe this slide in one short sentence: what is drawn on it?")
        gfx = ask(model, img, "Does this slide contain a chart, graph, diagram, code window or drawing, or only text? Answer with one word: picture or text.")
        seen.append((what, gfx))
        print(f"{i + 1}. [{s['template']:8}] {s['heading'][:30]:30} | {gfx.lower()[:12]:12} | {what[:110]}", flush=True)
    print("\nFlags:")
    flagged = 0
    for i, (what, gfx) in enumerate(seen):
        why = []
        template = scenes[i]["template"]
        if i and template == "title":
            why.append("a plain title card in the middle of the lesson")
        if "text" in gfx.lower() and "picture" not in gfx.lower() and template not in ("title", "summary", "quiz"):
            why.append("looks like text only")
        mine = words(what)
        if i and mine:
            best = max((len(mine & words(seen[j][0])) / max(len(mine | words(seen[j][0])), 1), j) for j in range(i))
            if best[0] >= 0.3:
                why.append(f"looks like scene {best[1] + 1} ({best[0]:.0%} of the description in common)")
        if why:
            flagged += 1
            print(f"  scene {i + 1} ({scenes[i]['template']}): " + "; ".join(why))
    print("  none" if not flagged else f"  {flagged} scene(s) flagged")


if __name__ == "__main__":
    main()
