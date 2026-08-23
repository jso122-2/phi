"""Pre-hook guards: simulation parameter bounds and phi action validation."""
from __future__ import annotations

import threading
from typing import Final

from mcp_server.hooks import HookViolation
from mcp_server.hooks import REGISTRY as _hook_registry

_SIM_X0_RANGE: Final[tuple[float, float]] = (-1000.0, 1000.0)
_SIM_GUARD_TOOLS: Final[frozenset[str]] = frozenset({
    "double_well_sim", "langevin_sim", "neg_exp_sim",
    "sweep_attractors", "mfpt_estimate", "ana_chi_sim",
})

VALID_PHI_KINDS: Final[frozenset[str]] = frozenset({
    "CLIP", "SHUFFLE_NEXT", "SHUFFLE_SEED",
    "HUB_INJECT", "SHARD_INJECT", "PROPAGATE",
    "CAIRRN_RUN", "TEMPORAL_REC", "MYCELIAL_TICK",
    "LOAD_TRACK", "HOVER_PREFETCH",
})
_PHI_KINDS_NEED_QUERY: Final[frozenset[str]] = frozenset({"CLIP", "LOAD_TRACK"})
_PHI_KINDS_NEED_HUB: Final[frozenset[str]] = frozenset({"HUB_INJECT", "CAIRRN_RUN", "TEMPORAL_REC"})
_PHI_KINDS_NEED_SHARD: Final[frozenset[str]] = frozenset({"SHARD_INJECT"})

_sim_guard_registered = threading.Event()
_phi_action_guard_registered = threading.Event()


def _register_sim_guard() -> None:
    """
    Register the simulation pre-hook. Idempotent.

    Mandates: x0/x0_min/x0_max ∈ [-1000, 1000]; noise_scale ≥ 0 for
    langevin/mfpt; x0_min < x0_max for sweep.
    """
    if _sim_guard_registered.is_set():
        return

    lo, hi = _SIM_X0_RANGE

    def _sim_guard(tool_name: str, kwargs: dict) -> None:
        if tool_name not in _SIM_GUARD_TOOLS:
            return
        for key in ("x0", "x0_min", "x0_max"):
            v = kwargs.get(key)
            if v is not None:
                try:
                    fv = float(v)
                    if not (lo <= fv <= hi):
                        raise HookViolation(
                            f"{tool_name}: '{key}={v}' must be in [{lo}, {hi}]"
                        )
                except (TypeError, ValueError):
                    raise HookViolation(
                        f"{tool_name}: '{key}' must be a float (got {v!r})"
                    )
        ns = kwargs.get("noise_scale")
        if ns is not None and tool_name in ("langevin_sim", "mfpt_estimate"):
            try:
                if float(ns) < 0:
                    raise HookViolation(
                        f"{tool_name}: noise_scale must be ≥ 0 (got {ns})"
                    )
            except (TypeError, ValueError):
                raise HookViolation(
                    f"{tool_name}: noise_scale must be a float ≥ 0 (got {ns!r})"
                )
        if tool_name == "sweep_attractors":
            x_min = kwargs.get("x0_min")
            x_max = kwargs.get("x0_max")
            if x_min is not None and x_max is not None:
                if float(x_min) >= float(x_max):
                    raise HookViolation(
                        f"sweep_attractors: x0_min ({x_min}) must be < x0_max ({x_max})"
                    )

    _hook_registry.register(
        name="sim_guard",
        description=(
            "Mandate x0/x0_min/x0_max ∈ [-1000,1000] for all sim tools; "
            "noise_scale ≥ 0 for langevin_sim/mfpt_estimate; "
            "x0_min < x0_max for sweep_attractors."
        ),
        fn=_sim_guard,
    )
    _sim_guard_registered.set()


def _register_phi_action_guard() -> None:
    """
    Register the phi action pre-hook. Idempotent.

    Mandates for phi_enqueue: valid kind enum; non-empty query for CLIP/LOAD_TRACK;
    valid hub_name for HUB_INJECT/CAIRRN_RUN/TEMPORAL_REC; shard_index ∈ [0,7] for SHARD_INJECT.
    """
    if _phi_action_guard_registered.is_set():
        return

    from mcp_server._guards_harmonic import VALID_HUBS

    def _phi_action_guard(tool_name: str, kwargs: dict) -> None:
        if tool_name != "phi_enqueue":
            return
        kind_raw = kwargs.get("kind", "")
        kind = kind_raw.strip().upper() if isinstance(kind_raw, str) else ""
        if kind not in VALID_PHI_KINDS:
            raise HookViolation(
                f"phi_enqueue: kind {kind_raw!r} must be one of {sorted(VALID_PHI_KINDS)}"
            )
        if kind in _PHI_KINDS_NEED_QUERY:
            q = kwargs.get("query", "")
            if not isinstance(q, str) or not q.strip():
                raise HookViolation(
                    f"phi_enqueue {kind}: 'query' must be a non-empty string"
                )
        if kind in _PHI_KINDS_NEED_HUB:
            hub = kwargs.get("hub_name", "")
            if hub not in VALID_HUBS:
                raise HookViolation(
                    f"phi_enqueue {kind}: 'hub_name' must be one of {sorted(VALID_HUBS)}"
                )
        if kind in _PHI_KINDS_NEED_SHARD:
            si = kwargs.get("shard_index")
            if si is None:
                raise HookViolation("phi_enqueue SHARD_INJECT: 'shard_index' is required")
            try:
                if not (0 <= int(si) <= 7):
                    raise HookViolation(
                        f"phi_enqueue SHARD_INJECT: shard_index {si!r} must be 0–7"
                    )
            except (TypeError, ValueError):
                raise HookViolation(
                    f"phi_enqueue SHARD_INJECT: shard_index {si!r} must be an integer 0–7"
                )

    _hook_registry.register(
        name="phi_action_guard",
        description=(
            "Mandate valid kind enum for phi_enqueue; "
            "non-empty query for CLIP/LOAD_TRACK; "
            "valid hub_name for HUB_INJECT/CAIRRN_RUN/TEMPORAL_REC; "
            "shard_index ∈ [0,7] for SHARD_INJECT."
        ),
        fn=_phi_action_guard,
    )
    _phi_action_guard_registered.set()
