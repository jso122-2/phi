"""
mcp_server._runtime_ledger — Runtime MCP tool-call enforcement ledger.

Agents must use the canonical MCP tool calls at runtime.  This module
enforces that contract by registering a ``runtime_ledger`` hook at
*initialisation time* that fires before every subsequent tool call.

What it does
------------
1. **Classification** — every tool call is classified into a family:
   ``init | search | dispatch | graph | sim | playback | system | other``.

2. **Sequence enforcement** — search / dispatch / graph / sim / playback
   families require ``init_check()`` to have been called first.  If the
   gate is closed when a family tool is called, a ``HookViolation`` is
   raised with a clear message (``action_required: "init_check()"``) and
   the call is aborted.  This is a *runtime* complement to the spawn-gate
   check — it covers cases where the gate was closed after initial spawn
   (e.g. a fresh subprocess or a late MCP attach).

3. **Ledger recording** — every tool call is appended to a
   ``SessionCallLedger`` ring-buffer: timestamp, tool name, family, and
   (on violation) the error.  The ledger is inspectable via the
   ``session_audit()`` MCP tool.

4. **Bypass detection** — if a ``run_command`` call contains a payload
   that looks like it is shelling out to a known bypass path (e.g.
   ``psspps.find``, ``run_psspps``, ``run_find``), a ``HookViolation``
   is raised.  Agents must call ``find_query`` / ``psspps_query`` directly.

Hook registration
-----------------
``_register_runtime_ledger()`` is called from ``_startup_init()`` — the
same function that registers all other guards — so the enforcement is live
from the first gated tool call onward.

Inspection
----------
``LEDGER.state()`` returns a serialisable snapshot:
    {
      "total_calls":    int,
      "by_family":      {family: count},
      "violations":     int,
      "calls":          [...last N call records...]
    }

Call the ``session_audit()`` MCP tool to read the ledger from an agent.
"""
from __future__ import annotations

import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Final

from mcp_server.hooks import HookViolation
from mcp_server.hooks import REGISTRY as _hook_registry

# ---------------------------------------------------------------------------
# Tool → family mapping
# ---------------------------------------------------------------------------

#: Canonical family for every registered MCP tool.
#: Tools not listed here fall into "other".
TOOL_FAMILY: Final[dict[str, str]] = {
    # ── init ─────────────────────────────────────────────────────────────────
    "init_check":          "init",
    "system_status":       "init",
    # ── search — canonical MCP tools (agents MUST use these) ──────────────
    "find_query":          "search",
    "psspps_query":        "search",
    # ── dispatch — canonical MCP tools ────────────────────────────────────
    "phi_enqueue":         "dispatch",
    "phi_step":            "dispatch",
    "phi_queue":           "dispatch",
    "phi_flush":           "dispatch",
    "phi_watchdog":        "dispatch",
    # ── playback ──────────────────────────────────────────────────────────
    "gemini_clip":         "playback",
    "shuffle_seed":        "playback",
    "shuffle_next":        "playback",
    # ── graph ─────────────────────────────────────────────────────────────
    "graph_commit":        "graph",
    "graph_ingest":        "graph",
    "graph_ingest_source": "graph",
    "graph_traverse":      "graph",
    "graph_annotate":      "graph",
    "graph_link":          "graph",
    "graph_sync_manifest": "graph",
    "graph_track_sync":    "graph",
    "graph_status":        "graph",
    "graph_clean":         "graph",
    "graph_nest":          "graph",
    "graph_track_state":   "graph",
    # ── harmonic ──────────────────────────────────────────────────────────
    "harmonic_inject":     "harmonic",
    "hub_inject":          "harmonic",
    "harmonic_propagate":  "harmonic",
    "harmonic_set_goal":   "harmonic",
    "harmonic_state":      "harmonic",
    "hub_state":           "harmonic",
    # ── sim ───────────────────────────────────────────────────────────────
    "double_well_sim":     "sim",
    "langevin_sim":        "sim",
    "neg_exp_sim":         "sim",
    "sweep_attractors":    "sim",
    "mfpt_estimate":       "sim",
    "ana_chi_sim":         "sim",
    # ── cairrn ────────────────────────────────────────────────────────────
    "cairrn_hub_run":      "cairrn",
    "cairrn_batch_run":    "cairrn",
    "cairrn_neuro_k":      "cairrn",
    "temporal_record":     "cairrn",
    # ── system / meta (always allowed, no family gate) ────────────────────
    "dom_queue_state":     "system",
    "list_hooks":          "system",
    "register_hook":       "system",
    "run_command":         "system",
    "list_commands":       "system",
    "bus_poll":            "system",
    "bus_status":          "system",
    "forecast_state":      "system",
    "session_audit":       "system",
    "watchdog_state":      "system",
    "retrigger_warmups":   "system",
    "run_tests":           "system",
}

#: Families that require the session gate to be open before they can run.
_GATED_FAMILIES: Final[frozenset[str]] = frozenset({
    "search", "dispatch", "playback", "graph", "harmonic", "sim", "cairrn",
})

#: Substrings that indicate a run_command payload is trying to bypass MCP search.
_BYPASS_PATTERNS: Final[tuple[str, ...]] = (
    "psspps.find",
    "run_psspps",
    "run_find",
    "psspps.pipeline",
    "psspps.retriever",
)


# ---------------------------------------------------------------------------
# Call record
# ---------------------------------------------------------------------------

@dataclass
class CallRecord:
    seq:       int
    ts:        float
    tool:      str
    family:    str
    violation: str | None = None

    def as_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "seq":    self.seq,
            "ts":     round(self.ts, 3),
            "tool":   self.tool,
            "family": self.family,
        }
        if self.violation:
            d["violation"] = self.violation
        return d


# ---------------------------------------------------------------------------
# Session call ledger
# ---------------------------------------------------------------------------

class SessionCallLedger:
    """
    Bounded ring-buffer of MCP tool calls for the current session.

    Thread-safe.  Append-only: records are never removed.
    """

    def __init__(self, maxlen: int = 500) -> None:
        self._maxlen = maxlen
        self._calls:  list[CallRecord] = []
        self._seq:    int = 0
        self._lock  = threading.Lock()
        self._by_family: dict[str, int] = {}
        self._violations: int = 0

    def record(
        self,
        tool: str,
        family: str,
        violation: str | None = None,
    ) -> CallRecord:
        """Append one call record.  Returns the record."""
        with self._lock:
            self._seq += 1
            rec = CallRecord(
                seq=self._seq,
                ts=time.time(),
                tool=tool,
                family=family,
                violation=violation,
            )
            self._calls.append(rec)
            if len(self._calls) > self._maxlen:
                self._calls = self._calls[-self._maxlen:]
            self._by_family[family] = self._by_family.get(family, 0) + 1
            if violation:
                self._violations += 1
        return rec

    def state(self, tail: int = 50) -> dict[str, Any]:
        """Return a serialisable snapshot of the ledger."""
        with self._lock:
            calls = list(self._calls[-tail:])
            by_family = dict(self._by_family)
            total = self._seq
            violations = self._violations
        return {
            "total_calls": total,
            "by_family":   by_family,
            "violations":  violations,
            "tail":        tail,
            "calls":       [c.as_dict() for c in calls],
        }


# ---------------------------------------------------------------------------
# Process-level singleton
# ---------------------------------------------------------------------------

LEDGER = SessionCallLedger()

# ---------------------------------------------------------------------------
# Hook registration
# ---------------------------------------------------------------------------

_ledger_registered = threading.Event()


def _register_runtime_ledger() -> None:
    """
    Register the ``runtime_ledger`` hook.  Idempotent.

    Called from ``_startup_init()`` so it is wired in on every server
    start — desktop MCP and Cloud stdio MCP alike.
    """
    if _ledger_registered.is_set():
        return

    def runtime_ledger_hook(tool_name: str, kwargs: dict) -> None:
        """
        Runtime enforcement hook — fires before every MCP tool call.

        1. Classify the tool into a family.
        2. For gated families (search, dispatch, graph, …), verify the
           session gate is open; abort with HookViolation if not.
        3. Detect run_command bypass attempts (shelling out to psspps etc.).
        4. Record the call (or violation) to the session ledger.
        """
        family = TOOL_FAMILY.get(tool_name, "other")

        # ── Gated family check ────────────────────────────────────────────
        if family in _GATED_FAMILIES:
            from mcp_server._gate import is_initialized
            if not is_initialized():
                violation = (
                    f"runtime_ledger: '{tool_name}' ({family} family) requires "
                    "an initialized session.  Call init_check() first."
                )
                LEDGER.record(tool_name, family, violation=violation)
                raise HookViolation(violation)

        # ── Bypass detection ──────────────────────────────────────────────
        if tool_name == "run_command":
            command = str(kwargs.get("command", ""))
            for pattern in _BYPASS_PATTERNS:
                if pattern in command:
                    violation = (
                        f"runtime_ledger: run_command contains '{pattern}' — "
                        "use find_query() or psspps_query() MCP tools instead of "
                        "shelling out to the PSSPPS pipeline directly."
                    )
                    LEDGER.record(tool_name, family, violation=violation)
                    raise HookViolation(violation)

        # ── Record ────────────────────────────────────────────────────────
        LEDGER.record(tool_name, family)
        _log_call(tool_name, family)

    _hook_registry.register(
        name="runtime_ledger",
        description=(
            "Runtime enforcement of canonical MCP tool usage. "
            "Classifies every call by family (init/search/dispatch/graph/sim/…), "
            "enforces gated-family init requirement, detects bypass attempts, "
            "and records every call to the session ledger (session_audit())."
        ),
        fn=runtime_ledger_hook,
    )
    _ledger_registered.set()


def _log_call(tool_name: str, family: str) -> None:
    """Lightweight stderr trace — visible in MCP console but not in tool results."""
    print(
        f"[ledger] {family}:{tool_name}",
        file=sys.stderr,
        flush=True,
    )
