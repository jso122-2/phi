"""Temporal sharding index tools: state, vector, coherence, record, advance, reset."""
from __future__ import annotations

from typing import Any

from mcp_server._gate import requires_init
from mcp_server._state import _dom_queue, _harmonic_index, _temporal_index, _vault_hub, mcp
from sims.temporal import CAIRRN_HUBS as _CAIRRN_HUBS


@mcp.tool()
@requires_init
def temporal_state() -> dict[str, Any]:
    """
    Return the full state of the temporal sharding index.

    Per-hub temporal traces and decay rates (Ana-Chi memory_decay):
        HOME  0.98 | MATH  0.95 | CODE  0.93 | COMMANDS  0.90 | agent-context  0.90
    """
    with _dom_queue.gate("temporal_state"):
        return _temporal_index.state()


# Slash-only — Cursor catalog cap 60. Call via run_command("/temporal-vector").
@requires_init
def temporal_vector() -> dict[str, Any]:
    """
    Return the (n_hubs × n_windows) temporal activation matrix.

    Rows = CAIRRN hubs (HOME, MATH, CODE, COMMANDS, agent-context).
    Cols = temporal lags t = 0 (now) … T-1 (oldest).
    Also returns Ana-Chi state: χ, coherence, and rattling proximity.
    """
    with _dom_queue.gate("temporal_vector"):
        return {**_temporal_index.vector_state(), "ana_chi": _temporal_index.ana_chi_state()}


# Slash-only — Cursor catalog cap 60. Call via run_command("/temporal-coherence").
@requires_init
def temporal_coherence() -> dict[str, Any]:
    """
    Return the Ana-Chi coherence of the temporal index.

    coherence = exp(-|χ_eff - 1.5414| / 0.40)  — 1.0 at HOME, lower at extremes.
    """
    with _dom_queue.gate("temporal_coherence"):
        return _temporal_index.ana_chi_state()


@requires_init
def temporal_record(hub_name: str, value: float = 1.0) -> dict[str, Any]:
    """
    Record activation for a CAIRRN hub in the temporal index at t=0 (now).

    Parameters
    ----------
    hub_name : CAIRRN hub — HOME, MATH, CODE, COMMANDS, agent-context
    value    : activation amount (default 1.0)
    """
    with _dom_queue.gate("temporal_record"):
        if hub_name not in _CAIRRN_HUBS:
            return {"error": "unknown_hub", "hub_name": hub_name, "valid_hubs": list(_CAIRRN_HUBS)}
        _temporal_index.record(hub_name, value)
        state = _temporal_index.state()
        _vault_hub.push_all(harmonic=_harmonic_index.state())
        return {"recorded": True, "hub": hub_name, "value": value, **state}


@requires_init
def temporal_advance(steps: int = 1) -> dict[str, Any]:
    """
    Advance the temporal index by `steps` clock ticks.

    Each tick: decay all window activations → prepend empty t=0 → drop oldest.

    Parameters
    ----------
    steps : number of clock ticks (default 1, min 1)
    """
    with _dom_queue.gate("temporal_advance"):
        if steps < 1:
            return {"error": "steps must be >= 1"}
        new_clock = _temporal_index.advance(steps=steps)
        state = _temporal_index.state()
        _vault_hub.push_all(harmonic=_harmonic_index.state())
        return {"advanced": True, "steps": steps, "clock": new_clock, **state}


@requires_init
def temporal_reset() -> dict[str, Any]:
    """Reset the temporal index — zero all activations and reset clock to 0."""
    with _dom_queue.gate("temporal_reset"):
        _temporal_index.reset()
        state = _temporal_index.state()
        _vault_hub.push_all(harmonic=_harmonic_index.state())
        return {"reset": True, **state}
