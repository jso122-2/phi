"""Pre-hook guards: search query validation and CAIRRN metric validation."""
from __future__ import annotations

import threading
from typing import Final

from mcp_server.hooks import HookViolation
from mcp_server.hooks import REGISTRY as _hook_registry

_SEARCH_TOOLS: Final[frozenset[str]] = frozenset({"find_query", "psspps_query"})
_FIND_MODES_VALID: Final[frozenset[str]] = frozenset({"pericles", "semantic", "harmonic", "quick"})
_CAIRRN_GUARD_TOOLS: Final[frozenset[str]] = frozenset({
    "cairrn_hub_run", "cairrn_batch_run", "cairrn_neuro_k",
})

_search_guard_registered = threading.Event()
_cairrn_guard_registered = threading.Event()


def _register_search_guard() -> None:
    """
    Register the search pre-hook. Idempotent.

    Mandates: non-empty query; valid mode for find_query; top_k ≥ 1 for psspps_query.
    """
    if _search_guard_registered.is_set():
        return

    def _search_guard(tool_name: str, kwargs: dict) -> None:
        if tool_name not in _SEARCH_TOOLS:
            return
        query = kwargs.get("query", "")
        if not isinstance(query, str) or not query.strip():
            raise HookViolation(
                f"{tool_name}: 'query' must be a non-empty string (got {query!r})"
            )
        if tool_name == "find_query":
            mode = kwargs.get("mode", "pericles")
            if mode not in _FIND_MODES_VALID:
                raise HookViolation(
                    f"find_query: 'mode' must be one of {sorted(_FIND_MODES_VALID)} "
                    f"(got {mode!r})"
                )
        if tool_name == "psspps_query":
            top_k = kwargs.get("top_k")
            if top_k is not None:
                try:
                    if int(top_k) < 1:
                        raise HookViolation(
                            f"psspps_query: 'top_k' must be ≥ 1 (got {top_k})"
                        )
                except (TypeError, ValueError):
                    raise HookViolation(
                        f"psspps_query: 'top_k' must be an integer ≥ 1 (got {top_k!r})"
                    )

    _hook_registry.register(
        name="search_guard",
        description=(
            "Mandate non-empty query + valid mode for find_query / psspps_query. "
            "Raises HookViolation on empty query, unknown mode, or top_k < 1."
        ),
        fn=_search_guard,
    )
    _search_guard_registered.set()


def _register_cairrn_guard() -> None:
    """
    Register the CAIRRN pre-hook. Idempotent.

    Mandates: hub_name ∈ VALID_HUBS for cairrn_hub_run; finite metric;
    finite tracer_consensus_value for cairrn_neuro_k.
    """
    if _cairrn_guard_registered.is_set():
        return

    from mcp_server._guards_harmonic import VALID_HUBS

    def _cairrn_guard(tool_name: str, kwargs: dict) -> None:
        if tool_name not in _CAIRRN_GUARD_TOOLS:
            return
        import math as _math
        if tool_name == "cairrn_hub_run":
            hub = kwargs.get("hub_name", "")
            if hub not in VALID_HUBS:
                raise HookViolation(
                    f"cairrn_hub_run: hub_name {hub!r} must be one of {sorted(VALID_HUBS)}"
                )
            metric = kwargs.get("metric")
            if metric is not None:
                try:
                    if not _math.isfinite(float(metric)):
                        raise HookViolation(
                            f"cairrn_hub_run: metric must be finite (got {metric})"
                        )
                except (TypeError, ValueError):
                    raise HookViolation(
                        f"cairrn_hub_run: metric must be a finite float (got {metric!r})"
                    )
        if tool_name == "cairrn_neuro_k":
            tcv = kwargs.get("tracer_consensus_value")
            if tcv is not None:
                try:
                    if not _math.isfinite(float(tcv)):
                        raise HookViolation(
                            f"cairrn_neuro_k: tracer_consensus_value must be finite (got {tcv})"
                        )
                except (TypeError, ValueError):
                    raise HookViolation(
                        f"cairrn_neuro_k: tracer_consensus_value must be a float (got {tcv!r})"
                    )

    _hook_registry.register(
        name="cairrn_guard",
        description=(
            "Mandate valid hub_name for cairrn_hub_run; "
            "finite metric for cairrn_hub_run; "
            "finite tracer_consensus_value for cairrn_neuro_k."
        ),
        fn=_cairrn_guard,
    )
    _cairrn_guard_registered.set()
