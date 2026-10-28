"""Made once, kept: an export (MP4, narration audio, lesson file, course video) is reused while what it was made from is unchanged.

Each output file gets a small `<file>.key` next to it: a hash of exactly what it was made from (the language track, the height, the format).
The lesson file itself changes for other reasons (a new language, the list of videos), so its modification time is not a reliable test;
the hash of the inputs is.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def key_of(*parts) -> str:
    """A stable hash of JSON-able inputs."""
    return hashlib.sha1(json.dumps(parts, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")).hexdigest()


def _key_file(out: Path) -> Path:
    return out.with_name(out.name + ".key")


def is_fresh(out: Path, key: str) -> bool:
    """True when `out` exists and was made from the inputs that hash to `key`."""
    kf = _key_file(out)
    try:
        return out.exists() and out.stat().st_size > 0 and kf.read_text(encoding="utf-8").strip() == key
    except OSError:
        return False


def mark(out: Path, key: str) -> None:
    """Record what `out` was made from (call after it was written successfully)."""
    _key_file(out).write_text(key, encoding="utf-8")
