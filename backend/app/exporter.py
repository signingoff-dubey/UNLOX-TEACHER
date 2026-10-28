"""MP4 export: hands one language track to the Remotion renderer (web/render.mjs)."""
from __future__ import annotations

import json
import logging
import os
import subprocess

from . import cache, config
from .pipeline import LESSONS_DIR, load_lesson, save_lesson

log = logging.getLogger(__name__)


def export_mp4(lesson_id: str, lang: str, height: int = 720, progress=lambda s, p: None) -> dict:
    lesson = load_lesson(lesson_id)
    if lang not in lesson["languages"]:
        raise ValueError(f"Lesson has no '{lang}' track")
    out_dir = LESSONS_DIR / lesson_id
    props_file = out_dir / f"props_{lang}.json"
    height = 1080 if height == 1080 else 720
    out_file = out_dir / f"lesson_{lang}_{height}p.mp4"
    url = f"/media/lessons/{lesson_id}/{out_file.name}"
    key = cache.key_of(lesson["languages"][lang], height)
    if cache.is_fresh(out_file, key):                                   # already rendered from this very track: no second render
        progress("Already made", 1.0)
        if lesson["videos"].get(lang if height == 720 else f"{lang}_{height}p") != url:
            lesson["videos"][lang if height == 720 else f"{lang}_{height}p"] = url
            save_lesson(lesson)
        return {"url": url, "cached": True}
    # The headless renderer fetches audio and fonts from this backend over localhost.
    props = {"track": lesson["languages"][lang], "assetBase": config.PUBLIC_BASE_URL}
    props_file.write_text(json.dumps(props, ensure_ascii=False), encoding="utf-8")

    cmd = [config.NODE_BIN, "render.mjs", str(props_file), str(out_file)]
    if config.RENDER_CONCURRENCY:
        cmd.append(config.RENDER_CONCURRENCY)
    progress("Rendering video", 0.02)
    proc = subprocess.Popen(cmd, cwd=config.WEB_DIR, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8", errors="replace",
                            env={**os.environ, "RENDER_HEIGHT": str(height)})
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
    cache.mark(out_file, key)

    lesson = load_lesson(lesson_id)                                     # re-read: a language may have been added while it rendered
    lesson["videos"][lang if height == 720 else f"{lang}_{height}p"] = url
    save_lesson(lesson)
    progress("Done", 1.0)
    return {"url": url}
