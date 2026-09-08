"""Ranking constants. Weights and thresholds only — no behaviour."""
from __future__ import annotations

import math

from workers.cairrn.mycelial import _E_MAX

_Z_HOT_THRESHOLD: float = 2.5
_Z_MAX_MODULATION: float = 5.0

WEIGHTS: dict[str, float] = {
    "genre": 0.28,
    "mood": 0.28,
    "novelty": 0.23,
    "elo": 0.13,
    "phi_rank": 0.08,
}

WEIGHT_KEYS: tuple[str, ...] = ("genre", "mood", "novelty", "elo", "phi_rank")

# Exponentiated-gradient step on WEIGHTS from skip/complete feedback.
LEARN_ETA: float = 0.08
LEARN_W_MIN: float = 0.05

ELO_K = 32
ELO_K_IMPLICIT = 8
ELO_DEFAULT = 1500.0
ELO_MIN = 800.0
ELO_MAX = 2400.0
ELO_NORM_LO = 1200.0
ELO_NORM_HI = 1800.0

_ASH_BASE: float = float(ELO_K_IMPLICIT)
_ASH_K: float = 0.20
_ASH_T_MIN: int = 3

CONFIDENCE_THRESHOLD = 0.15
IMPLICIT_POSITIVE_THRESHOLD = 0.70
IMPLICIT_NEGATIVE_THRESHOLD = 0.30
NOVELTY_HALF_LIFE = 14.0
NOVELTY_NEVER_HEARD = 0.85
SESSION_WINDOW = 8

TP_RAR_LAMBDA = math.log(2) / NOVELTY_HALF_LIFE
TP_RAR_MA_FLOOR = 1e-12

AC_WEIGHT_N = 1.0 / 3.0
AC_WEIGHT_S = 1.0 / 3.0
AC_WEIGHT_T = 1.0 / 3.0
CC_CEILING = _E_MAX
CC_MA_FLOOR = 1e-12
ARC_MA_FLOOR = 1e-12

# predicted_completion is a prior on C_E, not a bypass. Share grows as buoyancy falls
# so sparse catalog still listens to the ridge model; rich catalog keeps helm heading.
PRED_PRIOR_LO: float = 0.40
PRED_PRIOR_HI: float = 0.60

# Song-derivative D4 (library curve, [0, 1]) rides the phi_rank helm slot.
# Dragon D4_A stays geometric and feeds ArcScorer only.
SONG_D4_BLEND: float = 0.15

# Minimum fraction of base weight that helm dims (genre, mood, phi_rank) receive.
# Prevents ELO/novelty from dominating via renormalisation when buoyancy is low.
HELM_FLOOR: float = 0.50
