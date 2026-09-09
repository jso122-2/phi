"""In-process singleton bus scheduler.

Owns the job queue and a single worker thread. MCP stdio, studio, and
side-effects all submit here — no mmap rings, no leftover job files, no
stdio-owned celery subprocess.
"""
from __future__ import annotations

import logging
import os
import queue
import threading
import time
import uuid
from typing import Any, Optional

from mcp_server.bus.runtime import jobs_dir, pid_path, runtime_dir

log = logging.getLogger("mcp_server.bus.scheduler")

MAX_DONE = 64
_POISON = object()


def _purge_stale_job_files() -> int:
    """Drop leftover JSON records from the old mmap/file worker."""
    root = jobs_dir()
    if not root.exists():
        return 0
    n = 0
    for path in root.glob("*.json"):
        try:
            path.unlink()
            n += 1
        except OSError:
            pass
        tmp = path.with_suffix(".tmp")
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
    return n


class BusScheduler:
    """Serial in-process worker. Job records live in memory."""

    def __init__(self) -> None:
        self._jobs: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()
        self._cv = threading.Condition(self._lock)
        self._queue: queue.Queue[Any] = queue.Queue()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._generation = 0
        self._purged_job_files = 0

    @property
    def alive(self) -> bool:
        thread = self._thread
        return thread is not None and thread.is_alive()

    def start(self) -> None:
        with self._lock:
            if self.alive:
                return
            self._stop.clear()
            self._purged_job_files = _purge_stale_job_files()
            self._thread = threading.Thread(
                target=self._run,
                name="bus-scheduler",
                daemon=True,
            )
            self._thread.start()
            try:
                pid_path().parent.mkdir(parents=True, exist_ok=True)
                pid_path().write_text(str(os.getpid()), encoding="utf-8")
            except OSError:
                pass
            log.info("scheduler started pid=%s purged_files=%s", os.getpid(), self._purged_job_files)

    def stop(self, timeout: float = 2.0) -> None:
        thread = self._thread
        if thread is None:
            return
        self._stop.set()
        self._queue.put(_POISON)
        thread.join(timeout=timeout)
        with self._lock:
            if thread is self._thread and not thread.is_alive():
                self._thread = None
        try:
            pid_path().unlink(missing_ok=True)
        except OSError:
            pass

    def restart(self) -> dict[str, Any]:
        with self._cv:
            self._generation += 1
            while True:
                try:
                    self._queue.get_nowait()
                except queue.Empty:
                    break
            self._jobs.clear()
            self._purged_job_files = _purge_stale_job_files()
            self._cv.notify_all()
        if not self.alive:
            self.start()
        return self.snapshot()

    def submit(self, task: str, kwargs: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        if not self.alive:
            return {
                "job_id": "",
                "task": task,
                "status": "error",
                "error": "scheduler_not_running",
                "worker_alive": False,
            }
        job_id = uuid.uuid4().hex
        record: dict[str, Any] = {
            "job_id": job_id,
            "task": task,
            "kwargs": kwargs or {},
            "status": "queued",
            "queued_at": time.time(),
        }
        with self._cv:
            self._jobs[job_id] = record
        self._queue.put(job_id)
        return {
            "job_id": job_id,
            "task": task,
            "status": "queued",
            "worker_alive": True,
        }

    def load(self, job_id: str) -> Optional[dict[str, Any]]:
        with self._lock:
            rec = self._jobs.get(job_id)
            return dict(rec) if rec is not None else None

    def save(self, record: dict[str, Any]) -> None:
        job_id = str(record.get("job_id") or "")
        if not job_id:
            return
        with self._cv:
            existing = self._jobs.get(job_id)
            if existing is None:
                self._jobs[job_id] = dict(record)
            else:
                existing.update(record)
            self._cv.notify_all()

    def poll(self, job_id: str) -> Optional[dict[str, Any]]:
        return self.load(job_id)

    def wait(self, job_id: str, timeout: float = 30.0) -> Optional[dict[str, Any]]:
        deadline = time.monotonic() + timeout
        with self._cv:
            while True:
                rec = self._jobs.get(job_id)
                if rec is not None and rec.get("status") in {"done", "error", "batched"}:
                    return dict(rec)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return dict(rec) if rec is not None else None
                self._cv.wait(timeout=remaining)

    def queued(self, *, task: Optional[str] = None) -> list[dict[str, Any]]:
        with self._lock:
            out: list[dict[str, Any]] = []
            for rec in self._jobs.values():
                if rec.get("status") not in {"queued", "pending"}:
                    continue
                if task is not None and rec.get("task") != task:
                    continue
                out.append(dict(rec))
            return out

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            queued = sum(1 for r in self._jobs.values() if r.get("status") == "queued")
            running = sum(1 for r in self._jobs.values() if r.get("status") == "running")
            done = sum(1 for r in self._jobs.values() if r.get("status") in {"done", "error", "batched"})
            n_jobs = len(self._jobs)
        leftover = 0
        try:
            leftover = len(list(jobs_dir().glob("*.json")))
        except OSError:
            pass
        return {
            "worker_alive": self.alive,
            "worker_pid": os.getpid() if self.alive else None,
            "runtime": str(runtime_dir()),
            "dispatch_qsize": queued,
            "complete_qsize": done,
            "n_jobs": n_jobs,
            "n_running": running,
            "n_job_files": leftover,
            "purged_job_files": self._purged_job_files,
            "scheduler": "inproc",
            "host_child_alive": self.alive,
        }

    def _run(self) -> None:
        from mcp_server.bus.tasks import run_task

        while not self._stop.is_set():
            try:
                item = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue
            if item is _POISON:
                break
            job_id = str(item)
            with self._lock:
                job_gen = self._generation
                rec = self._jobs.get(job_id)
                if rec is None or rec.get("status") == "batched":
                    continue
                rec["status"] = "running"
                rec["started_at"] = time.time()
                task = str(rec.get("task") or "")
                kwargs = rec.get("kwargs") or {}
            try:
                result = run_task(task, kwargs, job_id=job_id)
                status = "done"
                error = None
            except Exception as exc:
                log.exception("task %s failed", task)
                result = None
                status = "error"
                error = f"{type(exc).__name__}: {exc}"
            with self._cv:
                if job_gen != self._generation:
                    continue
                rec = self._jobs.get(job_id)
                if rec is not None and rec.get("status") != "batched":
                    rec["status"] = status
                    rec["finished_at"] = time.time()
                    if status == "done":
                        rec["result"] = result
                    else:
                        rec["error"] = error
                    self._prune_locked()
                self._cv.notify_all()

    def _prune_locked(self) -> None:
        finished = [
            (job_id, rec)
            for job_id, rec in self._jobs.items()
            if rec.get("status") in {"done", "error", "batched"}
        ]
        if len(finished) <= MAX_DONE:
            return
        finished.sort(key=lambda item: float(item[1].get("finished_at") or 0.0))
        for job_id, _ in finished[: len(finished) - MAX_DONE]:
            self._jobs.pop(job_id, None)


_lock = threading.Lock()
_scheduler: BusScheduler | None = None


def get_scheduler() -> BusScheduler | None:
    return _scheduler


def ensure_scheduler() -> BusScheduler:
    """Return the process singleton, starting it if needed."""
    global _scheduler
    with _lock:
        if _scheduler is None or not _scheduler.alive:
            _scheduler = BusScheduler()
            _scheduler.start()
        return _scheduler


def reset_scheduler() -> None:
    """Stop and drop the singleton (tests)."""
    global _scheduler
    with _lock:
        if _scheduler is not None:
            _scheduler.stop()
        _scheduler = None
