"""phi.core.ranker — next-track ranking (fit → TP-RAR → Cc)."""
from ._capacity import adaptive_capacity, cc_budget_score
from ._embed import maybe_fit_and_annotate, session_vecs, refetch_embedder
from ._constants import (
    CONFIDENCE_THRESHOLD,
    ELO_DEFAULT,
    ELO_K,
    ELO_K_IMPLICIT,
    ELO_MAX,
    ELO_MIN,
    ELO_NORM_HI,
    ELO_NORM_LO,
    IMPLICIT_NEGATIVE_THRESHOLD,
    IMPLICIT_POSITIVE_THRESHOLD,
    NOVELTY_HALF_LIFE,
    NOVELTY_NEVER_HEARD,
    SESSION_WINDOW,
    TP_RAR_LAMBDA,
    WEIGHTS,
    WEIGHT_KEYS,
)
from ._context import bind_floor, session_capacity_signals
from ._learn import active_weights, fit_from_play_stats, reset_learned
from ._scoring import ash_yield, blend_c_e, helm_score
from ._session import RankContext
from ._tp_rar import tp_rar_score
from ._track import TrackRanker, spend_score

__all__ = [
    "TrackRanker",
    "RankContext",
    "bind_floor",
    "ash_yield",
    "WEIGHTS",
    "WEIGHT_KEYS",
    "active_weights",
    "fit_from_play_stats",
    "reset_learned",
    "maybe_fit_and_annotate",
    "session_vecs",
    "refetch_embedder",
    "ELO_K",
    "ELO_K_IMPLICIT",
    "ELO_DEFAULT",
    "ELO_MIN",
    "ELO_MAX",
    "ELO_NORM_LO",
    "ELO_NORM_HI",
    "CONFIDENCE_THRESHOLD",
    "IMPLICIT_POSITIVE_THRESHOLD",
    "IMPLICIT_NEGATIVE_THRESHOLD",
    "NOVELTY_HALF_LIFE",
    "NOVELTY_NEVER_HEARD",
    "SESSION_WINDOW",
    "TP_RAR_LAMBDA",
    "tp_rar_score",
    "adaptive_capacity",
    "cc_budget_score",
    "session_capacity_signals",
    "blend_c_e",
    "helm_score",
    "spend_score",
]
