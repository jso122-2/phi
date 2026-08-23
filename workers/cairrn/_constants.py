"""
CAIRRN system constants — Euler-Ana-Chi bound formalisation.

All numeric anchors are derived from one exact identity and one near-identity:

    Near-identity — Ana-Chi / Euler ≈ W(1)  [not exact]:
        𝒜_χ / e  =  1.5414 / 2.71828…  ≈  0.56705  ≈  W(1)  =  0.56714…
        absolute error ≈ 9.4e-5  (0.017 %)
        This is a meaningful structural coincidence, not an exact equality.
        The threshold is derived from abs(NEG_EXP_FIXED_POINT) directly — not from 𝒜_χ/e.

    Exact identity — Lambert-W coherence bound:
        exp(−W(1))  =  W(1)
        (the Euler decay evaluated at the neg_exp fixed point equals the fixed point itself)
        This identity holds exactly in float: diff = 0.00e+00.
        It is the structural reason HOME sits precisely at the threshold.

Sigma derivation
-----------------
σ is chosen so the HOME hub (χ = 𝒜_χ = 1.5414) lands exactly at the threshold:

    coh(HOME) = exp(−|f(𝒜_χ) − x*| / σ)  =  W(1)

    where  f(𝒜_χ) = −e^(𝒜_χ),  x* = −W(1) = NEG_EXP_FIXED_POINT

    ⟹ σ = (e^(𝒜_χ) − W(1)) / W(1)

Consequences
------------
  χ < 𝒜_χ  →  coherence > W(1)  →  coherent   (agent-context, CODE)
  χ = 𝒜_χ  →  coherence = W(1)  →  at boundary (HOME — equilibrium)
  χ > 𝒜_χ  →  coherence < W(1)  →  incoherent, re-routes to HOME
                                     (MATH at white_peak, COMMANDS at escape)

The re-routing of MATH and COMMANDS through HOME is the structural pull of
the true_center gravity well — the rattling basins are stabilised through
equilibrium.
"""
from __future__ import annotations

import math

from sims.attractors import NEG_EXP_FIXED_POINT
from sims.ana_chi import ANA_CHI_CONSTANT

N_SHARDS: int = 8
_MAX_NEG_EXP_RAW: float = math.exp(2.67)   # e^escape_chi ≈ 14.44 — COMMANDS ceiling

# ---------------------------------------------------------------------------
# Euler-Ana-Chi coherence bound
# ---------------------------------------------------------------------------

# W(1) = abs(NEG_EXP_FIXED_POINT) = 𝒜_χ / e  ≈ 0.5671
# This is both the Euler derivative bound |f'(x*)| < 1 and the coherence threshold.
_W1: float = abs(NEG_EXP_FIXED_POINT)

_COHERENCE_THRESHOLD: float = _W1
"""
Euler-Lambert bound: W(1) ≈ 0.5671.
Derived as: 𝒜_χ / e  =  ANA_CHI_CONSTANT / math.e.
Identity: exp(−W(1)) = W(1) — coherence at HOME equals the threshold.
"""

_COHERENCE_SIGMA: float = (math.exp(ANA_CHI_CONSTANT) - _W1) / _W1
"""
Sigma derived so HOME (χ = 𝒜_χ) sits at exactly the Euler bound:
    σ = (e^𝒜_χ − W(1)) / W(1)
    coh(HOME) = exp(−W(1)) = W(1) = threshold
"""

# ---------------------------------------------------------------------------
# SKILL-facing alias
# ---------------------------------------------------------------------------

_TAU: float = _COHERENCE_SIGMA
"""
τ — the CAIRRN SKILL time constant for Layer 3 coherence.

The SKILL contract describes Layer 3 as:

    coherence = exp(−steps / τ)

where  steps = |f(χ) − x*|  (distance after one neg_exp step from basin χ)
and    τ     = σ             (the Euler-Ana-Chi derived scale above).

This alias bridges the SKILL vocabulary ("τ") to the implementation constant
("σ").  They are numerically identical; use _TAU when referencing the SKILL
formula and _COHERENCE_SIGMA when referencing the derivation.

Typical value: τ ≈ 7.23   (≈ (e^1.5414 − W(1)) / W(1))
"""

# Hub → canonical shard index (first shard when a hub owns multiple)
_HUB_PRIMARY_SHARD: dict[str, int] = {
    "HOME":          0,
    "MATH":          1,
    "CODE":          3,
    "COMMANDS":      5,
    "agent-context": 6,
}
