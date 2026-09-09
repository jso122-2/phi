"""Bus tools: enqueue, poll, wait, status. MCP is a thin dispatcher on this surface."""
from __future__ import annotations

from typing import Any

from mcp_server._gate import requires_init
from mcp_server._state import _dom_queue, mcp
from mcp_server.bus.client import get_client
from mcp_server.bus.side_effects import apply_side_effects
from mcp_server.bus.tasks import TASKS


@mcp.tool()
@requires_init
def bus_submit(task: str, payload_json: str = "{}") -> dict[str, Any]:
    """
    Enqueue a celery/mmap job and return its job_id immediately.

    Parameters
    ----------
    task         : registered bus task name (e.g. graph.ingest_source)
    payload_json : JSON object of kwargs for that task
    """
    import json

    with _dom_queue.gate("bus_submit"):
        if task not in TASKS:
            return {"error": "unknown_task", "task": task, "valid": sorted(TASKS)}
        try:
            kwargs = json.loads(payload_json) if payload_json else {}
        except json.JSONDecodeError as exc:
            return {"error": "bad_payload", "detail": str(exc)}
        if not isinstance(kwargs, dict):
            return {"error": "bad_payload", "detail": "payload must be a JSON object"}
        client = get_client()
        if client is None:
            return {"error": "bus_unavailable", "task": task}
        return client.submit(task, kwargs)


@mcp.tool()
def bus_poll(job_id: str) -> dict[str, Any]:
    """Return the current job record. Init-free."""
    with _dom_queue.gate("bus_poll"):
        client = get_client()
        if client is None:
            return {"error": "bus_unavailable", "job_id": job_id}
        rec = client.poll(job_id)
        if rec is None:
            return {"error": "unknown_job", "job_id": job_id}
        rec = apply_side_effects(rec)
        return rec


@mcp.tool()
@requires_init
def bus_wait(job_id: str, timeout_s: float = 30.0) -> dict[str, Any]:
    """Block until a job finishes or timeout_s elapses."""
    with _dom_queue.gate("bus_wait"):
        client = get_client()
        if client is None:
            return {"error": "bus_unavailable", "job_id": job_id}
        rec = client.wait(job_id, timeout=float(timeout_s))
        if rec is None:
            return {"error": "unknown_job", "job_id": job_id}
        rec = apply_side_effects(rec)
        if rec.get("status") not in {"done", "error"}:
            rec = dict(rec)
            rec["hint"] = "still running"
        return rec


@mcp.tool()
@requires_init
def bus_restart() -> dict[str, Any]:
    """
    Kill the stale bus worker, reset the mmap rings, and spawn a fresh worker.

    Use when bus_status shows worker_alive=false. Clears backed-up dispatch
    jobs (they were never consumed), then starts a clean worker subprocess.
    """
    with _dom_queue.gate("bus_restart"):
        from mcp_server.bus.host import restart_worker
        from mcp_server.bus.runtime import purge_old_jobs
        try:
            snap = restart_worker()
            purged = purge_old_jobs(max_age_hours=24)
            return {"status": "restarted", "purged_jobs": purged, **snap}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}


@mcp.tool()
def bus_status() -> dict[str, Any]:
    """Mmap ring + celery worker snapshot. Init-free."""
    with _dom_queue.gate("bus_status"):
        client = get_client()
        from mcp_server.bus.guardian import guardian_alive
        from mcp_server.bus.runtime import guardian_pid_path, stdio_pid_path
        from mcp_server.bus.toggle import last_toggle

        def _pid(path):
            try:
                return int(path.read_text(encoding="utf-8").strip())
            except Exception:
                return None

        toggle = {
            "stdio_pid": _pid(stdio_pid_path()),
            "guardian_alive": guardian_alive(),
            "guardian_pid": _pid(guardian_pid_path()),
            "last_toggle": last_toggle(),
        }
        if client is None:
            from mcp_server.bus.client import worker_alive, worker_pid
            return {
                "connected": False,
                "worker_alive": worker_alive(),
                "worker_pid": worker_pid(),
                "tasks": sorted(TASKS),
                **toggle,
            }
        snap = client.status()
        snap["connected"] = True
        snap["tasks"] = sorted(TASKS)
        snap.update(toggle)
        return snap
