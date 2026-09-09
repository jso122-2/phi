"""Mmap/celery bus: SharedMmapPipe + in-process consumer (no celery required)."""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

import pytest

from mcp_server.bus.client import BusClient, bind_client, save_job
from mcp_server.bus.runtime import RING_CAPACITY, RING_SLOT_SIZE
from mcp_server.bus.tasks import TASKS, run_task
from pipeline.bridge.mmap_pipe import SharedMmapPipe


def test_shared_mmap_roundtrip(tmp_path: Path):
    path = tmp_path / "ring.bin"
    a = SharedMmapPipe(path, capacity=8, slot_size=256, create=True)
    b = SharedMmapPipe(path, capacity=8, slot_size=256, create=False)
    assert a.put(b"hello", timeout=1.0)
    assert b.get(timeout=1.0) == b"hello"
    a.close()
    b.close()


def test_shared_mmap_fifo_two_handles(tmp_path: Path):
    path = tmp_path / "ring.bin"
    w = SharedMmapPipe(path, capacity=8, slot_size=256, create=True)
    r = SharedMmapPipe(path, capacity=8, slot_size=256, create=False)
    for i in range(4):
        w.put(f"m{i}".encode(), timeout=1.0)
    for i in range(4):
        assert r.get(timeout=1.0) == f"m{i}".encode()
    w.close()
    r.close()


def _inproc_consumer(dispatch: SharedMmapPipe, complete: SharedMmapPipe, stop: threading.Event):
    from mcp_server.bus.client import load_job, save_job
    from mcp_server.bus.tasks import run_task

    while not stop.is_set():
        try:
            raw = dispatch.get(timeout=0.1)
        except RuntimeError:
            break
        if raw is None:
            continue
        msg = json.loads(raw)
        rec = load_job(msg["job_id"]) or {"job_id": msg["job_id"], "task": msg["task"], "kwargs": {}}
        rec["status"] = "done"
        rec["result"] = run_task(msg["task"], rec.get("kwargs") or {})
        save_job(rec)
        complete.put(json.dumps({"job_id": msg["job_id"], "ok": True}).encode(), timeout=1.0)


def test_bus_submit_and_wait_echo(tmp_path: Path, monkeypatch):
    from mcp_server.bus import runtime as rt
    monkeypatch.setattr(rt, "runtime_dir", lambda: tmp_path)
    monkeypatch.setattr(rt, "dispatch_path", lambda: tmp_path / "dispatch.ring")
    monkeypatch.setattr(rt, "complete_path", lambda: tmp_path / "complete.ring")
    monkeypatch.setattr(rt, "jobs_dir", lambda: tmp_path / "jobs")
    (tmp_path / "jobs").mkdir()

    from mcp_server.bus import client as client_mod
    monkeypatch.setattr(client_mod, "dispatch_path", lambda: tmp_path / "dispatch.ring")
    monkeypatch.setattr(client_mod, "complete_path", lambda: tmp_path / "complete.ring")
    monkeypatch.setattr(client_mod, "jobs_dir", lambda: tmp_path / "jobs")
    monkeypatch.setattr(client_mod, "pid_path", lambda: tmp_path / "worker.pid")

    dispatch = SharedMmapPipe(tmp_path / "dispatch.ring", RING_CAPACITY, RING_SLOT_SIZE, create=True)
    complete = SharedMmapPipe(tmp_path / "complete.ring", RING_CAPACITY, RING_SLOT_SIZE, create=True)
    client = BusClient(dispatch, complete)
    bind_client(client)

    TASKS["test.echo"] = lambda msg="": {"echo": msg}
    stop = threading.Event()
    t = threading.Thread(target=_inproc_consumer, args=(dispatch, complete, stop), daemon=True)
    t.start()
    try:
        ticket = client.submit("test.echo", {"msg": "ping"})
        rec = client.wait(ticket["job_id"], timeout=5.0)
        assert rec is not None
        assert rec["status"] == "done"
        assert rec["result"]["echo"] == "ping"
    finally:
        stop.set()
        t.join(timeout=1.0)
        TASKS.pop("test.echo", None)
        client.close()
        import mcp_server.bus.client as client_mod
        client_mod._client = None


def test_warmup_tasks_registered():
    assert "warmup.corpus" in TASKS
    assert "studio.build" in TASKS
    assert "graph.ingest_source" in TASKS


def test_purge_old_jobs_deletes_stale_files(tmp_path: Path, monkeypatch):
    """purge_old_jobs removes files whose mtime is older than the threshold."""
    from mcp_server.bus import runtime as rt
    jobs = tmp_path / "jobs"
    jobs.mkdir()
    monkeypatch.setattr(rt, "jobs_dir", lambda: jobs)

    # Create 3 "old" job files and 1 "fresh" file.
    old_mtime = time.time() - 48 * 3600  # 48 hours ago
    for i in range(3):
        p = jobs / f"old_{i}.json"
        p.write_text("{}")
        os.utime(p, (old_mtime, old_mtime))

    fresh = jobs / "fresh.json"
    fresh.write_text("{}")

    from mcp_server.bus.runtime import purge_old_jobs
    deleted = purge_old_jobs(max_age_hours=24)

    assert deleted == 3
    assert not (jobs / "old_0.json").exists()
    assert not (jobs / "old_1.json").exists()
    assert not (jobs / "old_2.json").exists()
    assert fresh.exists()  # untouched


def test_purge_old_jobs_empty_dir(tmp_path: Path, monkeypatch):
    """purge_old_jobs is silent and returns 0 on an empty directory."""
    from mcp_server.bus import runtime as rt
    jobs = tmp_path / "jobs"
    jobs.mkdir()
    monkeypatch.setattr(rt, "jobs_dir", lambda: jobs)

    from mcp_server.bus.runtime import purge_old_jobs
    assert purge_old_jobs(max_age_hours=1) == 0


def test_unknown_task_raises():
    with pytest.raises(KeyError):
        run_task("no.such.task", {})


def test_toggle_off_then_on(tmp_path: Path):
    cfg = tmp_path / "mcp.json"
    cfg.write_text(json.dumps({
        "mcpServers": {
            "spotify-rip": {
                "command": "python",
                "args": ["-m", "mcp_server.server"],
            }
        }
    }))
    from mcp_server.bus.toggle import set_disabled

    assert set_disabled(True, paths=[cfg]) == [str(cfg)]
    assert json.loads(cfg.read_text())["mcpServers"]["spotify-rip"]["disabled"] is True
    assert set_disabled(False, paths=[cfg]) == [str(cfg)]
    assert json.loads(cfg.read_text())["mcpServers"]["spotify-rip"]["disabled"] is False


def test_bounce_leaves_switch_on(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    cfg = tmp_path / "mcp.json"
    cfg.write_text(json.dumps({
        "mcpServers": {"spotify-rip": {"command": "python"}}
    }))
    monkeypatch.setattr("mcp_server.bus.toggle.last_toggle_path", lambda: tmp_path / "last.json")
    monkeypatch.setattr("mcp_server.bus.toggle.toggle_lock_path", lambda: tmp_path / "lock")
    monkeypatch.setattr("mcp_server.bus.toggle.ensure_runtime", lambda: tmp_path)
    from mcp_server.bus.toggle import bounce

    rec = bounce(paths=[cfg], off_hold_s=0.05)
    assert rec["off"] == [str(cfg)]
    assert rec["on"] == [str(cfg)]
    assert json.loads(cfg.read_text())["mcpServers"]["spotify-rip"]["disabled"] is False
    assert (tmp_path / "last.json").exists()


def test_ensure_guardian_skips_under_pytest():
    from mcp_server.bus.guardian import ensure_guardian

    rec = ensure_guardian(os.getpid())
    assert rec["spawned"] is False
    assert rec["reason"] == "pytest"


def test_guardian_alive_does_not_reuse_celery_pid():
    from mcp_server.bus.guardian import _alive

    assert _alive(None) is False
