"""Pre-hook guards: harmonic inject/propagate and temporal-graph validation."""
from __future__ import annotations

import threading
from typing import Final

from mcp_server.hooks import HookViolation
from mcp_server.hooks import REGISTRY as _hook_registry

# Shared validation constants — imported by other guard modules
VALID_HUBS: Final[frozenset[str]] = frozenset({
    "HOME", "MATH", "CODE", "COMMANDS", "agent-context",
})
VALID_PROPAGATE_MODES: Final[frozenset[str]] = frozenset({"local", "resonance"})

_HARMONIC_GUARD_TOOLS: frozenset[str] = frozenset({
    "harmonic_inject", "hub_inject", "harmonic_propagate", "harmonic_set_goal",
})
_TEMPORAL_HUB_TOOLS: frozenset[str] = frozenset({"temporal_record"})
_GRAPH_QUERY_TOOLS: frozenset[str] = frozenset({"graph_traverse", "graph_annotate"})

_harmonic_guard_registered = threading.Event()
_temporal_graph_guard_registered = threading.Event()


def _register_harmonic_guard() -> None:
    """
    Register the harmonic pre-hook. Idempotent.

    Mandates: shard_index ∈ [0,7] for harmonic_inject; hub_name ∈ VALID_HUBS
    for hub_inject / harmonic_set_goal; mode ∈ VALID_PROPAGATE_MODES for propagate.
    """
    if _harmonic_guard_registered.is_set():
        return

    def _harmonic_guard(tool_name: str, kwargs: dict) -> None:
        if tool_name not in _HARMONIC_GUARD_TOOLS:
            return
        if tool_name == "harmonic_inject":
            si = kwargs.get("shard_index")
            if si is not None:
                try:
                    if not (0 <= int(si) <= 7):
                        raise HookViolation(
                            f"harmonic_inject: shard_index {si!r} must be in [0, 7]"
                        )
                except (TypeError, ValueError):
                    raise HookViolation(
                        f"harmonic_inject: shard_index {si!r} must be an integer 0–7"
                    )
        if tool_name in ("hub_inject", "harmonic_set_goal"):
            hub = kwargs.get("hub_name", "")
            if hub not in VALID_HUBS:
                raise HookViolation(
                    f"{tool_name}: hub_name {hub!r} must be one of {sorted(VALID_HUBS)}"
                )
        if tool_name == "harmonic_propagate":
            mode = kwargs.get("mode", "local")
            if mode not in VALID_PROPAGATE_MODES:
                raise HookViolation(
                    f"harmonic_propagate: mode {mode!r} must be one of "
                    f"{sorted(VALID_PROPAGATE_MODES)}"
                )

    _hook_registry.register(
        name="harmonic_guard",
        description=(
            "Mandate shard_index ∈ [0,7] for harmonic_inject; "
            "valid hub_name for hub_inject / harmonic_set_goal; "
            "valid mode for harmonic_propagate."
        ),
        fn=_harmonic_guard,
    )
    _harmonic_guard_registered.set()


def _register_temporal_graph_guard() -> None:
    """
    Register the temporal + graph-query pre-hook. Idempotent.

    Mandates: hub_name ∈ VALID_HUBS for temporal_record; non-empty seed for
    graph_traverse; non-empty target_stem + comment for graph_annotate.
    """
    if _temporal_graph_guard_registered.is_set():
        return

    def _temporal_graph_guard(tool_name: str, kwargs: dict) -> None:
        if tool_name in _TEMPORAL_HUB_TOOLS:
            hub = kwargs.get("hub_name", "")
            if hub not in VALID_HUBS:
                raise HookViolation(
                    f"temporal_record: hub_name {hub!r} must be one of {sorted(VALID_HUBS)}"
                )
        elif tool_name == "graph_traverse":
            seed = kwargs.get("seed", "")
            if not isinstance(seed, str) or not seed.strip():
                raise HookViolation("graph_traverse: 'seed' must be a non-empty string")
        elif tool_name == "graph_annotate":
            for field in ("target_stem", "comment"):
                val = kwargs.get(field, "")
                if not isinstance(val, str) or not val.strip():
                    raise HookViolation(
                        f"graph_annotate: '{field}' must be a non-empty string"
                    )

    _hook_registry.register(
        name="temporal_graph_guard",
        description=(
            "Mandate valid hub_name for temporal_record; "
            "non-empty seed for graph_traverse; "
            "non-empty target_stem + comment for graph_annotate."
        ),
        fn=_temporal_graph_guard,
    )
    _temporal_graph_guard_registered.set()
