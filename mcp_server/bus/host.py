"""Own the singleton bus scheduler for the MCP process lifetime."""
from __future__ import annotations

import os
import signal
import time

from mcp_server.bus.client import BusClient, bind_client, worker_alive
from mcp_server.bus.runtime import complete_path, dispatch_path, pid_path
from mcp_server.bus.scheduler import BusScheduler, ensure_scheduler


def _kill_stale_subprocess() -> None:
    """Reap a leftover mmap/celery worker from the old stdio-host pattern."""
    pid = None
    path = pid_path()
    if path.exists():
        try:
            pid = int(path.read_text(encoding="utf-8").strip())
        except (TypeError, ValueError):
            pid = None
    if pid is None or pid == os.getpid():
        return
    if worker_alive(pid):
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            return
        deadline = time.monotonic() + 3.0
        while worker_alive(pid) and time.monotonic() < deadline:
            time.sleep(0.05)
        if worker_alive(pid):
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def _drop_legacy_rings() -> None:
    for ring in (dispatch_path(), complete_path()):
        try:
            ring.unlink(missing_ok=True)
        except OSError:
            pass
        lock = ring.with_suffix(ring.suffix + ".lock")
        try:
            lock.unlink(missing_ok=True)
        except OSError:
            pass


_current_host: "BusHost | None" = None


def set_current_host(host: "BusHost") -> None:
    """Register the active BusHost so tools can reach it for restart."""
    global _current_host
    _current_host = host


def restart_worker() -> dict:
    """
    Restart the in-process scheduler and clear queued jobs.

    Safe to call mid-session: `bind_client` updates the module-level client
    singleton so new submits go to the same scheduler instance immediately.
    """
    global _current_host
    host = BusHost.auto_start(force=True)
    _current_host = host
    return host.snapshot()


class BusHost:
    """Holds the process-lifetime BusScheduler."""

    def __init__(self, scheduler: BusScheduler, client: BusClient) -> None:
        self._sched = scheduler
        self.client = client

    @classmethod
    def auto_start(cls, *, force: bool = False) -> "BusHost":
        if not os.environ.get("PYTEST_CURRENT_TEST"):
            _kill_stale_subprocess()
            _drop_legacy_rings()
        from mcp_server.bus.scheduler import get_scheduler

        sched = get_scheduler()
        if sched is None:
            sched = ensure_scheduler()
        elif force:
            sched.restart()
        elif not sched.alive:
            sched.start()
        client = BusClient(sched)
        bind_client(client)
        return cls(sched, client)

    def stop(self) -> None:
        self._sched.stop()

    def snapshot(self) -> dict:
        return self._sched.snapshot()
