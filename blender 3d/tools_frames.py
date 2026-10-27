"""Contact sheet: one frame from the middle of each shot.  python tools_frames.py <run folder> <out.png>
Uses the ffmpeg that ships with Remotion (offline)."""
import json, subprocess, sys, tempfile
from pathlib import Path
from PIL import Image
run, dst = Path(sys.argv[1]), sys.argv[2]
ff = Path.home() / "visual-teacher/web/node_modules/@remotion/compositor-win32-x64-msvc/ffmpeg.exe"
plan = json.loads((run / "plan.json").read_text(encoding="utf-8"))
fps = json.loads((run / "job.json").read_text(encoding="utf-8"))["fps"]
tiles = []
with tempfile.TemporaryDirectory() as tmp:
    for i, s in enumerate(plan.get("rendered_shots") or plan["shots"]):
        t = (s["start"] + s["frames"] * 0.6) / fps
        png = Path(tmp) / f"{i}.png"
        subprocess.run([str(ff), "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(run / "lesson.mp4"), "-frames:v", "1", str(png)], check=True)
        im = Image.open(png).convert("RGB"); tiles.append((s["focus"], im.resize((im.width // 2, im.height // 2))))
w, h = tiles[0][1].size; cols = 3
sheet = Image.new("RGB", (w * cols, h * ((len(tiles) + cols - 1) // cols)))
for i, (_, im) in enumerate(tiles):
    sheet.paste(im, ((i % cols) * w, (i // cols) * h))
sheet.save(dst); print("shots:", [f for f, _ in tiles])
