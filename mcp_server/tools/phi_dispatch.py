"""
phi_dispatch — MCP tools for the CAIRRN-bound action dispatcher.

All phi operations (clip, shuffle, inject, propagate, CAIRRN run,
temporal record) flow through a single CAIRRNDispatcher that gates
execution by CODE hub coherence.

Five tools:

    phi_enqueue   — add any phi action to the CAIRRN queue
    phi_step      — one dispatcher clock tick (gate check + dispatch)
    phi_queue     — inspect queue + gate state
    phi_flush     — force-dispatch all queued actions immediately
    phi_watchdog  — Pericles/Euler race-condition watchdog state

The dispatcher singleton is lazy-constructed on first call.
It shares state with all existing tools:
  - _harmonic_index from _state    (HarmonicIndex — gate signal + inject)
  - _temporal_index from _state    (TemporalShardIndex — TEMPORAL_REC)
  - phi_clip._get_session()        (PhiTracerSession — CLIP, SHUFFLE_*)
  - prefeed_shuffle._get_shuffle() (CAIRRNPrefeedShuffle — SHUFFLE_*)

Watchdog
--------
make_dispatcher() now auto-attaches a DoubleRouteWatchdog.  The watchdog
scores every DOUBLE_ROUTE / DOUBLE_ADVANCE event with the Pericles formula
and flags events inside the Euler boundary (coherence < W(1) ≈ 0.5671).
Call phi_watchdog() to inspect or phi_watchdog(clear=True) to reset.
"""
from __future__ import annotations

import threading
from typing import Any, Optional

from mcp_server._gate import requires_init
from mcp_server._state import _dom_queue, _harmonic_index, _temporal_index, mcp

_dispatcher: Optional[Any] = None   # CAIRRNDispatcher
_dispatcher_lock = threading.Lock()

# N_SHARDS is the harmonic ring width — used for shard-index validation in phi_enqueue.
_N_SHARDS: int = 8


def _get_dispatcher() -> Any:
    """Lazy-construct the CAIRRNDispatcher singleton."""
    global _dispatcher
    with _dispatcher_lock:
        if _dispatcher is not None:
            return _dispatcher

        from engine.cairrn_dispatch import make_dispatcher
        from mcp_server.tools.phi_clip import _get_session
        from mcp_server.tools.prefeed_shuffle import _get_shuffle

        session = _get_session()   # None if library not available
        shuffle = _get_shuffle()   # None if library not available

        _dispatcher = make_dispatcher(
            harmonic_index=_harmonic_index,
            session=session,
            shuffle=shuffle,
            temporal_index=_temporal_index,
            tau=10.0,
            attach_watchdog=True,          # Pericles/Euler watchdog auto-wired
            watchdog_window_ms=450.0,
        )
        n = len(getattr(_harmonic_index, "shards", []) or [])
        if n:
            global _N_SHARDS
            _N_SHARDS = n
        return _dispatcher


# ---------------------------------------------------------------------------
# phi_enqueue
# ---------------------------------------------------------------------------


@mcp.tool()
@requires_init
def phi_enqueue(
    kind: str,
    query: Optional[str] = None,
    hub_name: Optional[str] = None,
    shard_index: Optional[int] = None,
    value: Optional[float] = None,
    metric: Optional[float] = None,
    top_k: int = 5,
    alpha: float = 0.5,
    steps: int = 1,
    mode: str = "local",
    priority: int = 0,
) -> dict[str, Any]:
    """
    Enqueue a phi action in the CAIRRN dispatcher.

    CAIRRN will gate execution based on CODE hub coherence.
    Prefeedable actions (CLIP, SHUFFLE_NEXT) are pre-computed silently
    while coherence builds; they execute instantly when the gate opens.

    Parameters
    ----------
    kind       : action kind — one of:
                   CLIP | SHUFFLE_NEXT | SHUFFLE_SEED |
                   HUB_INJECT | SHARD_INJECT | PROPAGATE |
                   CAIRRN_RUN | TEMPORAL_REC
    query      : query string (CLIP only)
    hub_name   : hub name (HUB_INJECT, CAIRRN_RUN, TEMPORAL_REC)
    shard_index: shard index 0–7 (SHARD_INJECT only)
    value      : activation value (HUB_INJECT, SHARD_INJECT, TEMPORAL_REC)
    metric     : CAIRRN metric (CAIRRN_RUN only, default 1.0)
    top_k      : number of tracks to return (CLIP only, default 5)
    alpha      : H-space blend weight (CLIP only, default 0.5)
    steps      : propagation steps (PROPAGATE only, default 1)
    mode       : propagation mode (PROPAGATE only, default "local")
    priority   : queue priority — negative=urgent, 0=normal, positive=deferred
    """
    with _dom_queue.gate("phi_enqueue"):
        from engine.cairrn_dispatch import PhiAction, PhiActionKind

        kind_upper = kind.strip().upper()
        try:
            action_kind = PhiActionKind(kind_upper)
        except ValueError:
            valid = [k.value for k in PhiActionKind]
            return {"error": f"unknown_kind: {kind!r}", "valid_kinds": valid}

        # Build payload from non-None args relevant to this kind
        payload: dict[str, Any] = {}
        if query is not None:
            payload["query"] = query
        if hub_name is not None:
            payload["hub_name"] = hub_name
        if shard_index is not None:
            if action_kind == PhiActionKind.SHARD_INJECT:
                if shard_index < 0 or shard_index >= _N_SHARDS:
                    return {
                        "error": "shard_index_out_of_range",
                        "shard_index": shard_index,
                        "valid_range": [0, _N_SHARDS - 1],
                    }
            payload["shard_index"] = shard_index
        if value is not None:
            payload["value"] = value
        if metric is not None:
            payload["metric"] = metric
        if action_kind == PhiActionKind.CLIP:
            payload.setdefault("top_k", top_k)
            payload.setdefault("alpha", alpha)
        if action_kind == PhiActionKind.PROPAGATE:
            payload["steps"] = steps
            payload["mode"] = mode

        action = PhiAction(kind=action_kind, payload=payload, priority=priority)
        d = _get_dispatcher()
        depth = d.enqueue(action)

        return {
            "queued":    True,
            "action_id": action.action_id,
            "kind":      action_kind.value,
            "priority":  priority,
            "queue_depth": depth,
            "gate_open": d.gate_open,
            "coherence": round(d.coherence, 4),
        }


# ---------------------------------------------------------------------------
# phi_step
# ---------------------------------------------------------------------------


# Slash-only — Cursor catalog cap 60. Call via run_command("/phi-step").
@requires_init
def phi_step() -> dict[str, Any]:
    """
    One CAIRRN dispatcher clock tick.

    Gate closed (coherence < 0.5671):
        Prefeed runs for the head action if prefeedable (CLIP, SHUFFLE_NEXT).
        Queue unchanged — nothing dispatched.

    Gate open (coherence ≥ 0.5671):
        Head action dispatched (uses prefeed cache if available → zero latency).
        CAIRRN CODE hub pipeline fires to update shard state.
        steps_since_tick resets to 0.

    Call this in a loop (or on a clock) to let CAIRRN drain the queue.
    """
    with _dom_queue.gate("phi_step"):
        d = _get_dispatcher()
        result = d.step()
        return result.as_dict()


# ---------------------------------------------------------------------------
# phi_queue
# ---------------------------------------------------------------------------


@mcp.tool()
@requires_init
def phi_queue() -> dict[str, Any]:
    """
    Inspect the CAIRRN dispatcher queue and gate state.

    Returns the full queue (ordered by priority + enqueue time),
    coherence, gate status, tick history, and prefeed cache depth.
    """
    with _dom_queue.gate("phi_queue"):
        d = _get_dispatcher()
        return {
            **d.state(),
            "history": d.history_snapshot(5),
        }


# ---------------------------------------------------------------------------
# phi_flush
# ---------------------------------------------------------------------------


# Slash-only — Cursor catalog cap 60. Call via run_command("/phi-flush").
@requires_init
def phi_flush() -> dict[str, Any]:
    """
    Force-dispatch all queued actions immediately, bypassing the coherence gate.

    Use when you need all pending operations executed now regardless of
    CAIRRN state.  Each action is dispatched in priority order.
    Returns a list of per-action results.
    """
    with _dom_queue.gate("phi_flush"):
        d = _get_dispatcher()
        from engine.cairrn_dispatch import PhiAction

        results: list[dict] = []
        while d.queue_depth > 0:
            # Peek at next action, force-dispatch it
            with d._lock:
                if not d._queue:
                    break
                action = d._queue.pop(0)
            result = d.force_dispatch(action)
            results.append(result.as_dict())

        return {
            "flushed":    len(results),
            "results":    results,
            "queue_depth": d.queue_depth,
            "coherence":  round(d.coherence, 4),
        }


# ---------------------------------------------------------------------------
# phi_watchdog
# ---------------------------------------------------------------------------


@mcp.tool()
@requires_init
def phi_watchdog(clear: bool = False) -> dict[str, Any]:
    """
    Pericles / Euler race-condition watchdog state for the CAIRRN dispatcher.

    Returns the DoubleRouteWatchdog state: every DOUBLE_ROUTE / DOUBLE_ADVANCE
    event scored with the Pericles formula and flagged when inside the Euler
    boundary (coherence < W(1) ≈ 0.5671).

    Parameters
    ----------
    clear : reset all recorded events and per-kind timestamps (default False)
    """
    with _dom_queue.gate("phi_watchdog"):
        d = _get_dispatcher()
        wd = d._dr_watchdog
        if wd is None:
            return {
                "error": "watchdog_not_attached",
                "hint": "Dispatcher was created with attach_watchdog=False",
            }
        if clear:
            wd.clear()
            return {"cleared": True, "total_events": 0}
        return wd.state()
