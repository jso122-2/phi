"""Harmonic index tools: state, propagate, inject, hub ops, reset, goal."""
from __future__ import annotations

from typing import Any

import numpy as np

from mcp_server._gate import requires_init
from mcp_server._state import (
    _dom_queue,
    _harmonic_index,
    _ticket_clipper,
    _vault_hub,
    mcp,
    save_harmonic_snapshot,
)
from sims.harmonic import HUB_NAMES, HUB_SHARD_MAP, cosine_path_count


def _ledger_record(tool: str) -> None:
    """Record current harmonic state into the session ledger (silent on failure)."""
    try:
        from mcp_server._state import _session_ledger
        if _harmonic_index is None or not _session_ledger.is_open():
            return
        shards = [float(s.activation) for s in _harmonic_index.shards]
        step = int(getattr(_harmonic_index, "_step_count", 0))
        _session_ledger.record(tool=tool, snapshot=shards, step_count=step)
    except Exception:
        pass


@mcp.tool()
@requires_init
def harmonic_index_state() -> dict[str, Any]:
    """Return the current state of the harmonically-sharded propagation index."""
    with _dom_queue.gate("harmonic_index_state"):
        return _harmonic_index.state()


@mcp.tool()
@requires_init
def harmonic_propagate(steps: int = 1, mode: str = "local") -> dict[str, Any]:
    """
    Advance the harmonic index by `steps` propagation cycles.

    Parameters
    ----------
    steps : number of propagation cycles to run (default 1)
    mode  : "local" | "resonance" | "isometric" | "goal"

    "goal" mode requires harmonic_set_goal() to have been called first.
    It blends local diffusion with a gradient pull toward the goal vector.
    """
    with _dom_queue.gate("harmonic_propagate"):
        if steps < 1:
            return {"error": "steps must be >= 1"}
        if mode not in ("local", "resonance", "isometric", "goal"):
            return {"error": f"unknown mode {mode!r}; expected 'local', 'resonance', 'isometric', or 'goal'"}

        if mode == "isometric":
            clipped = _ticket_clipper.propagate_and_clip(steps=steps, mode="isometric")
            state = _harmonic_index.state()
            peak = _harmonic_index.peak_shard()
            n = len(_harmonic_index.shards)
            state.update({
                "peak_shard":                peak.index,
                "peak_activation":           round(peak.activation, 8),
                "mode":                      mode,
                "ticket_journey":            _ticket_clipper.journey_summary(),
                "tickets_clipped_this_call": len(clipped),
                "path_space": {
                    "k_steps":            steps,
                    "n_shards":           n,
                    "paths_per_shard":    (n - 1) ** steps,
                    "total_paths":        cosine_path_count(n, steps),
                    "vs_nearest_neighbour": 2 ** steps,
                    "expansion_ratio":    round((n - 1) ** steps / max(2 ** steps, 1), 2),
                },
            })
        elif mode == "goal":
            if _harmonic_index._goal is None:
                return {
                    "error": "no_goal_set",
                    "action_required": "call harmonic_set_goal() first",
                }
            try:
                _harmonic_index.propagate(steps, mode="goal")
            except ValueError as exc:
                return {"error": str(exc)}
            state = _harmonic_index.state()
            peak = _harmonic_index.peak_shard()
            state.update({
                "peak_shard":      peak.index,
                "peak_activation": round(peak.activation, 8),
                "mode":            mode,
            })
        else:
            _harmonic_index.propagate(steps, mode=mode)
            state = _harmonic_index.state()
            peak = _harmonic_index.peak_shard()
            state.update({
                "peak_shard":      peak.index,
                "peak_activation": round(peak.activation, 8),
                "mode":            mode,
            })

        _vault_hub.push_harmonic(state)
        save_harmonic_snapshot()
        _ledger_record("harmonic_propagate")
        return state


@mcp.tool()
@requires_init
def harmonic_inject(shard_index: int, value: float = 1.0) -> dict[str, Any]:
    """
    Directly inject activation into a specific shard of the harmonic index.

    Parameters
    ----------
    shard_index : 0-based shard index (wraps on overflow)
    value       : amount of activation to add (default 1.0)
    """
    with _dom_queue.gate("harmonic_inject"):
        _harmonic_index.inject(shard_index, value)
        state = _harmonic_index.state()
        _vault_hub.push_harmonic(state)
        save_harmonic_snapshot()
        _ledger_record("harmonic_inject")
        return state


@mcp.tool()
@requires_init
def hub_inject(hub_name: str, value: float = 1.0) -> dict[str, Any]:
    """
    Inject activation into the harmonic index via a station-hub name.

    Station hubs: HOME → shard 0 | MATH → 1,2 | CODE → 3,4 |
                  COMMANDS → 5 | agent-context → 6,7

    Parameters
    ----------
    hub_name : one of HOME, MATH, CODE, COMMANDS, agent-context
    value    : total activation, split evenly across the hub's shards
    """
    with _dom_queue.gate("hub_inject"):
        if hub_name not in HUB_SHARD_MAP:
            return {"error": "unknown_hub", "hub_name": hub_name, "valid_hubs": list(HUB_NAMES)}
        shard_indices = _harmonic_index.inject_from_hub(hub_name, value)
        state = _harmonic_index.hub_state()
        state.update({
            "injected_hub":    hub_name,
            "injected_shards": list(shard_indices),
            "injected_value":  value,
        })
        _vault_hub.push_harmonic(_harmonic_index.state())
        save_harmonic_snapshot()
        _ledger_record("hub_inject")
        return state


@mcp.tool()
@requires_init
def hub_state() -> dict[str, Any]:
    """
    Return the harmonic index state broken down by station hub.

    Shows shard ownership, basin centres, and total activation per hub.
    """
    with _dom_queue.gate("hub_state"):
        return _harmonic_index.hub_state()


@mcp.tool()
@requires_init
def harmonic_set_goal(
    target_shard: int,
    value: float = 1.0,
    goal_strength: float = 0.1,
) -> dict[str, Any]:
    """
    Set the goal for goal-directed propagation.

    The goal is a one-hot activation vector: the target shard receives `value`,
    all others receive 0.  Subsequent harmonic_propagate(mode='goal') calls
    blend local diffusion with a gradient pull toward this target.

    Parameters
    ----------
    target_shard  : 0-based shard index to attract toward (wraps on overflow)
    value         : target activation at that shard (default 1.0)
    goal_strength : γ ∈ (0, 1) — gradient pull per step (default 0.1)
    """
    with _dom_queue.gate("harmonic_set_goal"):
        n = len(_harmonic_index.shards)
        if not 0.0 < goal_strength < 1.0:
            return {"error": "goal_strength must be in (0, 1)", "got": goal_strength}
        goal_vec = _harmonic_index.set_goal(
            target=target_shard % n,
            value=value,
            goal_strength=goal_strength,
        )
        state = _harmonic_index.state()
        _vault_hub.push_harmonic(state)
        save_harmonic_snapshot()
        return {
            "status": "goal_set",
            "target_shard": target_shard % n,
            "value": value,
            "goal_strength": goal_strength,
            "goal_vector": [round(float(v), 8) for v in goal_vec],
            **state,
        }


# Slash-only — Cursor catalog cap 60. Call via run_command("/harmonic-clear-goal").
@requires_init
def harmonic_clear_goal() -> dict[str, Any]:
    """
    Clear the current goal from the harmonic index.

    After this call harmonic_propagate(mode='goal') will return an error
    until harmonic_set_goal() is called again.
    """
    with _dom_queue.gate("harmonic_clear_goal"):
        _harmonic_index.clear_goal()
        state = _harmonic_index.state()
        _vault_hub.push_harmonic(state)
        save_harmonic_snapshot()
        return {"status": "goal_cleared", **state}


@mcp.tool()
@requires_init
def harmonic_reset() -> dict[str, Any]:
    """Reset the harmonic index, then re-seed the warm HOME floor.

    The ring stays on: a cold persist would boot the next spawn into a
    dead PSSPPS perspective. `/reset` drops live energy and restores the
    default peaked prior, then writes that snapshot.
    """
    with _dom_queue.gate("harmonic_reset"):
        _harmonic_index.reset()
        _harmonic_index.ensure_warm()
        state = _harmonic_index.state()
        _vault_hub.push_harmonic(state)
        save_harmonic_snapshot()
        return {"status": "reset", "warmed": True, **state}
