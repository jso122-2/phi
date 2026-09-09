"""
Direct MCP stdio protocol tests.

Speaks raw JSON-RPC 2.0 over stdin/stdout to the MCP server subprocess —
exactly as Cursor does when it spawns the server.  No mock, no import:
the server is a black box reached only through the wire protocol.

Run:
    pytest tests/test_mcp_direct.py -v

or directly:
    python tests/test_mcp_direct.py
"""
from __future__ import annotations

import json
import os
import select
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

_READ_TIMEOUT = 20.0  # seconds — must exceed house admission timeout (10s)


# ---------------------------------------------------------------------------
# MCP stdio transport
# ---------------------------------------------------------------------------

PYTHON = sys.executable
SERVER_CWD = str(Path(__file__).parent.parent)  # Spotify-rip/


class MCPClient:
    """Minimal MCP stdio client for testing.

    Wire format: newline-delimited JSON (one JSON object per line) in both
    directions — matches mcp.server.stdio.stdio_server in MCP SDK ≥ 1.1.
    """

    def __init__(self) -> None:
        env = os.environ.copy()
        env["PYTHONPATH"] = SERVER_CWD + (
            os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
        )
        env["PYTHONUNBUFFERED"] = "1"
        # Wire tests must not wait 10s per call on BMAD admission predicates.
        env["SPOTIFY_RIP_DISABLE_ADMISSION"] = "1"
        self._proc = subprocess.Popen(
            [PYTHON, "-m", "mcp_server.server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,  # unread PIPE deadlocks after ~64KB
            text=True,
            bufsize=1,
            cwd=SERVER_CWD,
            env=env,
        )
        self._req_id = 0
        time.sleep(0.5)  # let the server boot
        # Complete MCP handshake: initialize → notifications/initialized
        self._send({
            "jsonrpc": "2.0",
            "id": 0,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "0"},
            },
        })
        self._recv(expect_id=0)
        self._notify("notifications/initialized")

    def _send(self, msg: dict[str, Any]) -> None:
        self._proc.stdin.write(json.dumps(msg) + "\n")
        self._proc.stdin.flush()

    def _notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        """Send a JSON-RPC notification (no id, no response expected)."""
        msg: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params:
            msg["params"] = params
        self._proc.stdin.write(json.dumps(msg) + "\n")
        self._proc.stdin.flush()

    def _recv(self, expect_id: int | None = None) -> dict[str, Any]:
        """Read the next matching response from stdout, with timeout."""
        deadline = time.monotonic() + _READ_TIMEOUT
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(
                    f"MCP server did not respond within {_READ_TIMEOUT}s"
                    + (f" (waiting for id={expect_id})" if expect_id is not None else "")
                )
            ready, _, _ = select.select([self._proc.stdout], [], [], remaining)
            if not ready:
                raise TimeoutError(
                    f"MCP server did not respond within {_READ_TIMEOUT}s"
                    + (f" (waiting for id={expect_id})" if expect_id is not None else "")
                )
            line = self._proc.stdout.readline()
            if not line:
                raise EOFError("MCP server closed stdout unexpectedly")
            msg = json.loads(line)
            # Skip server-pushed notifications and stale responses (wrong id).
            if "id" not in msg:
                continue
            if expect_id is not None and msg.get("id") != expect_id:
                continue
            return msg

    def call(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self._req_id += 1
        req_id = self._req_id
        self._send({
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params or {},
        })
        return self._recv(expect_id=req_id)

    def tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        resp = self.call("tools/call", {"name": name, "arguments": arguments or {}})
        content = resp.get("result", {}).get("content", [{}])
        if content and "text" in content[0]:
            text = content[0]["text"]
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return {"error": text}
        return resp

    def close(self) -> None:
        self._proc.terminate()
        try:
            self._proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self._proc.kill()
            self._proc.wait(timeout=2)


# ---------------------------------------------------------------------------
# Test suite
# ---------------------------------------------------------------------------

def check_initialize(client: MCPClient) -> None:
    # Handshake is completed in the fixture; verify the server is alive by
    # checking it responds to tools/list (a lightweight probe).
    resp = client.call("tools/list", {})
    assert "result" in resp, f"server unresponsive after initialize: {resp}"
    assert "tools" in resp["result"], resp["result"]
    print("  PASS  initialize (handshake verified via tools/list)")


def check_tools_list(client: MCPClient) -> None:
    resp = client.call("tools/list", {})
    tools = [t["name"] for t in resp["result"]["tools"]]
    assert len(tools) <= 60, (
        f"Cursor catalog cap is 60, registered {len(tools)}"
    )
    required = {
        "init_check", "system_status", "harmonic_index_state",
        "cairrn_hub_state", "cairrn_hub_run", "cairrn_batch_run",
        "double_well_sim", "graph_status",
        "graph_annotate",
        "run_command", "list_commands",
        "code_audit", "cairrn_css_state", "cairrn_m3_gate", "cairrn_neuro_k",
        "bus_restart",
    }
    missing = required - set(tools)
    assert not missing, f"Missing tools: {missing}"
    print(f"  PASS  tools/list  ({len(tools)} tools registered)")


def check_auto_init(client: MCPClient) -> None:
    """Gate must be open at spawn — no init_check() required."""
    result = client.tool("harmonic_index_state")
    assert "error" not in result or result.get("error") != "session_not_initialized", (
        "Session gate was closed at spawn — auto-init failed"
    )
    assert "shards" in result or "step" in result, (
        f"Unexpected harmonic_index_state response: {result}"
    )
    print("  PASS  auto-init (gate open at spawn)")


def check_init_check_contract(client: MCPClient) -> None:
    """init_check() must return correct protocol contract fields."""
    result = client.tool("init_check")
    assert result.get("session_initialized") is True, result
    assert result.get("protocol_version") == "1.1.0", result
    assert result.get("gate_contract_hash") == "470e5b7f34748585", (
        f"gate_contract_hash mismatch: {result.get('gate_contract_hash')!r}"
    )
    assert result.get("base_hook_count") == 3, result
    assert result.get("hook_chain_version", 0) >= 3, result
    assert result.get("ready") is True, result
    print(f"  PASS  init_check contract  (hash={result['gate_contract_hash']})")


def check_cairrn_hub_state(client: MCPClient) -> None:
    """cairrn_hub_state must return all 5 hubs with coherence data."""
    result = client.tool("cairrn_hub_state")
    assert "hubs" in result, result
    hubs = result["hubs"]
    expected_hubs = {"HOME", "MATH", "CODE", "COMMANDS", "agent-context"}
    assert set(hubs.keys()) == expected_hubs, f"Missing hubs: {expected_hubs - set(hubs)}"

    for hub, data in hubs.items():
        assert "coherence" in data, f"{hub} missing coherence"
        assert "natural_shard" in data, f"{hub} missing natural_shard"
        assert "neg_exp_chi" in data, f"{hub} missing neg_exp_chi"
        assert 0.0 <= data["coherence"] <= 1.0, f"{hub} coherence out of range"
        assert 0 <= data["natural_shard"] <= 7, f"{hub} shard out of range"

    fp = result.get("neg_exp_fixed_point")
    assert abs(fp - (-0.5671432904097838)) < 1e-10, f"Fixed point wrong: {fp}"
    print(f"  PASS  cairrn_hub_state  (5 hubs, fixed_point={fp:.8f})")


def check_cairrn_hub_run(client: MCPClient) -> None:
    """cairrn_hub_run must apply all 4 layers, use effective hub, update temporal index."""
    result = client.tool("cairrn_hub_run", {"hub_name": "HOME", "metric": 0.8})
    assert result.get("hub") == "HOME", result
    assert result.get("requested_hub") == "HOME", f"requested_hub missing: {result}"
    assert result.get("basin") == "true_center", result
    assert "modulated_metric" in result, result
    assert "neg_exp_one_step" in result, result
    assert "coherence" in result, result
    assert "harmonic_step_after" in result, result
    assert "re_routed" in result, result
    assert "re_route_reason" in result, result

    # HOME (true_center, gravity=3.0) modulated = 0.8 × 3.0 = 2.4
    assert abs(result["modulated_metric"] - 2.4) < 1e-6, (
        f"modulation wrong: {result['modulated_metric']}"
    )
    print(
        f"  PASS  cairrn_hub_run/HOME  "
        f"(modulated={result['modulated_metric']:.3f}, "
        f"shard={result['natural_shard']}, "
        f"coherence={result['coherence']:.4f})"
    )


def check_cairrn_hub_run_z_scoring(client: MCPClient) -> None:
    """cairrn_hub_run with all 7 Z-space inputs must activate Layer 4."""
    result = client.tool("cairrn_hub_run", {
        "hub_name": "MATH",
        "metric": 1.0,
        "semantic_matrix_value": 0.8,
        "partial_deriv_1": 0.5,
        "z_activation": 1.2,
        "z_energy_cost": 0.3,
        "z_uncertainty": 0.1,
        "rizomic_distance": 1.0,
        "sigma_accumulator": 0.9,
    })
    assert result.get("z_active") is True, f"Z-scoring should be active: {result}"
    assert "neg_z" in result, f"neg_z missing: {result}"
    assert "z_shard" in result, f"z_shard missing: {result}"
    assert "z_coherence" in result, f"z_coherence missing: {result}"
    assert "z_coherent" in result, f"z_coherent missing: {result}"
    assert 0 <= result["z_shard"] <= 7, f"z_shard out of range: {result['z_shard']}"
    assert 0.0 <= result["z_coherence"] <= 1.0, f"z_coherence out of range: {result['z_coherence']}"
    print(
        f"  PASS  cairrn_hub_run/MATH (Z-active)  "
        f"neg_z={result['neg_z']:.4f}  "
        f"z_coh={result['z_coherence']:.4f}  "
        f"z_coherent={result['z_coherent']}"
    )


def check_cairrn_hub_run_no_z(client: MCPClient) -> None:
    """cairrn_hub_run without Z-space inputs must NOT activate Layer 4."""
    result = client.tool("cairrn_hub_run", {"hub_name": "CODE", "metric": 1.5})
    assert result.get("z_active") is None or result.get("z_active") is False, (
        f"Z-scoring should be inactive: {result}"
    )
    assert "neg_z" not in result, f"neg_z should be absent: {result}"
    print(
        f"  PASS  cairrn_hub_run/CODE (no-Z)  "
        f"hub={result['hub']}  coh={result['coherence']:.4f}"
    )


def check_cairrn_batch_run(client: MCPClient) -> None:
    """cairrn_batch_run must return results for all 5 hubs with shard_summary."""
    result = client.tool("cairrn_batch_run", {"metric": 1.0})
    assert result.get("n_hubs") == 5, f"Expected 5 hubs: {result}"
    assert "hubs" in result, result
    assert "shard_summary" in result, result

    expected_hubs = {"HOME", "MATH", "CODE", "COMMANDS", "agent-context"}
    assert set(result["hubs"].keys()) == expected_hubs, (
        f"Hub mismatch: {set(result['hubs'].keys())}"
    )
    for hub, hub_result in result["hubs"].items():
        assert "coherence" in hub_result, f"{hub} missing coherence"
        assert "modulated_metric" in hub_result, f"{hub} missing modulated_metric"
        assert "re_routed" in hub_result, f"{hub} missing re_routed"

    for hub, summary in result["shard_summary"].items():
        assert summary.get("runs", 0) >= 1, f"{hub} shard_summary shows 0 runs"

    print(
        f"  PASS  cairrn_batch_run  "
        f"(5 hubs, total_activation={result.get('total_activation', 0):.4f})"
    )


def check_cairrn_batch_run_z_scoring(client: MCPClient) -> None:
    """cairrn_batch_run with Z-space inputs must activate Layer 4 on all hubs."""
    result = client.tool("cairrn_batch_run", {
        "metric": 1.0,
        "semantic_matrix_value": 0.8,
        "partial_deriv_1": 0.5,
        "z_activation": 1.2,
        "z_energy_cost": 0.3,
        "z_uncertainty": 0.1,
        "rizomic_distance": 1.0,
        "sigma_accumulator": 0.9,
    })
    for hub, hub_result in result["hubs"].items():
        assert hub_result.get("z_active") is True, (
            f"{hub}: Z-scoring should be active, got: {hub_result}"
        )
        assert "neg_z" in hub_result, f"{hub}: neg_z missing"
        assert "z_coherence" in hub_result, f"{hub}: z_coherence missing"

    for hub, summary in result["shard_summary"].items():
        assert "z_active_runs" in summary, (
            f"{hub} shard_summary missing z_active_runs: {summary}"
        )

    print(
        f"  PASS  cairrn_batch_run (Z-active on all 5 hubs)  "
        f"hubs={list(result['hubs'])}"
    )


def check_neg_exp_sharding_order(client: MCPClient) -> None:
    """Natural shards must be ordered: boundary < mirror < true_center < white_peak < escape."""
    result = client.tool("cairrn_hub_state")
    hubs = result["hubs"]
    # agent-context → boundary (smallest chi) → smallest natural shard
    # COMMANDS → escape (largest chi) → largest natural shard
    ac_shard = hubs["agent-context"]["natural_shard"]
    cmd_shard = hubs["COMMANDS"]["natural_shard"]
    assert ac_shard < cmd_shard, (
        f"Expected agent-context shard ({ac_shard}) < COMMANDS shard ({cmd_shard})"
    )
    print(
        f"  PASS  neg_exp shard ordering  "
        f"(agent-context={ac_shard} < COMMANDS={cmd_shard})"
    )


def check_double_well_no_preinit(client: MCPClient) -> None:
    """Gated tools must work without a prior init_check() call."""
    result = client.tool("double_well_sim", {"x0": 1.5})
    assert "error" not in result or result.get("error") != "session_not_initialized", (
        "double_well_sim blocked without init — auto-init failed"
    )
    assert result.get("converged") is True, f"double_well_sim did not converge: {result}"
    print(f"  PASS  double_well_sim (auto-init)  final_x={result.get('final_x')}")


def check_graph_status_init_free(client: MCPClient) -> None:
    """graph_status is init-free and must work even if gate were closed."""
    result = client.tool("graph_status")
    assert "n_nodes" in result, f"graph_status missing n_nodes: {result}"
    print(f"  PASS  graph_status (init-free)  n_nodes={result['n_nodes']}")


def check_run_command_dispatch(client: MCPClient) -> None:
    """run_command parses slash strings through the command_dispatch pre-hook."""
    catalog = client.tool("list_commands")
    cmds = {row["command"] for row in catalog.get("commands", [])}
    assert "/read" in cmds and "/do" in cmds, catalog
    assert catalog.get("dispatcher") == "run_command"
    aliases = catalog.get("aliases") or {}
    assert aliases.get("/index") == "/read index", aliases
    assert aliases.get("/sim") == "/do sim", aliases

    idx = client.tool("run_command", {"command": "/read index"})
    assert idx.get("error") != "hook_violation", idx
    assert idx.get("dispatched_tool") == "harmonic_index_state" or "shards" in idx, idx

    legacy = client.tool("run_command", {"command": "/index"})
    assert legacy.get("error") != "hook_violation", legacy

    wf = client.tool("run_command", {"command": "/dev"})
    assert wf.get("kind") == "mcp", wf
    assert wf.get("mode") == "dev", wf

    help_do = client.tool("run_command", {"command": "/do help"})
    assert help_do.get("kind") == "dispatcher", help_do

    bad = client.tool("run_command", {"command": ""})
    assert bad.get("error") == "hook_violation", bad
    print(f"  PASS  run_command dispatch  (catalog n={catalog['n']})")


# ---------------------------------------------------------------------------
# pytest entry points
# ---------------------------------------------------------------------------

import pytest


@pytest.fixture(scope="module")
def client() -> MCPClient:
    c = MCPClient()
    yield c
    c.close()


def test_mcp_initialize(client):              check_initialize(client)
def test_mcp_tools_list(client):              check_tools_list(client)
def test_mcp_auto_init(client):               check_auto_init(client)
def test_mcp_init_check_contract(client):     check_init_check_contract(client)
def test_mcp_cairrn_hub_state(client):        check_cairrn_hub_state(client)
def test_mcp_cairrn_hub_run(client):          check_cairrn_hub_run(client)
def test_mcp_cairrn_hub_run_z(client):        check_cairrn_hub_run_z_scoring(client)
def test_mcp_cairrn_hub_run_no_z(client):     check_cairrn_hub_run_no_z(client)
def test_mcp_cairrn_batch_run(client):        check_cairrn_batch_run(client)
def test_mcp_cairrn_batch_run_z(client):      check_cairrn_batch_run_z_scoring(client)
def test_mcp_neg_exp_ordering(client):        check_neg_exp_sharding_order(client)
def test_mcp_gated_no_preinit(client):        check_double_well_no_preinit(client)
def test_mcp_graph_status_free(client):       check_graph_status_init_free(client)
def test_mcp_run_command_dispatch(client):    check_run_command_dispatch(client)


# ---------------------------------------------------------------------------
# Direct runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Starting MCP server subprocess...")
    c = MCPClient()
    try:
        check_initialize(c)
        check_tools_list(c)
        check_auto_init(c)
        check_init_check_contract(c)
        check_cairrn_hub_state(c)
        check_cairrn_hub_run(c)
        check_cairrn_hub_run_z_scoring(c)
        check_cairrn_hub_run_no_z(c)
        check_cairrn_batch_run(c)
        check_cairrn_batch_run_z_scoring(c)
        check_neg_exp_sharding_order(c)
        check_double_well_no_preinit(c)
        check_graph_status_init_free(c)
        print("\nAll tests passed.")
    finally:
        c.close()
