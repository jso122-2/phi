"""Environment probe and server startup init."""
from __future__ import annotations

import importlib.metadata
import sys
from typing import Any


def _raw_init_check() -> dict[str, Any]:
    """Check Python version, required packages, and critical imports."""
    results: dict[str, Any] = {}
    v = sys.version_info
    results["python"] = f"{v.major}.{v.minor}.{v.micro}"
    results["python_ok"] = v >= (3, 11)

    pkg_status: dict[str, str] = {}
    for pkg in ("numpy", "scipy", "mcp"):
        try:
            pkg_status[pkg] = importlib.metadata.version(pkg)
        except importlib.metadata.PackageNotFoundError:
            pkg_status[pkg] = "MISSING"
    results["packages"] = pkg_status
    results["packages_ok"] = all(v != "MISSING" for v in pkg_status.values())

    import_ok: dict[str, bool] = {}
    for module in (
        "sims.attractors", "sims.harmonic", "sims.ana_chi", "sims.temporal",
        "workers.base", "workers.cerberus", "workers.sentinel", "workers.oesophagus",
        "workers.cairrn",
        "graph.node", "graph.worker", "graph.linker", "graph.logger",
        "graph.ingestion", "graph.hub_classifier",
        "psspps.pipeline", "psspps.retriever", "psspps.scorer",
    ):
        try:
            __import__(module)
            import_ok[module] = True
        except Exception as exc:
            import_ok[module] = False
            results[f"import_error_{module}"] = str(exc)
    results["imports"] = import_ok
    results["imports_ok"] = all(import_ok.values())
    results["ready"] = results["python_ok"] and results["packages_ok"] and results["imports_ok"]
    return results


def _open_session_ledger() -> None:
    """Snapshot current harmonic state into the session ledger at gate-open."""
    try:
        from mcp_server._state import _harmonic_index, _session_ledger
        if _harmonic_index is not None and not _session_ledger.is_open():
            shards = [float(s.activation) for s in _harmonic_index.shards]
            _session_ledger.open(shards)
    except Exception as exc:
        print(f"[mcp_server._env_check] ledger open failed: {exc}", file=sys.stderr)


def _write_live_init_safe() -> None:
    """Write sessions/live-init.md from live _state data. Silent on failure."""
    try:
        from mcp_server._state import _harmonic_index, startup_errors
        from graph.node import _last_session_summary, write_live_init

        if _harmonic_index is not None:
            hub_acts = _harmonic_index.hub_activations()
            total = float(_harmonic_index.total_activation())
            steps = int(getattr(_harmonic_index, "_step_count", 0))
        else:
            hub_acts = {}
            total = 0.0
            steps = 0

        write_live_init(
            hub_activations=hub_acts,
            total_activation=total,
            step_count=steps,
            startup_errors=dict(startup_errors),
            last_session=_last_session_summary(),
        )
    except Exception as exc:
        print(f"[mcp_server._env_check] write_live_init failed: {exc}", file=sys.stderr)


def _startup_init() -> None:
    """
    Heal failed singletons, probe the environment, and open the session gate.

    Called from server.py at process startup and from retrigger_warmups() on
    watchdog stalls. Idempotent.
    """
    try:
        from mcp_server._reinit import _reinit_all_failed
        _reinit_all_failed()
    except Exception as exc:
        print(f"[mcp_server._gate] singleton re-init failed: {exc}", file=sys.stderr)
    try:
        if _raw_init_check().get("ready"):
            from mcp_server._gate import open_gate
            from mcp_server._state import ensure_harmonic_warm
            open_gate()
            ensure_harmonic_warm()
            _open_session_ledger()
            _write_live_init_safe()
            from mcp_server._context_hook import _register_psspps_context_hook
            from mcp_server._guards_graph import (
                _register_code_change_guard,
                _register_command_dispatch,
            )
            from mcp_server._guards_harmonic import (
                _register_harmonic_guard,
                _register_temporal_graph_guard,
            )
            from mcp_server._guards_search import _register_cairrn_guard, _register_search_guard
            from mcp_server._guards_sim import _register_phi_action_guard, _register_sim_guard
            _register_psspps_context_hook()
            _register_search_guard()
            _register_code_change_guard()
            _register_harmonic_guard()
            _register_cairrn_guard()
            _register_phi_action_guard()
            _register_sim_guard()
            _register_temporal_graph_guard()
            _register_command_dispatch()
    except Exception as exc:
        print(f"[mcp_server._gate] startup init failed: {exc}", file=sys.stderr)
