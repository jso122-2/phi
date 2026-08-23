"""ELO pairwise updates and F_SCUP_CANONICAL ranking."""
from __future__ import annotations

from typing import TYPE_CHECKING

from workers.cairrn.formulas import f_scup_canonical

from ._constants import (
    ELO_DEFAULT,
    ELO_K,
    ELO_K_IMPLICIT,
    ELO_MAX,
    ELO_MIN,
    IMPLICIT_NEGATIVE_THRESHOLD,
    IMPLICIT_POSITIVE_THRESHOLD,
)
from ._context import _floor, _get_rank_context, _z_weights
from ._scoring import ash_yield

if TYPE_CHECKING:
    from phi.core.library import Library

    from ._session import RankContext
    from ._track import TrackRanker


class _EloMixin:
    """ELO + SCUP methods mixed into TrackRanker."""

    def elo_update(
        self,
        winner: str,
        loser: str,
        library: "Library",
        K: int = ELO_K,
    ) -> None:
        """Standard ELO after an explicit pick of *winner* over *loser*."""
        ra = library.get_elo(winner)
        rb = library.get_elo(loser)
        expected_a = 1.0 / (1.0 + 10.0 ** ((rb - ra) / 400.0))
        library.set_elo(winner, max(ELO_MIN, min(ELO_MAX, ra + K * (1.0 - expected_a))))
        library.set_elo(loser, max(ELO_MIN, min(ELO_MAX, rb + K * (0.0 - (1.0 - expected_a)))))

    def implicit_elo_update(self, path: str, library: "Library") -> None:
        """ELO from completion_rate. K scales with coherent streak via ash_yield()."""
        s = library.play_stats.setdefault(path, {})
        completion = s.get("completion_rate")
        if completion is None:
            return
        streak = int(s.get("coherent_plays", 0))
        if completion >= IMPLICIT_POSITIVE_THRESHOLD:
            streak += 1
            k = ash_yield(streak)
            s["coherent_plays"] = streak
        elif completion < IMPLICIT_NEGATIVE_THRESHOLD:
            k = ELO_K_IMPLICIT
            s["coherent_plays"] = 0
        else:
            return
        ra = library.get_elo(path)
        rb = self._mean_elo(library)
        expected_a = 1.0 / (1.0 + 10.0 ** ((rb - ra) / 400.0))
        if completion >= IMPLICIT_POSITIVE_THRESHOLD:
            new_ra = ra + k * (1.0 - expected_a)
        else:
            new_ra = ra + k * (0.0 - expected_a)
        library.set_elo(path, max(ELO_MIN, min(ELO_MAX, new_ra)))
        from ._learn import observe_departure
        observe_departure(path, library)

    def compute_scup(
        self: "TrackRanker",
        path: str,
        library: "Library",
        ctx: "RankContext",
        weights: dict[str, float] | None = None,
    ) -> float:
        """SCUP = (S_i × TP-RAR) / (1 + P_s + U_p)."""
        ann = library.annotations.get(path) or {}
        stats = library.play_stats.get(path) or {}
        s_i = float(ann.get("phi_rank") or 0.5)
        tp_rar = self.tp_rar(path, library, ctx, weights=weights)
        plays = max(1, int(stats.get("plays", 1) or 1))
        p_s = int(stats.get("skip_count", 0) or 0) / plays
        u_p = 0.0
        if _floor is not None:
            try:
                u_p = max(0.0, 1.0 - _floor._bridge._hubs["CODE"].coherence)
            except Exception:
                pass
        return round(f_scup_canonical(s_i, tp_rar, p_s, u_p), 4)

    def rank_by_scup(
        self: "TrackRanker",
        paths: list[str],
        library: "Library",
        current_path: str | None = None,
    ) -> list[str]:
        """Sort *paths* by SCUP descending. Failures score 0.0 and sink."""
        ctx = _get_rank_context(current_path, library)
        w = _z_weights()
        scored: list[tuple[str, float]] = []
        for path in paths:
            try:
                scored.append((path, self.compute_scup(path, library, ctx, weights=w)))
            except Exception:
                scored.append((path, 0.0))
        scored.sort(key=lambda t: -t[1])
        return [path for path, _ in scored]

    @staticmethod
    def _mean_elo(library: "Library") -> float:
        """Mean stored ELO, or ELO_DEFAULT if none."""
        scores = [s["elo_score"] for s in library.play_stats.values() if "elo_score" in s]
        return sum(scores) / len(scores) if scores else ELO_DEFAULT
