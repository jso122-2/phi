"""Tests for workers.cerberus — mathematical bind and respawn guard."""
from __future__ import annotations

import math

import pytest

from workers.cerberus import (
    BindResult,
    CerberusExhausted,
    CerberusGuard,
    ceb_1,
    ceb_2,
    evaluate,
)


# ---------------------------------------------------------------------------
# ceb_1 — linear deviation
# ---------------------------------------------------------------------------


class TestCeb1:
    def test_perfect_worker_default_params(self):
        # x=1, z=0, A=1, C=0 → |1 - 0/1 - 0 - 1| = 0
        assert ceb_1(1.0) == pytest.approx(0.0)

    def test_zero_worker(self):
        # x=0 → |0 - 0 - 0 - 1| = 1
        assert ceb_1(0.0) == pytest.approx(1.0)

    def test_symmetry(self):
        # Deviation of +0.3 and -0.3 from target should give same ceb_1 magnitude
        pos = ceb_1(1.3)
        neg = ceb_1(0.7)
        assert pos == pytest.approx(neg)

    def test_custom_params(self):
        # x=2, z=1, A=2, C=0.5 → |2 - 1/2 - 0.5 - 1| = |2 - 0.5 - 0.5 - 1| = 0
        assert ceb_1(2.0, z=1.0, A=2.0, C=0.5) == pytest.approx(0.0)

    def test_zero_A_raises(self):
        with pytest.raises(ValueError, match="non-zero"):
            ceb_1(1.0, A=0.0)

    def test_always_non_negative(self):
        for x in [-5.0, -1.0, 0.0, 0.5, 1.0, 2.0, 10.0]:
            assert ceb_1(x) >= 0.0


# ---------------------------------------------------------------------------
# ceb_2 — factorial escalation
# ---------------------------------------------------------------------------


class TestCeb2:
    def test_m0_no_escalation(self):
        c1 = 0.4
        assert ceb_2(c1, 0) == pytest.approx(math.factorial(0) * c1)

    def test_m1_still_identity(self):
        c1 = 0.4
        assert ceb_2(c1, 1) == pytest.approx(1.0 * c1)

    def test_m3_factorial_6(self):
        c1 = 0.5
        assert ceb_2(c1, 3) == pytest.approx(6.0 * c1)

    def test_m5_factorial_120(self):
        c1 = 0.1
        assert ceb_2(c1, 5) == pytest.approx(120.0 * c1)

    def test_clamped_at_12(self):
        # M > 12 should be clamped to 12
        c1 = 0.01
        assert ceb_2(c1, 100) == pytest.approx(math.factorial(12) * c1)

    def test_negative_m_treated_as_zero(self):
        c1 = 0.5
        assert ceb_2(c1, -3) == pytest.approx(math.factorial(0) * c1)


# ---------------------------------------------------------------------------
# evaluate — combined bind evaluation
# ---------------------------------------------------------------------------


class TestEvaluate:
    def test_perfect_worker_passes(self):
        result = evaluate(1.0, M=0)
        assert result.passed
        assert not result.soft_violation
        assert not result.hard_violation

    def test_zero_metric_soft_violation(self):
        result = evaluate(0.0, M=0, tau_1=0.5, tau_2=100.0)
        # ceb_1 = 1.0 > 0.5 → soft
        assert result.soft_violation
        assert not result.hard_violation
        assert not result.passed

    def test_hard_violation_at_high_retry(self):
        # ceb_1 = 1.0, M=5 → ceb_2 = 120 > tau_2=10
        result = evaluate(0.0, M=5, tau_1=0.5, tau_2=10.0)
        assert result.hard_violation

    def test_result_fields_populated(self):
        result = evaluate(0.8, M=2, z=0.0, A=1.0, C=0.0, tau_1=0.3, tau_2=5.0)
        assert isinstance(result, BindResult)
        assert result.x == 0.8
        assert result.M == 2
        assert result.c1 >= 0.0
        assert result.c2 >= 0.0

    def test_str_representation(self):
        result = evaluate(1.0)
        assert "PASS" in str(result)

    def test_soft_str(self):
        result = evaluate(0.0, M=0, tau_1=0.3, tau_2=1000.0)
        assert "SOFT" in str(result)

    def test_hard_str(self):
        result = evaluate(0.0, M=5, tau_1=0.3, tau_2=0.1)
        assert "HARD" in str(result)


# ---------------------------------------------------------------------------
# CerberusGuard — integrated respawn tests
# ---------------------------------------------------------------------------


class TestCerberusGuard:
    def _make_guard(self, value_seq: list[float], tau_1: float = 0.5, tau_2: float = 10.0):
        """Guard that yields successive values from value_seq."""
        it = iter(value_seq)

        def factory():
            def fn():
                return next(it)
            return fn

        return CerberusGuard(
            factory=factory,
            metric_fn=lambda v: v,
            tau_1=tau_1,
            tau_2=tau_2,
            max_retries=6,
        )

    def test_passing_worker_returns_value(self):
        guard = self._make_guard([1.0])
        result = guard()
        assert result == pytest.approx(1.0)

    def test_bind_log_populated(self):
        guard = self._make_guard([1.0])
        guard()
        assert len(guard.bind_log) == 1

    def test_soft_violation_retries(self):
        # First call fails softly (0.0), second passes (1.0)
        guard = self._make_guard([0.0, 1.0], tau_1=0.5, tau_2=1000.0)
        result = guard()
        assert result == pytest.approx(1.0)
        assert len(guard.bind_log) == 2

    def test_hard_violation_triggers_respawn(self):
        # M=5 with ceb_1=1.0 → ceb_2=120 > tau_2=10 → hard
        # After respawn, returns 1.0
        values = [0.0] * 6 + [1.0]
        guard = self._make_guard(values, tau_1=0.3, tau_2=10.0)
        result = guard()
        assert result == pytest.approx(1.0)
        assert guard.bind_log[-1].passed

    def test_exhausted_raises(self):
        guard = self._make_guard([0.0] * 20, tau_1=0.1, tau_2=0.1)
        with pytest.raises(CerberusExhausted):
            guard()

    def test_retry_resets_after_pass(self):
        guard = self._make_guard([1.0, 0.0, 1.0])
        guard()  # passes
        assert guard.retry_count == 0
