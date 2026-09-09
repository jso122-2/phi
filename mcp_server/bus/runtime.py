"""Runtime paths — leftover rings/job files from the old stdio worker, plus pid."""
from __future__ import annotations

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
