"""Singleton bus scheduler + leftover toggle/guardian contracts."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from mcp_server.bus.client import BusClient, bind_client, get_client, worker_alive
from mcp_server.bus.scheduler import ensure_scheduler, reset_scheduler
from mcp_server.bus.tasks import TASKS, run_task
from pipeline.bridge.mmap_pipe import SharedMmapPipe


@pytest.fixture(autouse=True)
def _isolated_scheduler(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from mcp_server.bus import scheduler as sched_mod

    monkeypatch.setattr(sched_mod, "jobs_dir", lambda: tmp_path / "jobs")
    monkeypatch.setattr(sched_mod, "pid_path", lambda: tmp_path / "worker.pid")
    monkeypatch.setattr(sched_mod, "runtime_dir", lambda: tmp_path)
    reset_scheduler()
    yield
    reset_scheduler()
    import mcp_server.bus.client as client_mod
    client_mod._client = None


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


def test_scheduler_submit_and_wait_echo():
    TASKS["test.echo"] = lambda msg="": {"echo": msg}
    try:
        sched = ensure_scheduler()
        client = BusClient(sched)
        bind_client(client)
        ticket = client.submit("test.echo", {"msg": "ping"})
        rec = client.wait(ticket["job_id"], timeout=5.0)
        assert rec is not None
        assert rec["status"] == "done"
        assert rec["result"]["echo"] == "ping"
        assert worker_alive()
        snap = client.status()
        assert snap["scheduler"] == "inproc"
        assert snap["worker_alive"] is True
    finally:
        TASKS.pop("test.echo", None)


def test_get_client_starts_scheduler():
    client = get_client()
    assert client is not None
    assert client.alive
    assert worker_alive()


def test_scheduler_restart_clears_queue():
    TASKS["test.echo"] = lambda msg="": {"echo": msg}
    try:
        sched = ensure_scheduler()
        client = BusClient(sched)
        bind_client(client)
        first = client.submit("test.echo", {"msg": "old"})
        rec = client.wait(first["job_id"], timeout=5.0)
        assert rec is not None and rec["status"] == "done"
        from mcp_server.bus.host import restart_worker

        snap = restart_worker()
        assert snap["worker_alive"] is True
        assert snap["dispatch_qsize"] == 0
        assert client.poll(first["job_id"]) is None
        ticket = client.submit("test.echo", {"msg": "new"})
        rec = client.wait(ticket["job_id"], timeout=5.0)
        assert rec is not None
        assert rec["result"]["echo"] == "new"
    finally:
        TASKS.pop("test.echo", None)


def test_scheduler_purges_stale_job_files(tmp_path: Path):
    jobs = tmp_path / "jobs"
    jobs.mkdir()
    stale = jobs / "deadbeef.json"
    stale.write_text(json.dumps({"job_id": "deadbeef", "status": "queued"}), encoding="utf-8")

    reset_scheduler()
    sched = ensure_scheduler()
    assert not stale.exists()
    assert sched.snapshot()["purged_job_files"] == 1
    assert sched.snapshot()["n_job_files"] == 0


def test_warmup_tasks_registered():
    assert "warmup.corpus" in TASKS
    assert "studio.build" in TASKS
    assert "graph.ingest_source" in TASKS


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
