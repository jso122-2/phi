"""TrackRanker — session fit, then TP-RAR gate, then Cc budget gate."""
from __future__ import annotations

import random
from typing import TYPE_CHECKING

from ._capacity import cc_budget_score
from ._constants import CC_MA_FLOOR, TP_RAR_MA_FLOOR
from ._context import (
    _get_rank_cache,
    _get_rank_context,
    _set_rank_cache,
    _z_weights,
    session_capacity_signals,
)
from ._elo import _EloMixin
from ._scoring import (
    _confidence_weights,
    _elo_normalised,
    _genre_affinity,
    _mood_affinity,
    _novelty_score,
    _phi_rank,
)
from ._session import RankContext
from ._tp_rar import _confidence_level, _skip_pressure, _time_delta, keep_fill, tp_rar_score

if TYPE_CHECKING:
    from phi.core.library import Library


class TrackRanker(_EloMixin):
    """Scores library tracks and returns top-N next-track paths."""

    def candidates(
        self,
        library: "Library",
        current_path: str | None,
        n: int = 2,
        exclude: list[str] | None = None,
    ) -> list[str]:
        """Top-*n* paths: score → TP-RAR keep/fill → Cc keep/fill. Never empty if pool exists."""
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
        cc_ranked = [
            (path, cc_budget_score(ac, _skip_pressure(library.play_stats.get(path) or {}), tcv))
            for path in ordered
        ]
        result = keep_fill(cc_ranked, CC_MA_FLOOR)[:n]
        _set_rank_cache(cache_key, result)
        return result

    def score(
        self,
        path: str,
        library: "Library",
        ctx: RankContext,
        weights: dict[str, float] | None = None,
    ) -> float:
        """Session-fit score in [0, 1].

        Primary path: return the pre-annotated ``predicted_completion`` written
        by CompletionPredictor at session restore — a Ridge regression trained
        end-to-end on historical (context, track) → completion_rate data.

        Fallback (no annotation or predictor not fitted): heuristic weighted
        sum of genre / mood / novelty / elo / phi_rank dimensions, modulated
        by per-track metadata confidence.
        """
        ann = library.annotations.get(path) or {}
        pc = ann.get("predicted_completion")
        if pc is not None:
            try:
                return max(0.0, min(1.0, float(pc)))
            except (TypeError, ValueError):
                pass

        # Heuristic weighted-sum fallback
        w_base = weights if weights is not None else _z_weights()
        meta  = library.meta_cache.get(path) or {}
        stats = library.play_stats.get(path) or {}
        w = _confidence_weights(ann, w_base)
        return (
            w["genre"]     * _genre_affinity(meta, ann, ctx)
            + w["mood"]    * _mood_affinity(ann, meta, ctx)
            + w["novelty"] * _novelty_score(stats)
            + w["elo"]     * _elo_normalised(library.get_elo(path))
            + w["phi_rank"]* _phi_rank(ann)
        )

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
