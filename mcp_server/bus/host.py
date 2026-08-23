"""Auto-host the celery/mmap worker as a subprocess with stdio redirected to a log."""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

from mcp_server.bus.client import BusClient, bind_client, worker_alive, worker_pid
from mcp_server.bus.runtime import (
    RING_CAPACITY,
    RING_SLOT_SIZE,
    complete_path,
    dispatch_path,
    ensure_runtime,
    pid_path,
    worker_log_path,
)
from pipeline.bridge.mmap_pipe import SharedMmapPipe


def _write_pid(pid: int) -> None:
    pid_path().write_text(str(pid), encoding="utf-8")


def _kill_stale() -> None:
    pid = worker_pid()
    if pid is None:
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
        pid_path().unlink(missing_ok=True)
    except OSError:
        pass


def _reset_rings() -> tuple[SharedMmapPipe, SharedMmapPipe]:
    ensure_runtime()
    for path in (dispatch_path(), complete_path()):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        lock = path.with_suffix(path.suffix + ".lock")
        try:
            lock.unlink(missing_ok=True)
        except OSError:
            pass
    dispatch = SharedMmapPipe(
        dispatch_path(), capacity=RING_CAPACITY, slot_size=RING_SLOT_SIZE, create=True,
    )
    complete = SharedMmapPipe(
        complete_path(), capacity=RING_CAPACITY, slot_size=RING_SLOT_SIZE, create=True,
    )
    return dispatch, complete


_current_host: "BusHost | None" = None


def set_current_host(host: "BusHost") -> None:
    """Register the active BusHost so tools can reach it for restart."""
    global _current_host
    _current_host = host


def restart_worker() -> dict:
    """
    Kill any stale worker, reset the rings, and spawn a fresh subprocess.

    Safe to call mid-session: `bind_client` updates the module-level client
    singleton so new submits go to the fresh rings immediately.
    """
    global _current_host
    if _current_host is not None:
        try:
            _current_host.stop()
        except Exception:
            pass
    host = BusHost.auto_start(force=True)
    _current_host = host
    return host.snapshot()


class BusHost:
    """Owns the mmap rings and the celery worker subprocess."""

    def __init__(self, proc: Optional[subprocess.Popen], client: BusClient) -> None:
        self._proc = proc
        self.client = client

    @classmethod
    def auto_start(cls, *, force: bool = False) -> "BusHost":
        if not force and worker_alive():
            client = BusClient.connect(create=False)
            if client is not None:
                bind_client(client)
                return cls(None, client)
        _kill_stale()
        dispatch, complete = _reset_rings()
        client = BusClient(dispatch, complete)
        bind_client(client)

        log_path = worker_log_path()
        log_f = open(log_path, "ab", buffering=0)
        env = os.environ.copy()
        env.setdefault("PYTHONUNBUFFERED", "1")
        env["MCP_BUS_WORKER"] = "1"
        proc = subprocess.Popen(
            [sys.executable, "-m", "mcp_server.bus"],
            cwd=str(Path(__file__).resolve().parents[2]),
            stdin=subprocess.DEVNULL,
            stdout=log_f,
            stderr=log_f,
            env=env,
            start_new_session=True,
        )
        _write_pid(proc.pid)
        return cls(proc, client)

    def stop(self) -> None:
        proc = self._proc
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=1.5)
            except subprocess.TimeoutExpired:
                proc.kill()
                try:
                    proc.wait(timeout=1.0)
                except subprocess.TimeoutExpired:
                    pass
        elif worker_alive():
            pid = worker_pid()
            if pid is not None:
                try:
                    os.kill(pid, signal.SIGTERM)
                except OSError:
                    pass
        try:
            pid_path().unlink(missing_ok=True)
        except OSError:
            pass
        self.client.close()

    def snapshot(self) -> dict:
        alive = self._proc is not None and self._proc.poll() is None
        return {
            **self.client.status(),
            "host_child_alive": alive,
        }
