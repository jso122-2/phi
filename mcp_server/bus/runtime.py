"""Paths for the mmap rings, job files, celery broker, and worker pid."""
from __future__ import annotations

import time as _time
from pathlib import Path

from graph.node import VAULT_ROOT

RING_CAPACITY: int = 64
RING_SLOT_SIZE: int = 2048


def runtime_dir() -> Path:
    return VAULT_ROOT / ".runtime" / "bus"


def dispatch_path() -> Path:
    return runtime_dir() / "dispatch.ring"


def complete_path() -> Path:
    return runtime_dir() / "complete.ring"


def jobs_dir() -> Path:
    return runtime_dir() / "jobs"


def celery_dir() -> Path:
    return runtime_dir() / "celery"


def pid_path() -> Path:
    return runtime_dir() / "worker.pid"


def worker_log_path() -> Path:
    return runtime_dir() / "worker.log"


def stdio_pid_path() -> Path:
    return runtime_dir() / "stdio.pid"


def guardian_pid_path() -> Path:
    return runtime_dir() / "guardian.pid"


def guardian_log_path() -> Path:
    return runtime_dir() / "guardian.log"


def last_toggle_path() -> Path:
    return runtime_dir() / "last_toggle.json"


def toggle_lock_path() -> Path:
    return runtime_dir() / "toggle.lock"


def ensure_runtime() -> Path:
    root = runtime_dir()
    jobs_dir().mkdir(parents=True, exist_ok=True)
    celery_dir().mkdir(parents=True, exist_ok=True)
    for sub in ("in", "out", "processed", "results"):
        (celery_dir() / sub).mkdir(parents=True, exist_ok=True)
    return root


def purge_old_jobs(max_age_hours: int = 24) -> int:
    """Delete job JSON files older than *max_age_hours*.

    Returns the number of files deleted.  Silent on individual file errors so
    a locked or already-deleted file never aborts the sweep.
    """
    cutoff = _time.time() - max_age_hours * 3600
    deleted = 0
    try:
        for path in jobs_dir().glob("*.json"):
            try:
                if path.stat().st_mtime < cutoff:
                    path.unlink(missing_ok=True)
                    deleted += 1
            except OSError:
                pass
    except OSError:
        pass
    return deleted
