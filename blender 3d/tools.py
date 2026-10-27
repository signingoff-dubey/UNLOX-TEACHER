"""Find the local tools this pipeline needs. Every path can be overridden with an environment variable."""
from __future__ import annotations

import glob
import os
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent


def backend_dir() -> Path:
    return Path(os.environ.get("VT_BACKEND", Path.home() / "visual-teacher" / "backend"))


def blender_exe() -> Path | None:
    """BLENDER_EXE, then a normal install, a portable copy, PATH, and finally the Microsoft Store launcher
    (the Store's own blender.exe cannot be started directly)."""
    if os.environ.get("BLENDER_EXE"):
        return Path(os.environ["BLENDER_EXE"])
    pf = os.environ.get("ProgramFiles", r"C:\Program Files")
    candidates = sorted(glob.glob(os.path.join(pf, "Blender Foundation", "Blender*", "blender.exe")), reverse=True)
    candidates += sorted(glob.glob(str(Path.home() / "blender*" / "blender.exe")), reverse=True)
    candidates += sorted(glob.glob(str(HERE / "blender-portable*" / "blender.exe")), reverse=True)
    on_path = shutil.which("blender")
    if on_path:
        candidates.append(on_path)
    store = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WindowsApps" / "blender-launcher.exe"
    if store.exists():
        candidates.append(str(store))
    return Path(candidates[0]) if candidates else None


def ffmpeg_exe() -> Path | None:
    """Only used by tools_frames.py for previews; the render itself uses Blender's built-in encoder."""
    found = shutil.which("ffmpeg")
    if found:
        return Path(found)
    bundled = Path.home() / "visual-teacher" / "web" / "node_modules" / "@remotion" / "compositor-win32-x64-msvc" / "ffmpeg.exe"
    return bundled if bundled.exists() else None
