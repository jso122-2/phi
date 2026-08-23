"""MCP / studio client: submit jobs onto the mmap ring, poll result files."""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Optional

from mcp_server.bus.runtime import (
    RING_CAPACITY,
    RING_SLOT_SIZE,
    complete_path,
    dispatch_path,
    jobs_dir,
    pid_path,
)
from pipeline.bridge.mmap_pipe import SharedMmapPipe


def _job_path(job_id: str) -> Path:
    return jobs_dir() / f"{job_id}.json"


def load_job(job_id: str) -> Optional[dict[str, Any]]:
    path = _job_path(job_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_job(record: dict[str, Any]) -> None:
    jobs_dir().mkdir(parents=True, exist_ok=True)
    path = _job_path(str(record["job_id"]))
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(record, default=str), encoding="utf-8")
    tmp.replace(path)


def worker_pid() -> Optional[int]:
    path = pid_path()
    if not path.exists():
        return None
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except (TypeError, ValueError):
        return None


def worker_alive(pid: Optional[int] = None) -> bool:
    pid = pid if pid is not None else worker_pid()
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


class BusClient:
    """Thin mmap client. Does not import celery or run tasks."""

    def __init__(
        self,
        dispatch: SharedMmapPipe,
        complete: SharedMmapPipe,
    ) -> None:
        self._dispatch = dispatch
        self._complete = complete

    @classmethod
    def connect(cls, *, create: bool = False) -> Optional["BusClient"]:
        dpath = dispatch_path()
        cpath = complete_path()
        if not dpath.exists() or not cpath.exists():
            if not create:
                return None
        try:
            dispatch = SharedMmapPipe(
                dpath, capacity=RING_CAPACITY, slot_size=RING_SLOT_SIZE, create=create,
            )
            complete = SharedMmapPipe(
                cpath, capacity=RING_CAPACITY, slot_size=RING_SLOT_SIZE, create=create,
            )
        except FileNotFoundError:
            return None
        return cls(dispatch, complete)

    def close(self) -> None:
        try:
            self._dispatch.close()
        except Exception:
            pass
        try:
            self._complete.close()
        except Exception:
            pass

    def submit(self, task: str, kwargs: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        job_id = uuid.uuid4().hex
        record: dict[str, Any] = {
            "job_id": job_id,
            "task": task,
            "kwargs": kwargs or {},
            "status": "queued",
            "queued_at": time.time(),
        }
        save_job(record)
        msg = json.dumps({"job_id": job_id, "task": task}).encode()
        ok = self._dispatch.put(msg, timeout=5.0)
        if not ok:
            record["status"] = "error"
            record["error"] = "dispatch_ring_full"
            save_job(record)
        return {
            "job_id": job_id,
            "task": task,
            "status": record["status"],
            "worker_alive": worker_alive(),
        }

    def poll(self, job_id: str) -> Optional[dict[str, Any]]:
        # Drain complete-ring ticks so the worker never blocks on a full complete pipe.
        while True:
            tick = self._complete.get(timeout=0.0)
            if tick is None:
                break
        return load_job(job_id)

    def wait(self, job_id: str, timeout: float = 30.0) -> Optional[dict[str, Any]]:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            rec = self.poll(job_id)
            if rec is not None and rec.get("status") in {"done", "error"}:
                return rec
            remaining = deadline - time.monotonic()
            self._complete.get(timeout=min(0.25, max(0.0, remaining)))
        return self.poll(job_id)

    def status(self) -> dict[str, Any]:
        pid = worker_pid()
        n_jobs = 0
        try:
            n_jobs = len(list(jobs_dir().glob("*.json")))
        except OSError:
            pass
        return {
            "worker_alive": worker_alive(pid),
            "worker_pid": pid,
            "runtime": str(dispatch_path().parent),
            "dispatch_qsize": self._dispatch.qsize(),
            "complete_qsize": self._complete.qsize(),
            "n_job_files": n_jobs,
        }


_client: Optional[BusClient] = None


def get_client() -> Optional[BusClient]:
    global _client
    if _client is not None:
        return _client
    _client = BusClient.connect(create=False)
    return _client


def bind_client(client: BusClient) -> BusClient:
    global _client
    _client = client
    return client


def submit_and_maybe_wait(
    task: str,
    *,
    wait_s: float = 60.0,
    **kwargs: Any,
) -> dict[str, Any]:
    """Enqueue on the bus. Wait for a result when wait_s > 0."""
    from mcp_server.bus.side_effects import apply_side_effects

    client = get_client()
    if client is None:
        return {
            "error": "bus_unavailable",
            "task": task,
            "hint": "celery worker did not open the mmap rings",
        }
    ticket = client.submit(task, kwargs)
    if wait_s <= 0:
        return ticket
    rec = client.wait(ticket["job_id"], timeout=float(wait_s))
    if rec is None:
        ticket["status"] = "queued"
        ticket["hint"] = "still running — call bus_wait"
        return ticket
    rec = apply_side_effects(rec)
    if rec.get("status") == "done":
        result = rec.get("result")
        if isinstance(result, dict):
            result = dict(result)
            result["job_id"] = rec["job_id"]
            result["task"] = rec.get("task", task)
            result["status"] = "done"
            return result
        return rec
    return rec
