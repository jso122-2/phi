"""
Coherence gate for OctopusTracer arms.

Formula (ARCHITECTURE LOCKED — pow.md):

    coherence = exp(−steps / τ_cairrn)

    if coherence < W(1)  →  arms suppress write, read-only pass
    if coherence ≥ W(1)  →  full arm authority, Samba MCP live

Threshold derivation:
    W(1) = abs(NEG_EXP_FIXED_POINT) = 𝒜_χ / e ≈ 0.5671
    Identity: exp(−W(1)) = W(1) — coherence at HOME equals the threshold.

The gate is stateless — call gate_coherence() with (steps, tau) each tick.
"""

from __future__ import annotations

import math

from sims.attractors import NEG_EXP_FIXED_POINT

# Euler-Lambert bound: W(1) = |x*| = 𝒜_χ / e ≈ 0.5671
COHERENCE_THRESHOLD: float = abs(NEG_EXP_FIXED_POINT)


def gate_coherence(steps: int, tau_cairrn: float) -> float:
    """
    Compute arm coherence score.

    coherence = exp(−steps / τ_cairrn)

    Parameters
    ----------
    steps       : number of steps elapsed since last reset
    tau_cairrn  : CAIRRN time constant  (must be > 0)

    Returns
    -------
    float in (0, 1]
    """
    tau = max(float(tau_cairrn), 1e-9)
    return math.exp(-steps / tau)


def is_coherent(coherence: float, threshold: float = COHERENCE_THRESHOLD) -> bool:
    """True when arms have full write authority."""
    return coherence >= threshold


def gate_pass(
    steps: int,
    tau_cairrn: float,
    threshold: float = COHERENCE_THRESHOLD,
) -> tuple[bool, float]:
    """
    Convenience: compute coherence and gate flag in one call.

    Returns
    -------
    (coherent, coherence_score)
    """
    coh = gate_coherence(steps, tau_cairrn)
    return is_coherent(coh, threshold), coh
