"""Cloud MCP: in-process search when the mmap bus is down."""
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
        assert len(names) <= 60
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=2)
