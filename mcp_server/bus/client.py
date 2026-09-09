"""MCP / studio client: submit jobs to the singleton in-process scheduler."""
from __future__ import annotations

import os
from typing import Any, Optional

from mcp_server.bus.runtime import pid_path


def load_job(job_id: str) -> Optional[dict[str, Any]]:
    from mcp_server.bus.scheduler import get_scheduler

    sched = get_scheduler()
    if sched is None:
        return None
    return sched.load(job_id)


def save_job(record: dict[str, Any]) -> None:
    from mcp_server.bus.scheduler import get_scheduler

    sched = get_scheduler()
    if sched is None:
        return
    sched.save(record)


def worker_pid() -> Optional[int]:
    from mcp_server.bus.scheduler import get_scheduler

    sched = get_scheduler()
    if sched is not None and sched.alive:
        return os.getpid()
    path = pid_path()
    if not path.exists():
        return None
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except (TypeError, ValueError):
        return None


def worker_alive(pid: Optional[int] = None) -> bool:
    if pid is not None:
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        return True
    from mcp_server.bus.scheduler import get_scheduler

    sched = get_scheduler()
    return sched is not None and sched.alive


class BusClient:
    """Thin facade over the process-lifetime BusScheduler."""

    def __init__(self, scheduler: Any = None) -> None:
        self._sched = scheduler

    @property
    def alive(self) -> bool:
        sched = self._sched
        return sched is not None and bool(getattr(sched, "alive", False))

    @classmethod
    def connect(cls, *, create: bool = False) -> Optional["BusClient"]:
        from mcp_server.bus.scheduler import ensure_scheduler, get_scheduler

        if create:
            return cls(ensure_scheduler())
        sched = get_scheduler()
        if sched is None or not sched.alive:
            return None
        return cls(sched)

    def close(self) -> None:
        return None

    def submit(self, task: str, kwargs: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        if self._sched is None:
            return {
                "job_id": "",
                "task": task,
                "status": "error",
                "error": "bus_unavailable",
                "worker_alive": False,
            }
        return self._sched.submit(task, kwargs)

    def poll(self, job_id: str) -> Optional[dict[str, Any]]:
        if self._sched is None:
            return None
        return self._sched.poll(job_id)

    def wait(self, job_id: str, timeout: float = 30.0) -> Optional[dict[str, Any]]:
        if self._sched is None:
            return None
        return self._sched.wait(job_id, timeout=timeout)

    def status(self) -> dict[str, Any]:
        if self._sched is None:
            return {
                "worker_alive": False,
                "worker_pid": None,
                "connected": False,
            }
        return self._sched.snapshot()


_client: Optional[BusClient] = None


def get_client() -> Optional[BusClient]:
    global _client
    if _client is not None and _client.alive:
        return _client
    from mcp_server.bus.scheduler import ensure_scheduler

    _client = BusClient(ensure_scheduler())
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
            "hint": "bus scheduler did not start",
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
