"""Keeps the laptop usable while a course is being made.

A 5 video course used to fill the 8 GB graphics card (language model + translator + speech model + every voice on CUDA), which makes
Windows spill into system memory and freeze the desktop, and then fail with "CUDA error: out of memory". Four things here prevent that:

* the backend runs below normal priority, so the desktop, the browser and the slides stay responsive while it works;
* background work (the extra episodes, the study tools) waits while RAM or VRAM is short (`wait_for_headroom`, `has_headroom`);
* models that are only needed now and then (speech recognition, the translator) are released after a quiet spell (`idle_release`);
* the number of threads the maths libraries may use is capped (see config.py).
"""
from __future__ import annotations

import gc
import logging
import os
import sys
import threading
import time
from typing import Callable

log = logging.getLogger(__name__)

MIN_RAM_GB = float(os.getenv("MIN_FREE_RAM_GB", "1.5"))      # background work waits below this much free system memory
MIN_VRAM_GB = float(os.getenv("MIN_FREE_VRAM_GB", "0.8"))    # ... or below this much free graphics memory


def lower_priority() -> None:
    """Below-normal CPU priority for this process (and so its threads): the rest of the computer always wins."""
    try:
        import psutil
        psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS if sys.platform == "win32" else 5)
        log.info("Backend priority lowered so the desktop stays responsive")
    except Exception as e:  # noqa: BLE001  a nicety, never a reason to stop
        log.info("Could not lower the priority: %s", e)


def free_ram_gb() -> float | None:
    try:
        import psutil
        return psutil.virtual_memory().available / 2 ** 30
    except Exception:  # noqa: BLE001
        return None


def free_vram_gb() -> float | None:
    """Free graphics memory, without importing torch just to look (None until something has loaded it, or without a GPU)."""
    if "torch" not in sys.modules:
        return None
    from . import config
    return config.gpu_free_gb()


def snapshot() -> dict:
    ram, vram = free_ram_gb(), free_vram_gb()
    out = {"free_ram_gb": None if ram is None else round(ram, 1), "free_vram_gb": None if vram is None else round(vram, 1)}
    if "torch" in sys.modules:                                    # what this process's torch holds on the card (it must stay small)
        try:
            import torch
            if torch.cuda.is_available():
                out["torch_reserved_gb"] = round(torch.cuda.memory_reserved() / 2 ** 30, 2)
        except Exception:  # noqa: BLE001
            pass
    return out


def has_headroom(min_ram: float = MIN_RAM_GB, min_vram: float = MIN_VRAM_GB) -> bool:
    ram, vram = free_ram_gb(), free_vram_gb()
    return (ram is None or ram >= min_ram) and (vram is None or vram >= min_vram)


def wait_for_headroom(what: str, min_ram: float = MIN_RAM_GB, min_vram: float = MIN_VRAM_GB, timeout: float = 90.0) -> None:
    """Block while memory is short, at most `timeout` seconds (then go on: a slow lesson is better than none)."""
    t0, told = time.monotonic(), False
    while not has_headroom(min_ram, min_vram) and time.monotonic() - t0 < timeout:
        if not told:
            told = True
            log.warning("Waiting to start %s: %s", what, snapshot())
        time.sleep(2.0)


# ---------------------------------------------------------------- release what has been idle for a while
_last_used: dict[str, float] = {}
_release: dict[str, tuple[float, Callable[[], None]]] = {}
_lock = threading.Lock()
_reaper: threading.Thread | None = None


def touch(name: str) -> None:
    """Call on every use of a model that was registered with `idle_release`."""
    _last_used[name] = time.monotonic()


def idle_release(name: str, idle_s: float, release: Callable[[], None]) -> None:
    """Call `release` once `name` has not been touched for `idle_s` seconds (it must be safe to load the model again afterwards)."""
    global _reaper
    with _lock:
        _release[name] = (idle_s, release)
        touch(name)
        if _reaper is None or not _reaper.is_alive():
            _reaper = threading.Thread(target=_reap, name="idle-reaper", daemon=True)
            _reaper.start()


def _reap() -> None:
    while True:
        time.sleep(20.0)
        now = time.monotonic()
        with _lock:
            due = [(n, fn) for n, (idle, fn) in _release.items() if n in _last_used and now - _last_used[n] >= idle]
            for n, _ in due:
                _last_used.pop(n, None)                       # released: asleep until it is touched again
        for n, fn in due:
            try:
                fn()
                gc.collect()
                try:
                    import torch
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                except Exception:  # noqa: BLE001
                    pass
                log.info("Released %s after a quiet spell (%s)", n, snapshot())
            except Exception as e:  # noqa: BLE001
                log.warning("Could not release %s: %s", n, e)
