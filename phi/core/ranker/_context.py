"""ForestFloor bind, rank caches, z-weights, and session capacity signals."""
from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any, Optional

from ._capacity import adaptive_capacity
from ._constants import (
    SESSION_WINDOW,
    _Z_HOT_THRESHOLD,
    _Z_MAX_MODULATION,
)
from ._learn import active_weights
from ._session import RankContext

if TYPE_CHECKING:
    from phi.engine.forest_floor import ForestFloor

_floor: Optional["ForestFloor"] = None
_lock = threading.Lock()
_rank_cache: dict[str, Any] = {}
_rank_cache_step: int = -1
_ctx_cache: dict[str, tuple] = {}


def bind_floor(floor: "ForestFloor") -> None:
    """Subscribe to CODE hub shifts so rank caches invalidate. Called once at app init."""
    global _floor
    _floor = floor

    def _on_code_shift(result, payload: dict) -> None:
        if result.should_act:
            _invalidate_rank_cache()

    floor.when_floor_shifts(shard=1, handler=_on_code_shift)


def _invalidate_rank_cache() -> None:
    """Drop rank and context caches after a CODE hub shift."""
    global _rank_cache_step
    with _lock:
        _rank_cache.clear()
        _rank_cache_step = -1
        _ctx_cache.clear()


def _get_rank_cache(key: str) -> Any | None:
    if _floor is None:
        return None
    try:
        code_hub = _floor._bridge._hubs["CODE"]
        if code_hub.coherence < _floor._bridge.coherence_floor:
            return None
        with _lock:
            if _rank_cache_step != code_hub.steps:
                return None
            return _rank_cache.get(key)
    except Exception:
        return None


def _set_rank_cache(key: str, value: Any) -> None:
    if _floor is None:
        return
    try:
        code_hub = _floor._bridge._hubs["CODE"]
        global _rank_cache_step
        with _lock:
            _rank_cache_step = code_hub.steps
            _rank_cache[key] = value
    except Exception:
        pass


def _get_rank_context(current_path: str | None, library: Any) -> RankContext:
    if _floor is None:
        return RankContext.from_library(library, current_path)
    try:
        code_hub = _floor._bridge._hubs["CODE"]
        key = current_path or "__none__"
        with _lock:
            entry = _ctx_cache.get(key)
            if (
                entry is not None
                and entry[1] == code_hub.steps
                and code_hub.coherence >= _floor._bridge.coherence_floor
            ):
                return entry[0]
            ctx = RankContext.from_library(library, current_path)
            _ctx_cache[key] = (ctx, code_hub.steps)
            return ctx
    except Exception:
        return RankContext.from_library(library, current_path)


def _z_weights() -> dict[str, float]:
    """Boost novelty when CODE |z| is hot. Returns learned weights if the floor is unbound."""
    base = active_weights()
    if _floor is None:
        return base
    try:
        code_z = abs(_floor._bridge._hubs["CODE"].z_awareness)
        if code_z < _Z_HOT_THRESHOLD:
            return base
        t = min(1.0, (code_z - _Z_HOT_THRESHOLD) / (_Z_MAX_MODULATION - _Z_HOT_THRESHOLD))
        boost = t * 0.15
        half = boost * 0.5
        return {
            "genre": max(0.10, base["genre"] - half),
            "mood": max(0.10, base["mood"] - half),
            "novelty": min(0.38, base["novelty"] + boost),
            "elo": base["elo"],
            "phi_rank": base["phi_rank"],
        }
    except Exception:
        return base


def session_capacity_signals(ctx: RankContext) -> tuple[float, float]:
    """Return (AC, Tcv). Unbound floor: M_SHI=0, S_T=1, Tcv=1."""
    window = max(1, SESSION_WINDOW)
    nutrient = max(0.0, 1.0 - len(ctx.recent_paths) / window)
    shi_margin = 0.0
    tracer_slack = 1.0
    tcv = 1.0
    if _floor is not None:
        try:
            bridge = _floor._bridge
            hubs = bridge._hubs
            floor_c = float(bridge.coherence_floor)
            span = max(1e-9, 1.0 - floor_c)
            code = hubs["CODE"]
            shi_margin = min(1.0, max(0.0, (float(code.coherence) - floor_c) / span))
            commands = hubs.get("COMMANDS")
            if commands is not None:
                z_thr = max(1e-9, float(bridge.z_spawn_threshold))
                tracer_slack = max(
                    0.0,
                    1.0 - min(1.0, abs(float(commands.z_awareness)) / z_thr),
                )
            coherences = [float(h.coherence) for h in hubs.values()]
            if coherences:
                tcv = sum(coherences) / len(coherences)
        except Exception:
            pass
    return adaptive_capacity(nutrient, shi_margin, tracer_slack), tcv
