"""TrackRanker — session fit, then TP-RAR, then Cc · S_arc spend gate."""
from __future__ import annotations

import random
from typing import TYPE_CHECKING

from phi.engine.arc_scorer import ArcScorer

from ._capacity import cc_budget_score
from ._constants import ARC_MA_FLOOR, CC_MA_FLOOR, TP_RAR_MA_FLOOR
from ._context import (
    _floor,
    _get_rank_cache,
    _get_rank_context,
    _set_rank_cache,
    _z_weights,
    session_capacity_signals,
)
from ._elo import _EloMixin
from ._scoring import _buoyancy, blend_c_e, helm_score
from ._session import RankContext
from ._tp_rar import _confidence_level, _skip_pressure, _time_delta, keep_fill, tp_rar_score

if TYPE_CHECKING:
    from phi.core.library import Library


def _parse_predicted(ann: dict) -> float | None:
    pc = ann.get("predicted_completion")
    if pc is None:
        return None
    try:
        return max(0.0, min(1.0, float(pc)))
    except (TypeError, ValueError):
        return None


def _session_arc(library: "Library", ctx: RankContext) -> ArcScorer:
    """ArcScorer fed oldest→newest from the session window's dragon D4_A."""
    scorer = ArcScorer(capacity=16)
    for path in reversed(ctx.recent_paths):
        d4 = (library.annotations.get(path) or {}).get("d4_a")
        scorer.push(d4)
    return scorer


def _code_incoherence() -> float:
    """U_p from SCUP — CODE hub 1 − coherence. 0 when the floor is unbound."""
    if _floor is None:
        return 0.0
    try:
        return max(0.0, 1.0 - _floor._bridge._hubs["CODE"].coherence)
    except Exception:
        return 0.0


def _cognitive_pressure(ann: dict, stats: dict) -> float:
    """P = B σ² — catalog buoyancy times skip-pressure squared."""
    p = _skip_pressure(stats)
    return _buoyancy(ann) * p * p


def spend_score(
    path: str,
    library: "Library",
    ctx: RankContext,
    ac: float,
    tcv: float,
    arc: ArcScorer | None = None,
) -> float:
    """Cc · S_arc / ((1+U_p)(1+P)). Dragon arc, SCUP incoherence, cognitive pressure."""
    stats = library.play_stats.get(path) or {}
    ann = library.annotations.get(path) or {}
    cc = cc_budget_score(ac, _skip_pressure(stats), tcv)
    if arc is None:
        s_arc = 1.0
    else:
        d4 = ann.get("d4_a")
        d4_a = float(d4) if d4 is not None else ArcScorer._D4A_NEUTRAL
        s_arc = arc.score_candidate(d4_a)
    u_p = _code_incoherence()
    pressure = _cognitive_pressure(ann, stats)
    return cc * s_arc / ((1.0 + u_p) * (1.0 + pressure))


class TrackRanker(_EloMixin):
    """Scores library tracks and returns top-N next-track paths."""

    def candidates(
        self,
        library: "Library",
        current_path: str | None,
        n: int = 2,
        exclude: list[str] | None = None,
    ) -> list[str]:
        """Top-*n*: C_E → TP-RAR keep/fill → spend (Cc·S_arc) keep/fill."""
        cache_key = f"{current_path}:{library.size}:{n}:{','.join(sorted(exclude or []))}"
        cached = _get_rank_cache(cache_key)
        if cached is not None:
            return cached

        blocked = set(exclude or [])
        if current_path:
            blocked.add(current_path)
        ctx = _get_rank_context(current_path, library)
        blocked.update(ctx.recent_paths[:3])

        pool = [p for p in library.playlist if p not in blocked]
        if not pool:
            pool = [p for p in library.playlist if p != current_path]
        if len(pool) <= n:
            random.shuffle(pool)
            result = pool[:n]
            _set_rank_cache(cache_key, result)
            return result

        w = _z_weights()
        random.shuffle(pool)
        scored = [(p, self.score(p, library, ctx, weights=w)) for p in pool]
        scored.sort(key=lambda t: -t[1])

        ranked_tp: list[tuple[str, float]] = []
        for path, c_e in scored:
            stats = library.play_stats.get(path) or {}
            ann = library.annotations.get(path) or {}
            ranked_tp.append((
                path,
                tp_rar_score(c_e, _confidence_level(ann, stats), _time_delta(stats), _skip_pressure(stats)),
            ))
        ordered = keep_fill(ranked_tp, TP_RAR_MA_FLOOR)

        ac, tcv = session_capacity_signals(ctx)
        arc = _session_arc(library, ctx)
        spent = [
            (path, spend_score(path, library, ctx, ac, tcv, arc=arc))
            for path in ordered
        ]
        result = keep_fill(spent, ARC_MA_FLOOR if spent else CC_MA_FLOOR)[:n]
        _set_rank_cache(cache_key, result)
        return result

    def score(
        self,
        path: str,
        library: "Library",
        ctx: RankContext,
        weights: dict[str, float] | None = None,
    ) -> float:
        """Session-fit C_E in [0, 1].

        Helm mix always runs. ``predicted_completion`` is a buoyancy-scaled
        prior, not a short-circuit.
        """
        w_base = weights if weights is not None else _z_weights()
        helm = helm_score(path, library, ctx, w_base)
        ann = library.annotations.get(path) or {}
        return blend_c_e(helm, _parse_predicted(ann), _buoyancy(ann))

    def tp_rar(
        self,
        path: str,
        library: "Library",
        ctx: RankContext,
        c_e: float | None = None,
        conf_ma: float = 1.0,
        weights: dict[str, float] | None = None,
    ) -> float:
        """F_TP_RAR for *path*. *c_e* defaults to score()."""
        if c_e is None:
            c_e = self.score(path, library, ctx, weights=weights)
        ann = library.annotations.get(path) or {}
        stats = library.play_stats.get(path) or {}
        return tp_rar_score(
            c_e,
            _confidence_level(ann, stats),
            _time_delta(stats),
            _skip_pressure(stats),
            conf_ma=conf_ma,
        )

    def adaptive_capacity(self, ctx: RankContext) -> float:
        """F_ADAPTIVE_CAPACITY for the current session."""
        ac, _tcv = session_capacity_signals(ctx)
        return ac

    def cc_budget(self, path: str, library: "Library", ctx: RankContext) -> float:
        """F_CC for *path* using session AC and skip pressure."""
        ac, tcv = session_capacity_signals(ctx)
        stats = library.play_stats.get(path) or {}
        return cc_budget_score(ac, _skip_pressure(stats), tcv)

    def top_by_score(
        self,
        library: "Library",
        current_path: str | None,
        n: int = 20,
    ) -> list[tuple[str, float]]:
        """Top-*n* (path, score) pairs for debugging."""
        ctx = RankContext.from_library(library, current_path)
        w = _z_weights()
        pool = [p for p in library.playlist if p != current_path]
        scored = [(p, self.score(p, library, ctx, weights=w)) for p in pool]
        scored.sort(key=lambda t: -t[1])
        return scored[:n]
