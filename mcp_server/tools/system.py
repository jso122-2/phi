"""System / health tools: init_check, system_status, run_tests, hooks, watchdog."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from mcp_server._gate import (
    PROTOCOL_VERSION,
    _GATE_CONTRACT_HASH,
    _raw_init_check,
    open_gate,
    requires_init,
)
from mcp_server._state import _dom_queue, mcp, startup_errors as _startup_errors
from mcp_server.hooks import BASE_HOOK_COUNT as _BASE_HOOK_COUNT
from mcp_server.hooks import REGISTRY as _hook_registry
from mcp_server.tools.phi_clip import is_warmed as _phi_clip_warmed
from sims.attractors import ALPHA


def _init_account_path() -> str | None:
    """Return the vault-relative path to live-init.md if it exists."""
    try:
        from graph.node import SESSIONS_DIR, VAULT_ROOT
        p = SESSIONS_DIR / "live-init.md"
        if p.exists():
            return str(p.relative_to(VAULT_ROOT))
        return None
    except Exception:
        return None


def _tool_load_errors() -> dict[str, str]:
    """Return tool-module load failures (populated during tools/__init__ import)."""
    try:
        from mcp_server import tools as _tools_pkg
        return dict(getattr(_tools_pkg, "load_errors", {}))
    except Exception:
        return {}


@mcp.tool()
def init_check() -> dict[str, Any]:
    """
    Verify that the spotify-rip environment is correctly initialised.

    Checks Python version, required packages, and that the sims / workers
    packages are importable.  Returns a status dict including the protocol
    version and gate contract hash for agent verification.

    Also reports any singleton or tool-module failures that occurred at
    server startup (startup_errors, tool_load_errors).
    """
    with _dom_queue.gate("init_check"):
        results = _raw_init_check()
        tool_load_errors = _tool_load_errors()
        startup_ok = not _startup_errors and not tool_load_errors

        if results["ready"] and startup_ok:
            open_gate()
            results["session_initialized"] = True
        elif results["ready"]:
            # Env is healthy but some singletons/modules failed — open gate
            # for the tools that did load; agents can see what's degraded.
            open_gate()
            results["session_initialized"] = True

        results["hook_chain_version"] = _hook_registry.version
        results["base_hook_count"] = _BASE_HOOK_COUNT
        results["protocol_version"] = PROTOCOL_VERSION
        results["gate_contract_hash"] = _GATE_CONTRACT_HASH
        results["phi_clip_ready"] = _phi_clip_warmed()
        results["startup_errors"] = dict(_startup_errors)
        results["tool_load_errors"] = tool_load_errors
        results["startup_ok"] = startup_ok
        results["init_account"] = _init_account_path()

        # Spawn gate: include session context in the init_check response so
        # the agent receives live-init.md content directly in the tool result.
        # emit_spawn_context() was already called eagerly at server startup;
        # this covers the case where the agent calls init_check() before the
        # eager emit has fired or when running in a non-cloud context.
        try:
            from mcp_server._spawn_gate import emit_spawn_context, spawn_context_dict
            emit_spawn_context()   # idempotent — no-op if already emitted
            results["spawn_context"] = spawn_context_dict()
        except Exception:
            pass

        return results


@mcp.tool()
def system_status() -> dict[str, Any]:
    """One-shot system health report: environment, harmonic index, package versions."""
    from mcp_server._state import _harmonic_index, _vault_hub

    with _dom_queue.gate("system_status"):
        env = _raw_init_check()
        tool_load_errors = _tool_load_errors()

        harmonic_info: dict[str, Any]
        if _harmonic_index is not None:
            idx = _harmonic_index.state()
            peak = _harmonic_index.peak_shard()
            harmonic_info = {
                "step":              idx["step"],
                "n_harmonics":       idx["n_harmonics"],
                "total_activation":  idx["total_activation"],
                "peak_shard":        peak.index,
                "peak_basin_centre": round(peak.basin_centre, 4),
            }
        else:
            idx = {}
            harmonic_info = {"error": "harmonic_index_unavailable"}

        if env["ready"]:
            open_gate()

        queue_state = _dom_queue.state()
        _vault_hub.push_all(harmonic=idx, queue=queue_state)
        from mcp_server._state import _hot_loader, _retrigger_count
        hot_info: dict[str, Any]
        if _hot_loader is not None:
            hot_info = {**_hot_loader.summary(), "retrigger_count": _retrigger_count}
        else:
            hot_info = {"error": "hot_loader_unavailable", "retrigger_count": _retrigger_count}
        bus_info: dict[str, Any]
        try:
            from mcp_server.bus.client import get_client, worker_alive, worker_pid
            client = get_client()
            bus_info = client.status() if client is not None else {
                "connected": False,
                "worker_alive": worker_alive(),
                "worker_pid": worker_pid(),
            }
            if client is not None:
                bus_info["connected"] = True
        except Exception as exc:
            bus_info = {"error": str(exc)}
        return {
            "environment":         env,
            "harmonic_index":      harmonic_info,
            "alpha":               ALPHA,
            "ready":               env["ready"],
            "session_initialized": env["ready"],
            "hook_chain_version":  _hook_registry.version,
            "base_hook_count":     _BASE_HOOK_COUNT,
            "protocol_version":    PROTOCOL_VERSION,
            "gate_contract_hash":  _GATE_CONTRACT_HASH,
            "dom_queue":           queue_state,
            "hot_loader":          hot_info,
            "bus":                 bus_info,
            "phi_clip_ready":      _phi_clip_warmed(),
            "startup_errors":      dict(_startup_errors),
            "tool_load_errors":    tool_load_errors,
            "startup_ok":          not _startup_errors and not tool_load_errors,
            "init_account":        _init_account_path(),
        }


_RUN_TESTS_MODES = frozenset({"all", "fast", "mcp", "unit"})
"""
Test-run modes for run_tests():

  all   (default) — full pytest suite; same as calling pytest with no filters.
  fast            — skip tests marked @pytest.mark.slow or @pytest.mark.integration.
                    Best for tight dev loops.
  mcp             — only MCP server tests (wire protocol, dom_queue, gate).
                    Fastest signal on whether the server contract is intact.
  unit            — exclude @pytest.mark.integration tests; includes slow unit tests.
"""

_MCP_TEST_FILES = [
    "tests/test_mcp_wire.py",
    "tests/test_dom_queue.py",
    "tests/test_gate.py",
    "tests/test_mcp_robust.py",
    "tests/test_bus.py",
    "tests/test_commands.py",
]

# mcp_server/tools/system.py → mcp_server/tools → mcp_server → package root
_PACKAGE_ROOT = Path(__file__).resolve().parents[2]


def _pytest_cwd() -> str:
    """Directory that contains tests/ — independent of the MCP process cwd."""
    return str(_PACKAGE_ROOT)


@mcp.tool()
@requires_init
def run_tests(mode: str = "all", coverage: bool = False) -> dict[str, Any]:
    """
    Run the pytest suite and return pass/fail counts.

    Modes
    -----
    all   (default) — full suite; no filters applied.
    fast            — skip slow + integration tests; ideal for tight dev loops.
    mcp             — only MCP server tests (wire, dom_queue, gate); fastest
                      signal on whether the server contract is intact.
    unit            — exclude integration tests; includes slow unit tests.

    Parameters
    ----------
    mode     : one of "all" | "fast" | "mcp" | "unit"
    coverage : collect coverage report (requires pytest-cov; only for mode="all")
    """
    if mode not in _RUN_TESTS_MODES:
        return {
            "error":       "unknown_mode",
            "mode":        mode,
            "valid_modes": sorted(_RUN_TESTS_MODES),
        }

    with _dom_queue.gate("run_tests"):
        cmd = [sys.executable, "-m", "pytest", "-v", "--tb=short"]

        if mode == "all":
            if coverage:
                cmd += [
                    "--cov=sims", "--cov=workers",
                    "--cov=graph", "--cov=psspps",
                    "--cov-report=term-missing",
                ]
        elif mode == "fast":
            cmd += ["-m", "not slow and not integration"]
        elif mode == "mcp":
            cmd += _MCP_TEST_FILES
        elif mode == "unit":
            cmd += ["-m", "not integration"]

        env = os.environ.copy()
        env["PYTHONPATH"] = str(_PACKAGE_ROOT) + (
            os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
        )
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=180,
                cwd=_PACKAGE_ROOT,
                env=env,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
            stderr = (exc.stderr or "") if isinstance(exc.stderr, str) else ""
            return {
                "mode":      mode,
                "error":     "timeout",
                "timeout_s": 180,
                "exit_code": None,
                "passed":    0,
                "failed":    0,
                "errors":    1,
                "all_ok":    False,
                "stdout":    stdout[-4000:],
                "stderr":    stderr[-1000:],
            }
        except OSError as exc:
            return {
                "mode":      mode,
                "error":     "pytest_failed_to_start",
                "message":   str(exc),
                "all_ok":    False,
            }

        lines = proc.stdout.splitlines()
        return {
            "mode":      mode,
            "exit_code": proc.returncode,
            "passed":    sum(1 for ln in lines if " PASSED" in ln),
            "failed":    sum(1 for ln in lines if " FAILED" in ln),
            "errors":    sum(1 for ln in lines if " ERROR"  in ln),
            "all_ok":    proc.returncode == 0,
            "stdout":    proc.stdout[-4000:] if len(proc.stdout) > 4000 else proc.stdout,
            "stderr":    proc.stderr[-1000:] if proc.stderr else "",
        }


@mcp.tool()
def dom_queue_state() -> dict[str, Any]:
    """Inspect the DOM Request Queue — all 7 houses, call counts, and active state."""
    # Late import: reflects any _reinit_dom_queue() that ran after module load.
    from mcp_server._state import _dom_queue as _live_dom_queue
    with _live_dom_queue.gate("dom_queue_state"):
        return _live_dom_queue.state()


# Slash-only — Cursor catalog cap 60. Call via run_command("/coherence-state").
def coherence_state(tail: int = 10) -> dict[str, Any]:
    """
    Return the harmonic trajectory for this session (init-free).

    Shows the initial shard snapshot captured at gate-open, the current state,
    the per-shard and per-hub cumulative delta, and the last ``tail`` mutation
    entries.  Also exposes the BMAD-relevant pressure scalars so agents can
    understand why admission predicates are throttling.

    Parameters
    ----------
    tail : number of recent ledger entries to include (default 10, max 50)
    """
    from mcp_server._state import _session_ledger
    tail = max(0, min(int(tail), 50))
    if not _session_ledger.is_open():
        return {
            "initialized": False,
            "message": "ledger not yet opened — gate has not fired",
        }
    data = _session_ledger.to_dict(tail=tail)
    data["bmad_signals"] = {
        "total_pressure":  data["total_pressure"],
        "code_pressure":   data["code_pressure"],
        "n_mutations":     data["n_mutations"],
    }
    return data


@mcp.tool()
def list_hooks() -> dict[str, Any]:
    """Return the current state of the append-only pre-tool hook chain."""
    with _dom_queue.gate("list_hooks"):
        return _hook_registry.state()


@mcp.tool()
def register_hook(name: str, description: str) -> dict[str, Any]:
    """
    Register a named placeholder hook in the append-only hook chain.

    Re-registering an existing name is a no-op (idempotent).  Placeholders
    cannot be removed once registered.

    Parameters
    ----------
    name        : unique hook name (snake_case recommended)
    description : what this hook slot is reserved for
    """
    with _dom_queue.gate("register_hook"):
        def _noop(tool_name: str, kwargs: dict) -> None:
            pass
        version = _hook_registry.register(name=name, description=f"[placeholder] {description}", fn=_noop)
        return {
            "registered":       name,
            "hook_chain_version": version,
            "chain":            _hook_registry.state(),
        }


@mcp.tool()
def session_audit(tail: int = 50) -> dict[str, Any]:
    """
    Return the runtime MCP call ledger for this session.

    Every tool call made since server startup is recorded here with its
    timestamp, tool name, and family classification
    (init / search / dispatch / graph / sim / playback / cairrn / harmonic /
    system / other).  Violations (gate failures, bypass attempts) are flagged.

    Use this to verify that your session is using the canonical MCP tools
    correctly and in the right sequence.

    Parameters
    ----------
    tail : number of recent call records to return (default 50, max 500)
    """
    with _dom_queue.gate("session_audit"):
        from mcp_server._runtime_ledger import LEDGER
        tail = max(1, min(int(tail), 500))
        state = LEDGER.state(tail=tail)
        state["tool_families"] = {
            "search":   ["find_query", "psspps_query"],
            "dispatch": ["phi_enqueue", "phi_step", "phi_queue", "phi_flush", "phi_watchdog"],
            "playback": ["gemini_clip", "shuffle_seed", "shuffle_next"],
            "graph":    ["graph_commit", "graph_ingest", "graph_traverse", "graph_annotate"],
            "init":     ["init_check", "system_status"],
        }
        state["enforcement"] = {
            "gated_families": sorted(["search", "dispatch", "playback", "graph", "harmonic", "sim", "cairrn"]),
            "bypass_patterns": ["psspps.find", "run_psspps", "run_find", "psspps.pipeline"],
            "hook": "runtime_ledger",
        }
        return state


@mcp.tool()
@requires_init
def watchdog_state() -> dict[str, Any]:
    """
    Inspect the race condition watchdog — stall events, contention events,
    and current watchdog configuration.
    """
    with _dom_queue.gate("watchdog_state"):
        watchdog = getattr(_dom_queue, "_watchdog", None)
        if watchdog is None:
            return {"error": "watchdog_not_initialized"}
        from mcp_server._state import _hot_loader, _retrigger_count
        payload = watchdog.state()
        payload["retrigger_count"] = _retrigger_count
        if _hot_loader is not None:
            payload["hot_loader"] = _hot_loader.summary()
        return payload
