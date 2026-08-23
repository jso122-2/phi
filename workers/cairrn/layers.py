"""
CAIRRN three-layer pipeline dataclasses and runner functions.

Layer 1 — Ana-Chi Modulation   : ModulationResult, ana_chi_modulate
Layer 2 — neg_exp Sharding     : ShardSignal, neg_exp_shard
Layer 3 — Coherence Enforcement: CoherenceResult, measure_coherence
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from sims.ana_chi import AnaChiBasin, basin_at_hub, coherence as _ana_chi_coherence
from sims.attractors import NEG_EXP_FIXED_POINT, run_neg_exp_map, neg_exp
from workers.cairrn._constants import (
    N_SHARDS,
    _MAX_NEG_EXP_RAW,
    _COHERENCE_SIGMA,
    _COHERENCE_THRESHOLD,
    _HUB_PRIMARY_SHARD,
    _TAU,
)


# ---------------------------------------------------------------------------
# Layer 1 — Ana-Chi Modulation
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ModulationResult:
    """Output of Ana-Chi modulation for one worker metric."""
    raw_metric: float
    basin_name: str
    chi: float
    gravity: float
    rattling: bool
    memory_decay: float
    modulated_metric: float
    energy_weighted: Optional[float] = None
    energy_consumption: Optional[float] = None
    height_node: Optional[float] = None
    global_rzone: Optional[float] = None
    local_friction_d: Optional[float] = None

    @property
    def damping_applied(self) -> bool:
        return self.rattling


def ana_chi_modulate(metric: float, hub_name: str) -> ModulationResult:
    """
    Apply Ana-Chi basin modulation to a worker metric.

    metric × gravity (amplification); × memory_decay when the basin rattles.
    Desktop Layer-1 formulas are computed separately in run_desktop_formulas.

    Parameters
    ----------
    metric   : raw float metric from the worker (typically in [0, 1])
    hub_name : CAIRRN hub — HOME, MATH, CODE, COMMANDS, agent-context
    """
    basin: AnaChiBasin = basin_at_hub(hub_name)
    modulated = metric * basin.gravity
    if basin.rattling:
        modulated *= basin.memory_decay
    return ModulationResult(
        raw_metric=metric,
        basin_name=basin.name,
        chi=basin.chi,
        gravity=basin.gravity,
        rattling=basin.rattling,
        memory_decay=basin.memory_decay,
        modulated_metric=round(modulated, 8),
    )


# ---------------------------------------------------------------------------
# Layer 2 — neg_exp Sharding ("the backwards e")
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ShardSignal:
    """Shard assignment derived from one step of f(x) = −eˣ on basin χ."""
    chi: float
    neg_exp_one_step: float       # −e^χ  (always negative)
    natural_shard: int            # floor(e^χ × 8 / 14.44) clamped [0, 7]
    target_shard: int             # hub's canonical shard
    shard_mismatch: bool          # natural ≠ target → entropy signal
    conv_steps: int
    conv_final: float             # converges to x* ≈ −0.5671 when coherent
    converged: bool
    scope_nav: Optional[float] = None
    location_route: Optional[float] = None


def neg_exp_shard(hub_name: str) -> ShardSignal:
    """
    Run neg_exp analysis on the hub's Ana-Chi basin χ to produce a ShardSignal.

    Natural shard from one neg_exp step orders basins across the ring:
        −e^χ gives a unique fingerprint per basin.
        |−e^χ| = e^χ scaled to [0, 7] preserves the ordering.
    """
    basin = basin_at_hub(hub_name)
    chi = basin.chi

    one_step = neg_exp(chi)
    raw = math.exp(chi)
    nat_shard = min(int(raw * N_SHARDS / _MAX_NEG_EXP_RAW), N_SHARDS - 1)

    traj = run_neg_exp_map(chi, max_iter=200)
    conv_final = traj.steps[-1] if traj.steps else chi
    target = _HUB_PRIMARY_SHARD.get(hub_name, 0)

    return ShardSignal(
        chi=chi,
        neg_exp_one_step=round(one_step, 8),
        natural_shard=nat_shard,
        target_shard=target,
        shard_mismatch=(nat_shard != target),
        conv_steps=len(traj.steps),
        conv_final=round(conv_final, 8),
        converged=traj.converged,
    )


# ---------------------------------------------------------------------------
# Layer 3 — Coherence Enforcement ("the negative e")
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CoherenceResult:
    """
    Layer 3 — Coherence Enforcement ("the negative e").

    SKILL contract formula:
        coherence = exp(−steps / τ)

    where in this pipeline context:
        steps = |f(χ) − x*|   (distance after one neg_exp step to the fixed point)
        τ     = σ             (Euler-Ana-Chi derived scale; alias: _TAU ≈ 7.23)
        x*    = −W(1) ≈ −0.5671  (Lambert-W fixed point of f(x) = −eˣ)
        f(χ)  = −e^χ         (one application of the neg_exp map to basin χ)

    Threshold = W(1) ≈ 0.5671 (the fixed-point bound |f′(x*)| = W(1)).
    Identity: exp(−W(1)) = W(1) → HOME sits exactly at threshold.

    Coherence partition across hubs:
        agent-context > CODE > HOME ≥ threshold > MATH > COMMANDS
    HOME (χ = 𝒜_χ) is at the equilibrium boundary by construction.

    ana_chi_coherence (structural order):
        exp(−|χ − 𝒜_χ| / 0.40) — proximity to true_center (static per hub).
        1.0 at HOME, decays as χ moves away from equilibrium.
    """
    steps: int
    x_final: float
    x_one_step: float
    fixed_point: float
    error_to_fixed_point: float
    coherence: float
    coherent: bool
    tau: float = _TAU
    ana_chi_coherence: float = 0.0
    delta_two: Optional[float] = None
    tracer_consensus_k: Optional[float] = None
    tick_wisdom: Optional[float] = None

    @property
    def fixed_point_reached(self) -> bool:
        return abs(self.x_final - self.fixed_point) < 1e-4


def measure_coherence(signal: ShardSignal) -> CoherenceResult:
    """
    Layer 3 — Coherence Enforcement.

    SKILL formula:  coherence = exp(−steps / τ)

    Concretely:
        steps = |f(χ) − x*|   where f(χ) = −e^χ  (neg_exp_one_step)
        τ     = _TAU = _COHERENCE_SIGMA ≈ 7.23
        x*    = −W(1) ≈ −0.5671

    HOME (χ = 𝒜_χ) lands at steps = W(1) exactly, giving:
        coherence = exp(−W(1)/τ) = exp(−W(1)) = W(1)  (by identity exp(−W(1))=W(1)).

    ana_chi_coherence:
        exp(−|χ − 𝒜_χ| / 0.40) — structural proximity to true_center.
    """
    x_one_step = signal.neg_exp_one_step
    err = abs(x_one_step - NEG_EXP_FIXED_POINT)
    score = math.exp(-err / _COHERENCE_SIGMA)
    ana_coh = round(_ana_chi_coherence(signal.chi), 6)
    return CoherenceResult(
        steps=signal.conv_steps,
        x_final=signal.conv_final,
        x_one_step=x_one_step,
        fixed_point=NEG_EXP_FIXED_POINT,
        error_to_fixed_point=round(err, 8),
        coherence=score,            # exact float; round for display in to_dict()
        coherent=score >= _COHERENCE_THRESHOLD,
        tau=_TAU,
        ana_chi_coherence=ana_coh,
    )
