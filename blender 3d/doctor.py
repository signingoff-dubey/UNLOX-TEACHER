"""Check that this PC has everything the offline 3D lesson pipeline needs, and say how to fix what is missing.

    python doctor.py            (run with the Visual Teacher backend venv's python)
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from tools import HERE, backend_dir, blender_exe

OK, BAD, WARN = "OK  ", "MISS", "WARN"
rows: list[tuple[str, str, str]] = []


def check(name, fn):
    try:
        status, detail = fn()
    except Exception as e:  # noqa: BLE001
        status, detail = BAD, f"{type(e).__name__}: {e}"
    rows.append((status, name, detail))


def blender():
    exe = blender_exe()
    if not exe:
        return BAD, "install Blender 4.2+ (blender.org zip or installer; any edition works), or set BLENDER_EXE"
    probe = Path(tempfile.gettempdir()) / "blender3d_probe.txt"
    probe.unlink(missing_ok=True)
    expr = f"import bpy; open(r'{probe}','w').write(bpy.app.version_string)"
    subprocess.run([str(exe), "-b", "--factory-startup", "--python-expr", expr], capture_output=True, timeout=180)
    if not probe.exists():
        return BAD, f"{exe} did not run headless"
    return OK, f"Blender {probe.read_text()} headless via {exe.name}"


def backend():
    b = backend_dir()
    if not (b / "app" / "tts.py").exists():
        return BAD, f"Visual Teacher backend not found at {b} (set VT_BACKEND)"
    sys.path.insert(0, str(b))
    import app.config  # noqa: F401
    return OK, str(b)


def ollama():
    import requests
    from app import config
    tags = requests.get(f"{config.OLLAMA_URL}/api/tags", timeout=5).json()
    names = [m["name"] for m in tags.get("models", [])]
    if config.OLLAMA_MODEL not in names:
        return BAD, f"model {config.OLLAMA_MODEL} missing: run `ollama pull {config.OLLAMA_MODEL}` (once, online)"
    return OK, f"{config.OLLAMA_MODEL} at {config.OLLAMA_URL}"


def voices():
    from app import config
    have = sorted({p.name.split("-")[0].split("_")[0] for p in Path(config.PIPER_DIR).glob("*.onnx")})
    need = {"en", "hi", "te", "ta", "ml", "mr", "kn", "bn", "gu"}
    missing = sorted(need - set(have))
    detail = f"Piper voices: {', '.join(have) or 'none'}"
    if missing:
        detail += f"; no Piper voice for {', '.join(missing)} (the backend falls back to its Indic engine or silence)"
    return (OK if have else BAD), detail


def translator():
    from app import config
    name = getattr(config, "NLLB_MODEL", "facebook/nllb-200-distilled-600M")
    hub = Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface")) / "hub"
    found = list(hub.glob(f"models--{name.replace('/', '--')}*"))
    return (OK, f"{name} cached") if found else (WARN, f"{name} not in {hub}; translation will fail offline")


def labels():
    if os.name != "nt":
        return BAD, "label rendering uses Windows text shaping (labels.ps1)"
    fonts = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    if not list(fonts.glob("Nirmala*")):
        return WARN, "Nirmala UI font missing: Indian-language labels may not shape correctly"
    from labels import render_labels
    out = render_labels({"t": "प्रकाश संश्लेषण"}, Path(tempfile.mkdtemp()))
    png, aspect = out["t"]
    if aspect < 2:                                    # an empty label is only padding (about 2:1)
        return BAD, f"label rendered empty ({png})"
    return OK, f"Windows text shaping works (Hindi label {aspect:.1f}:1)"


def gpu():
    smi = shutil.which("nvidia-smi")
    if not smi:
        return WARN, "no NVIDIA GPU found; EEVEE still renders but slowly"
    q = subprocess.run([smi, "--query-gpu=name,memory.total,memory.used", "--format=csv,noheader"], capture_output=True, text=True)
    return OK, q.stdout.strip()


def disk():
    free = shutil.disk_usage(HERE).free / 1e9
    return (OK if free > 5 else WARN), f"{free:.0f} GB free"


for name, fn in (("Blender (headless)", blender), ("Backend venv", backend), ("Ollama + model", ollama),
                 ("Voices", voices), ("Translator (NLLB)", translator), ("Label shaping", labels),
                 ("GPU", gpu), ("Disk", disk)):
    check(name, fn)
w = max(len(n) for _, n, _ in rows)
for status, name, detail in rows:
    print(f"[{status}] {name:<{w}}  {detail}")
bad = [n for s, n, _ in rows if s == BAD]
print("\nready: everything needed is installed." if not bad else f"\nnot ready: fix {', '.join(bad)}")
sys.exit(1 if bad else 0)
