"""Tiny in-process job queues. Lessons and exports share one worker (one GPU job at a time);
PDF uploads get their own worker so a long OCR pass never delays a lesson."""
from __future__ import annotations

import logging
import threading
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

log = logging.getLogger(__name__)

_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="lesson")
# Separate workers: a course in progress must not block a single lesson or an export, and a long OCR pass must not block any of them.
_pools = {"default": _pool, "playlist": ThreadPoolExecutor(max_workers=1, thread_name_prefix="playlist"),
          "export": ThreadPoolExecutor(max_workers=1, thread_name_prefix="export"),
          "upload": ThreadPoolExecutor(max_workers=1, thread_name_prefix="upload"),
          "studio": ThreadPoolExecutor(max_workers=1, thread_name_prefix="studio"),
          "vision": ThreadPoolExecutor(max_workers=1, thread_name_prefix="vision"),
          "langs": ThreadPoolExecutor(max_workers=1, thread_name_prefix="langs"),
          "homework": ThreadPoolExecutor(max_workers=1, thread_name_prefix="homework")}
_jobs: dict[str, dict[str, Any]] = {}
_lock = threading.Lock()


def _remember(job: dict) -> None:
    """Keeps a copy of the job on disk (resume.py), so a restart knows what was running. Best effort."""
    try:
        from . import resume
        resume.record(job)
    except Exception:  # noqa: BLE001
        pass


def submit(kind: str, fn: Callable[..., Any], *args: Any) -> dict:
    job_id = uuid.uuid4().hex[:12]
    job = {"id": job_id, "kind": kind, "status": "queued", "stage": "Waiting", "progress": 0.0,
           "result": None, "error": None}
    with _lock:
        _jobs[job_id] = job
    _remember(job)

    def progress(stage: str, value: float, **extra: Any) -> None:
        """`extra` is attached to the job as it is (e.g. the id of a lesson whose first scenes can already be watched)."""
        with _lock:
            job.update(stage=stage, progress=round(min(max(value, 0.0), 1.0), 3), **extra)
        if extra:
            _remember(job)                                   # e.g. the lesson id: worth keeping at once

    def run() -> None:
        job["status"] = "running"
        _remember(job)
        try:
            job["result"] = fn(*args, progress)
            job["status"] = "done"
        except Exception as e:  # surfaced to the UI
            log.error("Job %s failed:\n%s", job_id, traceback.format_exc())
            job.update(status="error", error=f"{type(e).__name__}: {e}")
        _remember(job)

    _pools.get(kind, _pool).submit(run)
    return job


def active(*kinds: str) -> bool:
    """True while any job of these kinds is waiting or running."""
    with _lock:
        return any(j["kind"] in kinds and j["status"] in ("queued", "running") for j in _jobs.values())


def get(job_id: str) -> dict | None:
    with _lock:
        job = _jobs.get(job_id)
        return dict(job) if job else None
