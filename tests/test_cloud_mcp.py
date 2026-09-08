"""Cloud MCP: in-process search when the mmap bus is down + spawn gate protocol."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

from mcp_server.bus.client import submit_and_maybe_wait

ROOT = Path(__file__).resolve().parent.parent


def test_search_find_in_process_when_bus_down(monkeypatch):
    import mcp_server.bus.client as client_mod

    monkeypatch.setattr(client_mod, "get_client", lambda: None)
    result = submit_and_maybe_wait(
        "search.find",
        wait_s=60.0,
        query="mcp utilized tool call based solutions",
        activations=np.zeros(8).tolist(),
        mode="pericles",
        harmonic_step=0,
        perspective_alpha=0.5,
        modulation={"source": "test"},
        dawn_x=0.0,
    )
    assert result.get("error") is None, result
    assert result["status"] == "done"
    assert result["source"] == "in-process"
    assert result["task"] == "search.find"
    assert result["vault_sim_tool"] == "find_query"
    assert result["n_docs_searched"] > 0
    assert result["answer"] is not None
    assert result["answer"]["title"]


def test_search_psspps_in_process_when_bus_down(monkeypatch):
    import mcp_server.bus.client as client_mod

    monkeypatch.setattr(client_mod, "get_client", lambda: None)
    result = submit_and_maybe_wait(
        "search.psspps",
        wait_s=30.0,
        query="how is psspps utilised for the mcp server",
        activations=np.zeros(8).tolist(),
        top_k=3,
        perspective_alpha=0.5,
        modulation={"source": "test"},
    )
    assert result.get("error") is None, result
    assert result["source"] == "in-process"
    assert result["vault_sim_tool"] == "psspps_query"
    assert result["retrieval_triggered"] is True
    assert len(result["top_docs"]) >= 1


def test_async_ticket_still_requires_bus(monkeypatch):
    import mcp_server.bus.client as client_mod

    monkeypatch.setattr(client_mod, "get_client", lambda: None)
    result = submit_and_maybe_wait("search.find", wait_s=0, query="x", activations=[0.0] * 8)
    assert result["error"] == "bus_unavailable"


def test_cloud_stdio_lists_search_tools():
    """Handshake ``python3 -m mcp_server.cloud`` and require find_query + psspps_query."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    env["PYTHONUNBUFFERED"] = "1"
    env["SPOTIFY_RIP_DISABLE_ADMISSION"] = "1"
    env["SPOTIFY_RIP_MCP_NAME"] = "phi"
    env["SPOTIFY_RIP_CLOUD_MCP"] = "1"
    proc = subprocess.Popen(
        [sys.executable, "-m", "mcp_server.cloud"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        cwd=str(ROOT),
        env=env,
    )
    try:
        time.sleep(1.0)

        def send(msg: dict) -> None:
            proc.stdin.write(json.dumps(msg) + "\n")
            proc.stdin.flush()

        def recv() -> dict:
            deadline = time.monotonic() + 25.0
            while time.monotonic() < deadline:
                line = proc.stdout.readline()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if obj.get("id") is not None:
                    return obj
            raise TimeoutError("no JSON-RPC response from cloud MCP")

        send({
            "jsonrpc": "2.0",
            "id": 0,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "cloud-mcp-test", "version": "0"},
            },
        })
        init = recv()
        assert "result" in init, init
        send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        send({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
        listed = recv()
        names = {t["name"] for t in listed["result"]["tools"]}
        assert "find_query" in names, sorted(names)
        assert "psspps_query" in names, sorted(names)
        assert "session_audit" in names, sorted(names)
        assert "phi_watchdog" in names, sorted(names)
        assert len(names) <= 70   # catalog grows; keep a reasonable ceiling
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=2)


# ---------------------------------------------------------------------------
# Spawn gate unit tests (no subprocess — in-process, isolated via monkeypatch)
# ---------------------------------------------------------------------------

def test_spawn_gate_hook_registered_after_startup_init(monkeypatch):
    """_startup_init registers the spawn_gate hook in the hook chain."""
    import importlib
    import mcp_server._spawn_gate as sg_mod
    import mcp_server.hooks as hooks_mod

    # Reset spawn state so the test runs clean
    monkeypatch.setattr(sg_mod, "_spawn_complete", __import__("threading").Event())
    monkeypatch.setattr(sg_mod, "_hook_registered", __import__("threading").Event())

    # Re-register via the public function
    sg_mod._register_spawn_gate()

    names = {h.name for h in hooks_mod.REGISTRY._chain}
    assert "spawn_gate" in names, f"spawn_gate not in hook chain: {names}"


def test_emit_spawn_context_idempotent(monkeypatch, tmp_path):
    """emit_spawn_context() fires only once; second call is a no-op."""
    import mcp_server._spawn_gate as sg_mod

    # Redirect session dir to tmp
    call_count = []

    original_emit = sg_mod._emit_spawn_banner
    def counting_emit(init, ctx):
        call_count.append(1)
        original_emit(init, ctx)

    monkeypatch.setattr(sg_mod, "_spawn_complete", __import__("threading").Event())
    monkeypatch.setattr(sg_mod, "_emit_spawn_banner", counting_emit)

    sg_mod.emit_spawn_context()
    sg_mod.emit_spawn_context()   # second call — must be no-op
    sg_mod.emit_spawn_context()   # third call — also no-op

    assert len(call_count) == 1, f"emit_spawn_banner called {len(call_count)} times, want 1"


def test_spawn_gate_hook_blocks_ungated_call(monkeypatch):
    """spawn_gate hook raises HookViolation when gate is not open and a substantive tool is called."""
    import threading
    import mcp_server._spawn_gate as sg_mod
    from mcp_server.hooks import HookViolation

    # Reset spawn state
    monkeypatch.setattr(sg_mod, "_spawn_complete", threading.Event())
    monkeypatch.setattr(sg_mod, "_spawn_lock", threading.Lock())

    # Gate NOT open
    monkeypatch.setattr("mcp_server._gate._session_initialized", False)

    import pytest
    with pytest.raises(HookViolation, match="spawn_gate"):
        # Simulate the hook firing on a substantive tool call
        sg_mod.spawn_gate_hook = None   # will be replaced below
        # Re-register to get a fresh closure
        monkeypatch.setattr(sg_mod, "_hook_registered", threading.Event())
        from mcp_server.hooks import REGISTRY
        # Grab the last registered spawn_gate hook fn directly
        sg_mod._register_spawn_gate()
        hook_fn = next(h.fn for h in reversed(REGISTRY._chain) if h.name == "spawn_gate")
        hook_fn("psspps_query", {})


def test_spawn_gate_hook_allows_init_check_without_gate(monkeypatch):
    """spawn_gate hook does NOT raise for init_check even when gate is closed."""
    import threading
    import mcp_server._spawn_gate as sg_mod

    monkeypatch.setattr(sg_mod, "_spawn_complete", threading.Event())
    monkeypatch.setattr(sg_mod, "_spawn_lock", threading.Lock())
    monkeypatch.setattr("mcp_server._gate._session_initialized", False)
    monkeypatch.setattr(sg_mod, "_hook_registered", threading.Event())

    from mcp_server.hooks import REGISTRY
    sg_mod._register_spawn_gate()
    hook_fn = next(h.fn for h in reversed(REGISTRY._chain) if h.name == "spawn_gate")

    # Should not raise — init_check is exempt from the gate check
    hook_fn("init_check", {})


def test_spawn_context_dict_contains_live_init(monkeypatch, tmp_path):
    """spawn_context_dict() returns spawned=True and live_init content."""
    import mcp_server._spawn_gate as sg_mod

    fake_init = "# Session Init\n\n- hub: HOME\n- activation: 0.7"
    (tmp_path / "live-init.md").write_text(fake_init, encoding="utf-8")

    monkeypatch.setattr(
        sg_mod,
        "_read_live_init_content",
        lambda: fake_init,
    )

    ctx = sg_mod.spawn_context_dict()
    assert ctx["spawned"] is True
    assert ctx["live_init"] == fake_init
