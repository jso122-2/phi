"""
tests/test_gate.py — direct tests for engine/gate.py.

Covers:
  - gate_coherence decay formula
  - COHERENCE_THRESHOLD derivation (W(1) = abs(NEG_EXP_FIXED_POINT))
  - is_coherent threshold boundary
  - gate_pass convenience wrapper
  - tau=0 guard (no ZeroDivisionError)
"""
from __future__ import annotations

import math

import pytest

from engine.gate import COHERENCE_THRESHOLD, gate_coherence, gate_pass, is_coherent
from sims.attractors import NEG_EXP_FIXED_POINT


# ---------------------------------------------------------------------------
# Threshold derivation
# ---------------------------------------------------------------------------

class TestThresholdDerivation:
    def test_threshold_equals_w1(self):
        """COHERENCE_THRESHOLD must equal W(1) = abs(NEG_EXP_FIXED_POINT)."""
        assert COHERENCE_THRESHOLD == abs(NEG_EXP_FIXED_POINT)

    def test_threshold_value(self):
        assert abs(COHERENCE_THRESHOLD - 0.5671432904097838) < 1e-15

    def test_lambert_w_identity(self):
        """exp(−W(1)) = W(1) — the exact Lambert-W coherence identity."""
        assert abs(math.exp(-COHERENCE_THRESHOLD) - COHERENCE_THRESHOLD) < 1e-15


# ---------------------------------------------------------------------------
# gate_coherence
# ---------------------------------------------------------------------------

class TestGateCoherence:
    def test_zero_steps_is_one(self):
        assert gate_coherence(0, tau_cairrn=10.0) == pytest.approx(1.0)

    def test_decays_with_steps(self):
        c0 = gate_coherence(0, 10.0)
        c5 = gate_coherence(5, 10.0)
        c10 = gate_coherence(10, 10.0)
        assert c0 > c5 > c10

    def test_at_tau_equals_exp_neg_one(self):
        tau = 7.0
        assert gate_coherence(int(tau), tau) == pytest.approx(math.exp(-1.0), abs=1e-4)

    def test_output_in_zero_one(self):
        for steps in range(0, 100, 10):
            c = gate_coherence(steps, tau_cairrn=10.0)
            assert 0.0 < c <= 1.0

    def test_tau_zero_no_crash(self):
        """tau=0 must not raise ZeroDivisionError — clamped to 1e-9."""
        c = gate_coherence(1, tau_cairrn=0.0)
        assert 0.0 <= c <= 1.0


# ---------------------------------------------------------------------------
# is_coherent
# ---------------------------------------------------------------------------

class TestIsCoherent:
    def test_above_threshold(self):
        assert is_coherent(COHERENCE_THRESHOLD + 0.01) is True

    def test_at_threshold(self):
        assert is_coherent(COHERENCE_THRESHOLD) is True

    def test_below_threshold(self):
        assert is_coherent(COHERENCE_THRESHOLD - 0.01) is False

    def test_zero_incoherent(self):
        assert is_coherent(0.0) is False

    def test_one_coherent(self):
        assert is_coherent(1.0) is True

    def test_custom_threshold(self):
        assert is_coherent(0.40, threshold=0.30) is True
        assert is_coherent(0.20, threshold=0.30) is False


# ---------------------------------------------------------------------------
# gate_pass
# ---------------------------------------------------------------------------

class TestGatePass:
    def test_returns_tuple(self):
        result = gate_pass(0, tau_cairrn=10.0)
        assert isinstance(result, tuple) and len(result) == 2

    def test_fresh_arm_is_coherent(self):
        coherent, score = gate_pass(0, tau_cairrn=10.0)
        assert coherent is True
        assert score == pytest.approx(1.0)

    def test_stale_arm_incoherent(self):
        """After enough steps the arm drops below threshold."""
        coherent, score = gate_pass(100, tau_cairrn=10.0)
        assert coherent is False
        assert score < COHERENCE_THRESHOLD

    def test_score_consistent_with_is_coherent(self):
        for steps in (0, 3, 7, 15):
            coherent, score = gate_pass(steps, tau_cairrn=10.0)
            assert coherent == is_coherent(score)
