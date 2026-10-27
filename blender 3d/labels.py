"""Text labels as PNG masks, shaped by Windows (correct Hindi, Telugu, Tamil... conjuncts)."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent


def render_labels(texts: dict[str, str], folder: Path) -> dict[str, tuple[str, float]]:
    """{object id: text} -> {object id: (png path, width / height)}."""
    texts = {k: v.strip() for k, v in texts.items() if v and v.strip()}
    if not texts:
        return {}
    folder.mkdir(parents=True, exist_ok=True)
    spec = [{"text": t, "out": str(folder / f"label_{i}.png")} for i, t in enumerate(texts.values())]
    spec_file = folder / "labels.json"
    spec_file.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    proc = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(HERE / "labels.ps1"),
                           "-Spec", str(spec_file)], capture_output=True, text=True, encoding="utf-8")
    if proc.returncode != 0:
        raise RuntimeError(f"label rendering failed: {proc.stderr.strip()[-500:]}")
    sizes = json.loads(proc.stdout.strip().splitlines()[-1])
    return {k: (s["out"], s["width"] / s["height"]) for k, s in zip(texts, sizes)}
