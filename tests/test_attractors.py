"""Tests for sims.attractors — math and convergence checks."""

import math
import pytest

from sims.attractors import (
    ALPHA,
    NEG_EXP_FIXED_POINT,
    potential,
    potential_grad,
    potential_hess,
    stability_at,
    neg_exp,
    neg_exp_deriv,
    run_double_well,
    run_neg_exp_map,
    sweep_initial_conditions,
    summarise,
)


# ---------------------------------------------------------------------------
# Math: potential
# ---------------------------------------------------------------------------

class TestPotential:
    def test_minima_at_alpha(self):
        """V(±α) == 0 — wells sit at zero potential."""
        assert potential(ALPHA) == pytest.approx(0.0, abs=1e-10)
        assert potential(-ALPHA) == pytest.approx(0.0, abs=1e-10)

    def test_potential_at_origin(self):
        """V(0) = α⁴."""
        assert potential(0.0) == pytest.approx(ALPHA**4, rel=1e-9)

    def test_gradient_zero_at_fixed_points(self):
        """V'(0) == 0 and V'(±α) == 0."""
        assert potential_grad(0.0) == pytest.approx(0.0, abs=1e-10)
        assert potential_grad(ALPHA) == pytest.approx(0.0, abs=1e-10)
        assert potential_grad(-ALPHA) == pytest.approx(0.0, abs=1e-10)

    def test_hessian_sign(self):
        """V''(±α) > 0 (stable), V''(0) < 0 (unstable saddle)."""
        assert potential_hess(ALPHA) > 0
        assert potential_hess(-ALPHA) > 0
        assert potential_hess(0.0) < 0

    def test_stability_labels(self):
        assert stability_at(ALPHA) == "stable"
        assert stability_at(-ALPHA) == "stable"
        assert stability_at(0.0) == "unstable"


# ---------------------------------------------------------------------------
# Math: negative exponential
# ---------------------------------------------------------------------------

class TestNegExp:
    def test_value(self):
        assert neg_exp(0.0) == pytest.approx(-1.0, rel=1e-9)
        assert neg_exp(1.0) == pytest.approx(-math.e, rel=1e-9)

    def test_deriv_equals_function(self):
        """d/dx(-e^x) = -e^x — derivative equals the function itself."""
        for x in [-2.0, -1.0, 0.0, 0.5, 1.0, 2.0]:
            assert neg_exp_deriv(x) == pytest.approx(neg_exp(x), rel=1e-12)

    def test_fixed_point_exists(self):
        """
        -e^x = x has exactly one real solution: x* = -W(1) ≈ -0.5671.
        This is the Lambert W fixed point.  Verify f(x*) ≈ x*.
        """
        x_star = NEG_EXP_FIXED_POINT
        assert neg_exp(x_star) == pytest.approx(x_star, abs=1e-6)

    def test_fixed_point_is_stable(self):
        """
        |f'(x*)| = e^(x*) = W(1) ≈ 0.5671 < 1 → attracting fixed point.
        """
        x_star = NEG_EXP_FIXED_POINT
        assert abs(neg_exp_deriv(x_star)) < 1.0


# ---------------------------------------------------------------------------
# Simulation: double-well convergence
# ---------------------------------------------------------------------------

class TestDoubleWellSim:
    @pytest.mark.parametrize("x0", [0.1, 0.5, 1.0])
    def test_converges_to_positive_alpha(self, x0):
        """Small positive x0 lies in the basin of +α."""
        traj = run_double_well(x0)
        assert traj.converged, f"Did not converge from x0={x0}"
        assert traj.converged_at == pytest.approx(ALPHA, abs=1e-4)

    @pytest.mark.parametrize("x0", [-0.1, -0.5, -1.0])
    def test_converges_to_negative_alpha(self, x0):
        """Small negative x0 lies in the basin of -α."""
        traj = run_double_well(x0)
        assert traj.converged, f"Did not converge from x0={x0}"
        assert traj.converged_at == pytest.approx(-ALPHA, abs=1e-4)

    @pytest.mark.parametrize("x0", [3.0, 5.0, -3.0, -5.0])
    def test_large_x0_converges_to_either_well(self, x0):
        """Large x0 can overshoot — it still converges to one of ±α."""
        traj = run_double_well(x0, max_iter=2000)
        assert traj.converged, f"Did not converge from x0={x0}"
        assert abs(traj.converged_at) == pytest.approx(ALPHA, abs=1e-4)

    def test_trajectory_length_reasonable(self):
        traj = run_double_well(1.0)
        assert 2 <= len(traj.steps) <= 500

    def test_custom_alpha(self):
        alpha = 1.94
        traj = run_double_well(1.0, alpha=alpha)
        assert traj.converged
        assert traj.converged_at == pytest.approx(alpha, abs=1e-4)


# ---------------------------------------------------------------------------
# Simulation: neg-exp map diverges
# ---------------------------------------------------------------------------

class TestNegExpSim:
    def test_converges_to_lambert_w_fixed_point(self):
        """
        Despite d/dx(-e^x) = -e^x, the map converges to x* = -W(1) ≈ -0.5671
        because |f'(x*)| = W(1) ≈ 0.567 < 1 (attracting fixed point).
        """
        traj = run_neg_exp_map(0.0)
        assert traj.converged, "Expected convergence to Lambert W fixed point"
        assert traj.converged_at == pytest.approx(NEG_EXP_FIXED_POINT, abs=1e-5)

    def test_converges_from_various_starts(self):
        for x0 in [-2.0, -1.0, 0.0, 0.5]:
            traj = run_neg_exp_map(x0)
            assert traj.converged, f"Did not converge from x0={x0}"
            assert traj.converged_at == pytest.approx(NEG_EXP_FIXED_POINT, abs=1e-5)

    def test_trajectory_recorded(self):
        traj = run_neg_exp_map(0.0)
        assert len(traj.steps) >= 2


# ---------------------------------------------------------------------------
# Sweep and summary
# ---------------------------------------------------------------------------

class TestSweep:
    def test_sweep_returns_correct_count(self):
        x0s = [1.0, -1.0, 2.0, -2.0]
        trajs = sweep_initial_conditions(x0s, run_double_well)
        assert len(trajs) == len(x0s)

    def test_summary_keys(self):
        traj = run_double_well(1.0)
        s = summarise(traj)
        for key in ("x0", "steps", "final_x", "converged", "target", "error_to_attractor"):
            assert key in s

    def test_summary_error_small(self):
        traj = run_double_well(1.0)
        s = summarise(traj)
        assert s["error_to_attractor"] < 1e-4


# ---------------------------------------------------------------------------
# Kramers + Langevin
# ---------------------------------------------------------------------------

class TestKramers:
    def test_omegas_match_hessian(self):
        from sims.attractors import kramers_rate
        k = kramers_rate(2.0)
        assert k["omega_0"] == pytest.approx(2.0 * math.sqrt(2.0) * ALPHA, rel=1e-9)
        assert k["omega_s"] == pytest.approx(2.0 * ALPHA, rel=1e-9)
        assert k["delta_V"] == pytest.approx(ALPHA ** 4, rel=1e-9)

    def test_noise_scale_2_tau_steps(self):
        from sims.attractors import kramers_rate
        k = kramers_rate(2.0, lr=0.05)
        assert k["tau_steps"] == pytest.approx(231.4, rel=0.01)
        assert k["rate"] == pytest.approx(0.0864, rel=0.01)

    def test_zero_noise_is_infinite(self):
        from sims.attractors import kramers_rate
        k = kramers_rate(0.0)
        assert k["tau_steps"] == float("inf")
        assert k["rate"] == 0.0


class TestLangevin:
    def test_zero_noise_stays_in_well(self):
        from sims.attractors import run_langevin
        traj = run_langevin(ALPHA, noise_scale=0.0, max_iter=50, seed=0)
        assert traj.steps[-1] == pytest.approx(ALPHA, abs=0.05)

    def test_reproducible_with_seed(self):
        from sims.attractors import run_langevin
        a = run_langevin(ALPHA, noise_scale=2.0, max_iter=20, seed=7)
        b = run_langevin(ALPHA, noise_scale=2.0, max_iter=20, seed=7)
        assert a.steps == b.steps

    def test_mfpt_high_noise_escapes(self):
        from sims.attractors import measure_mfpt
        result = measure_mfpt(noise_scale=3.0, n_trials=20, max_iter=2000, seed=1)
        assert result["n_escaped"] >= 10
        assert result["mean_escape_steps"] is not None
