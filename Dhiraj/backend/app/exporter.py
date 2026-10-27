"""MP4 export: hands one language track to the Remotion renderer (web/render.mjs)."""
from __future__ import annotations

import json
import logging
import subprocess

from . import config
from .pipeline import LESSONS_DIR, load_lesson, save_lesson

log = logging.getLogger(__name__)


def export_mp4(lesson_id: str, lang: str, progress=lambda s, p: None) -> dict:
    lesson = load_lesson(lesson_id)
    if lang not in lesson["languages"]:
        raise ValueError(f"Lesson has no '{lang}' track")
    out_dir = LESSONS_DIR / lesson_id
    props_file = out_dir / f"props_{lang}.json"
    out_file = out_dir / f"lesson_{lang}.mp4"
    # The headless renderer fetches audio and fonts from this backend over localhost.
    props = {"track": lesson["languages"][lang], "assetBase": config.PUBLIC_BASE_URL}
    props_file.write_text(json.dumps(props, ensure_ascii=False), encoding="utf-8")

    cmd = [config.NODE_BIN, "render.mjs", str(props_file), str(out_file)]
    if config.RENDER_CONCURRENCY:
        cmd.append(config.RENDER_CONCURRENCY)
    progress("Rendering video", 0.02)
    proc = subprocess.Popen(cmd, cwd=config.WEB_DIR, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8", errors="replace")
    tail: list[str] = []
    assert proc.stdout
    for line in proc.stdout:
        line = line.strip()
        if line.startswith("PROGRESS "):
            stage, value = line[9:].split(" ", 1)
            progress(stage.replace("_", " ").capitalize(), float(value))
        elif line:
            tail = (tail + [line])[-20:]
    if proc.wait() != 0:
        raise RuntimeError("Render failed:\n" + "\n".join(tail))

    url = f"/media/lessons/{lesson_id}/{out_file.name}"
    lesson["videos"][lang] = url
    save_lesson(lesson)
    progress("Done", 1.0)
    return {"url": url}
