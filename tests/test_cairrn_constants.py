"""
tests/test_cairrn_constants.py — direct tests for workers/cairrn/_constants.py.

Covers:
  - _COHERENCE_THRESHOLD == W(1) == abs(NEG_EXP_FIXED_POINT)
  - Lambert-W identity: exp(−W(1)) = W(1)
  - Sigma derivation: coh(HOME) == W(1) exactly (HOME at Euler boundary)
  - Ana-Chi near-identity: 𝒜_χ / e ≈ W(1) within documented tolerance
  - Hub coherence partition: agent-context/CODE/HOME coherent; MATH/COMMANDS not
"""
from __future__ import annotations

import math

import pytest

from sims.attractors import NEG_EXP_FIXED_POINT
from sims.ana_chi import ANA_CHI_CONSTANT, basin_at_hub
from workers.cairrn._constants import (
    _COHERENCE_THRESHOLD,
    _COHERENCE_SIGMA,
    _W1,
    N_SHARDS,
    _MAX_NEG_EXP_RAW,
    _HUB_PRIMARY_SHARD,
)
from workers.cairrn.layers import neg_exp_shard, measure_coherence


# ---------------------------------------------------------------------------
# Threshold
# ---------------------------------------------------------------------------

class TestThreshold:
    def test_threshold_is_w1(self):
        assert _COHERENCE_THRESHOLD == abs(NEG_EXP_FIXED_POINT)

    def test_w1_alias(self):
        assert _W1 == _COHERENCE_THRESHOLD

    def test_threshold_approximate_value(self):
        assert abs(_COHERENCE_THRESHOLD - 0.5671) < 1e-4

    def test_lambert_w_identity_holds_in_float(self):
        """exp(−W(1)) = W(1) — exact in IEEE 754 double."""
        assert math.exp(-_W1) == _W1


# ---------------------------------------------------------------------------
# Sigma derivation
# ---------------------------------------------------------------------------

class TestSigmaDerivation:
    def test_sigma_formula(self):
        """σ = (e^𝒜_χ − W(1)) / W(1) — derived from Ana-Chi and Euler."""
        expected = (math.exp(ANA_CHI_CONSTANT) - _W1) / _W1
        assert abs(_COHERENCE_SIGMA - expected) < 1e-12

    def test_sigma_positive(self):
        assert _COHERENCE_SIGMA > 0.0

    def test_sigma_approximate_value(self):
        assert 7.0 < _COHERENCE_SIGMA < 7.5

    def test_home_coherence_equals_w1(self):
        """
        HOME hub (χ = 𝒜_χ) must have coherence ≈ W(1) — at the Euler boundary.
        Construction guarantees coh(HOME) = exp(−W(1)) = W(1); the ~1e-10
        residual is rounding from neg_exp_one_step stored at 8 decimal places.
        """
        sig = neg_exp_shard("HOME")
        coh = measure_coherence(sig)
        assert abs(coh.coherence - _W1) < 1e-9, (
            f"HOME coherence {coh.coherence:.16f} should equal W(1) {_W1:.16f}"
        )

    def test_home_is_coherent(self):
        sig = neg_exp_shard("HOME")
        coh = measure_coherence(sig)
        assert coh.coherent is True


# ---------------------------------------------------------------------------
# Ana-Chi near-identity
# ---------------------------------------------------------------------------

class TestAnaChiNearIdentity:
    def test_ana_chi_over_e_approx_w1(self):
        """𝒜_χ / e ≈ W(1) within documented tolerance of 0.017%."""
        approx = ANA_CHI_CONSTANT / math.e
        relative_error = abs(approx - _W1) / _W1
        assert relative_error < 2e-4, (
            f"relative error {relative_error:.2e} exceeds 0.02% — near-identity broken"
        )

    def test_near_identity_is_not_exact(self):
        """Document that this is approximate, not exact."""
        assert ANA_CHI_CONSTANT / math.e != _W1


# ---------------------------------------------------------------------------
# Hub coherence partition
# ---------------------------------------------------------------------------

COHERENT_HUBS    = ("agent-context", "CODE", "HOME")
INCOHERENT_HUBS  = ("MATH", "COMMANDS")

class TestHubPartition:
    @pytest.mark.parametrize("hub", COHERENT_HUBS)
    def test_coherent_hubs_pass(self, hub):
        sig = neg_exp_shard(hub)
        coh = measure_coherence(sig)
        assert coh.coherent is True, (
            f"{hub}: expected coherent but coh={coh.coherence:.4f} < threshold={_COHERENCE_THRESHOLD:.4f}"
        )

    @pytest.mark.parametrize("hub", INCOHERENT_HUBS)
    def test_incoherent_hubs_reroute(self, hub):
        sig = neg_exp_shard(hub)
        coh = measure_coherence(sig)
        assert coh.coherent is False, (
            f"{hub}: expected incoherent but coh={coh.coherence:.4f} >= threshold={_COHERENCE_THRESHOLD:.4f}"
        )

    def test_coherence_ordering(self):
        """agent-context > CODE > HOME > MATH > COMMANDS (by neg_exp distance to x*)."""
        order = ["agent-context", "CODE", "HOME", "MATH", "COMMANDS"]
        scores = [measure_coherence(neg_exp_shard(h)).coherence for h in order]
        for i in range(len(scores) - 1):
            assert scores[i] > scores[i + 1], (
                f"Expected {order[i]} ({scores[i]:.4f}) > {order[i+1]} ({scores[i+1]:.4f})"
            )


# ---------------------------------------------------------------------------
# Other constants
# ---------------------------------------------------------------------------

class TestOtherConstants:
    def test_n_shards(self):
        assert N_SHARDS == 8

    def test_max_neg_exp_raw(self):
        assert abs(_MAX_NEG_EXP_RAW - math.exp(2.67)) < 1e-10

    def test_hub_primary_shard_coverage(self):
        assert set(_HUB_PRIMARY_SHARD.keys()) == {"HOME", "MATH", "CODE", "COMMANDS", "agent-context"}

    def test_hub_primary_shard_in_range(self):
        for hub, shard in _HUB_PRIMARY_SHARD.items():
            assert 0 <= shard < N_SHARDS, f"{hub}: shard {shard} out of range"
