"""Mmap consume loop — runs inside the celery worker process."""
from __future__ import annotations

import json
import logging
import time
from typing import Any

from mcp_server.bus.client import load_job, save_job
from mcp_server.bus.runtime import (
    RING_CAPACITY,
    RING_SLOT_SIZE,
    complete_path,
    dispatch_path,
)
from mcp_server.bus.tasks import run_task
from pipeline.bridge.mmap_pipe import SharedMmapPipe

log = logging.getLogger("mcp_server.bus.consumer")


def _open_rings(timeout: float = 15.0) -> tuple[SharedMmapPipe, SharedMmapPipe]:
    deadline = time.monotonic() + timeout
    last_err: Exception | None = None
    while time.monotonic() < deadline:
        try:
            dispatch = SharedMmapPipe(
                dispatch_path(),
                capacity=RING_CAPACITY,
                slot_size=RING_SLOT_SIZE,
                create=False,
            )
            complete = SharedMmapPipe(
                complete_path(),
                capacity=RING_CAPACITY,
                slot_size=RING_SLOT_SIZE,
                create=False,
            )
            return dispatch, complete
        except FileNotFoundError as exc:
            last_err = exc
            time.sleep(0.05)
    raise FileNotFoundError(f"mmap rings not ready: {last_err}")


def consume_forever(stop: Any = None) -> None:
    """Block, reading the dispatch ring until *stop* is set (or forever)."""
    dispatch, complete = _open_rings()
    log.info("mmap consumer attached to %s", dispatch_path())
    try:
        while stop is None or not stop.is_set():
            raw = dispatch.get(timeout=0.5)
            if raw is None:
                continue
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                log.warning("malformed dispatch message: %r", raw[:80])
                continue
            job_id = msg.get("job_id")
            task = msg.get("task")
            if not job_id or not task:
                continue
            rec = load_job(str(job_id)) or {
                "job_id": job_id,
                "task": task,
                "kwargs": {},
            }
            rec["status"] = "running"
            rec["started_at"] = time.time()
            save_job(rec)
            try:
                result = run_task(str(task), rec.get("kwargs") or {})
                rec["status"] = "done"
                rec["result"] = result
            except Exception as exc:
                log.exception("task %s failed", task)
                rec["status"] = "error"
                rec["error"] = f"{type(exc).__name__}: {exc}"
            rec["finished_at"] = time.time()
            save_job(rec)
            tick = json.dumps({"job_id": job_id, "ok": rec["status"] == "done"}).encode()
            complete.put(tick, timeout=5.0)
    finally:
        dispatch.close()
        complete.close()
