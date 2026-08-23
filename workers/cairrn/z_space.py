"""
CAIRRN active -Z spatial scoring.

ZScore is the result of mapping a raw −Z value onto the shard ring and
scoring its proximity to the Lambert-W fixed point x* ≈ −0.5671.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from sims.attractors import NEG_EXP_FIXED_POINT
from workers.cairrn._constants import N_SHARDS, _MAX_NEG_EXP_RAW, _COHERENCE_SIGMA, _COHERENCE_THRESHOLD
from workers.cairrn.formulas import f_cairrn_z_space


@dataclass(frozen=True)
class ZScore:
    """
    Active -Z scoring result.

    neg_z       : raw −Z value from F_CAIRRN_Z_SPACE
    z_shard     : shard assignment derived from |neg_Z|, same scaling as neg_exp
    z_coherence : exp(−|neg_Z − x*| / σ) — proximity to Lambert-W fixed point
    z_coherent  : z_coherence ≥ threshold
    z_active    : True — Z scoring is live and participates in coherence gate
    """
    neg_z: float
    z_shard: int
    z_coherence: float
    z_coherent: bool
    z_active: bool = True


def compute_z_score(
    semantic_matrix_value: float,
    partial_deriv_1: float,
    activation: float,
    energy_cost: float,
    uncertainty: float,
    rizomic_distance: float,
    sigma_accumulator: float,
    coherence_threshold: float = _COHERENCE_THRESHOLD,
) -> ZScore:
    """
    Compute active -Z score and map it onto the shard ring.

    neg_Z is scored against the Lambert-W fixed point x* ≈ −0.5671 using
    the same decay kernel as Layer 3 coherence — the closer neg_Z lands to
    x*, the more coherent the spatial position.

    z_shard = clamp( floor(|neg_Z| × N_SHARDS / max_raw), 0, N_SHARDS−1 )
    """
    neg_z = f_cairrn_z_space(
        semantic_matrix_value, partial_deriv_1, activation,
        energy_cost, uncertainty, rizomic_distance, sigma_accumulator,
    )
    raw = abs(neg_z)
    z_shard = min(int(raw * N_SHARDS / _MAX_NEG_EXP_RAW), N_SHARDS - 1)
    err = abs(neg_z - NEG_EXP_FIXED_POINT)
    z_coh = round(math.exp(-err / _COHERENCE_SIGMA), 6)
    return ZScore(
        neg_z=round(neg_z, 8),
        z_shard=z_shard,
        z_coherence=z_coh,
        z_coherent=z_coh >= coherence_threshold,
    )
