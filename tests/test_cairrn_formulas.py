"""
tests/test_cairrn_formulas.py — unit tests for workers/cairrn/formulas.py.

Covers all 14 pure formula functions:
  Layer X  : f_constraint_var, f_forecast_score, f_cairrn_composite
  Layer 1  : f_energy_weighted, f_energy_consumption, f_height_node,
             f_global_rzone, f_local_friction_d
  Layer 2  : f_scope_nav, f_location_route
  Layer 3  : f_delta_two, f_tracer_consensus_k, f_tick_wisdom
  Z-Space  : f_cairrn_z_space

Each test covers: basic output, division-by-zero guards, sign behaviour.
"""
from __future__ import annotations

import math

import pytest

from workers.cairrn.formulas import (
    f_cairrn_composite,
    f_cairrn_z_space,
    f_constraint_var,
    f_delta_two,
    f_energy_consumption,
    f_energy_weighted,
    f_forecast_score,
    f_global_rzone,
    f_height_node,
    f_local_friction_d,
    f_location_route,
    f_scope_nav,
    f_tick_wisdom,
    f_tracer_consensus_k,
    f_tp_rar,
    f_secondary_model_select,
    f_scup_canonical,
)


# ---------------------------------------------------------------------------
# Layer X — composite / constraint
# ---------------------------------------------------------------------------

class TestConstraintVar:
    def test_basic(self):
        # x_c = Lh / P − O
        result = f_constraint_var(likelihood=0.6, possibility=0.4, opportunity_cost=0.1)
        assert result == pytest.approx(0.6 / 0.4 - 0.1)

    def test_zero_possibility_no_crash(self):
        result = f_constraint_var(likelihood=0.5, possibility=0.0, opportunity_cost=0.0)
        assert math.isfinite(result)

    def test_sign_positive_likelihood_dominant(self):
        assert f_constraint_var(1.0, 1.0, 0.0) == pytest.approx(1.0)

    def test_opportunity_cost_subtracts(self):
        base = f_constraint_var(0.6, 0.4, 0.0)
        with_cost = f_constraint_var(0.6, 0.4, 1.0)
        assert base - with_cost == pytest.approx(1.0)


class TestForecastScore:
    def test_basic_output_finite(self):
        result = f_forecast_score(
            forecasting_result=0.8,
            constraint_var=1.0,
            temporal_validator=1.0,
            energy_available=1.0,
        )
        assert math.isfinite(result)

    def test_zero_constraint_var_no_crash(self):
        result = f_forecast_score(0.8, 0.0, 1.0, 1.0)
        assert math.isfinite(result)

    def test_euler_baseline(self):
        # Distance from e; at forecasting_result=e exactly → numerator=0
        result = f_forecast_score(math.e, 1.0, 1.0, 1.0)
        assert result == pytest.approx(0.0, abs=1e-10)

    def test_scales_with_energy(self):
        r1 = f_forecast_score(0.5, 1.0, 1.0, 1.0)
        r2 = f_forecast_score(0.5, 1.0, 1.0, 2.0)
        assert r2 == pytest.approx(r1 * 2.0)


class TestCairrnComposite:
    def test_basic_output_finite(self):
        result = f_cairrn_composite(
            confidence=0.8, scope=0.5, dawn_data=0.6,
            energy_cost=0.3, tick_interval=10,
        )
        assert math.isfinite(result)

    def test_tick_interval_additive(self):
        r1 = f_cairrn_composite(0.5, 0.5, 0.5, 0.2, 0)
        r5 = f_cairrn_composite(0.5, 0.5, 0.5, 0.2, 5)
        assert r5 - r1 == pytest.approx(5.0)


# ---------------------------------------------------------------------------
# Layer 1 — Ana-Chi modulation formulas
# ---------------------------------------------------------------------------

class TestEnergyWeighted:
    def test_basic(self):
        result = f_energy_weighted(
            energies=[1.0, 2.0],
            desirability_costs=[0.5, 0.5],
            resources=2.0,
            dist_weighted_times=[1.0, 1.0],
            positive_normalisation=1.0,
        )
        assert math.isfinite(result) and result >= 0.0

    def test_zero_resources_no_crash(self):
        result = f_energy_weighted([1.0], [0.5], 0.0, [1.0], 1.0)
        assert math.isfinite(result)

    def test_zero_normalisation_no_crash(self):
        result = f_energy_weighted([1.0], [0.5], 1.0, [1.0], 0.0)
        assert math.isfinite(result)

    def test_proportional_to_normalisation(self):
        r1 = f_energy_weighted([1.0], [0.0], 1.0, [1.0], 1.0)
        r2 = f_energy_weighted([1.0], [0.0], 1.0, [1.0], 2.0)
        assert r2 == pytest.approx(r1 * 2.0)


class TestEnergyConsumption:
    def test_basic_finite(self):
        result = f_energy_consumption(2.0, 1.0, 1.0, 1.0, 1.0)
        assert math.isfinite(result)

    def test_zero_performance_no_crash(self):
        result = f_energy_consumption(2.0, 1.0, 1.0, 0.0, 1.0)
        assert math.isfinite(result)

    def test_proportional_to_tracer_consensus(self):
        r1 = f_energy_consumption(2.0, 1.0, 1.0, 1.0, 1.0)
        r2 = f_energy_consumption(2.0, 1.0, 1.0, 1.0, 2.0)
        assert r2 == pytest.approx(r1 * 2.0)


class TestHeightNode:
    def test_basic_finite(self):
        assert math.isfinite(f_height_node(1.0, 1.0, 0.5))

    def test_formula(self):
        # H = |g + A| − Tcv
        assert f_height_node(1.0, 2.0, 0.5) == pytest.approx(abs(1.0 + 2.0) - 0.5)


class TestGlobalRzone:
    def test_basic_finite(self):
        assert math.isfinite(f_global_rzone(2.0, 1.0, 1.0, 0.5))

    def test_zero_pressure_no_crash(self):
        assert math.isfinite(f_global_rzone(2.0, 0.0, 1.0, 0.5))


class TestLocalFrictionD:
    def test_basic_finite(self):
        assert math.isfinite(f_local_friction_d(0.5, 0.3, 0.8, 0.4, 0.1))

    def test_zero_scop_no_crash(self):
        assert math.isfinite(f_local_friction_d(0.5, 0.3, 0.8, 0.0, 0.1))


# ---------------------------------------------------------------------------
# Layer 2 — neg_exp sharding formulas
# ---------------------------------------------------------------------------

class TestScopeNav:
    def test_basic_finite(self):
        assert math.isfinite(f_scope_nav(1.0, 0.5, 0.2, 1, 1.0))

    def test_zero_shi_no_crash(self):
        assert math.isfinite(f_scope_nav(1.0, 0.5, 0.2, 1, 0.0))

    def test_boolean_temporal_zero_gives_zero(self):
        assert f_scope_nav(1.0, 0.5, 0.2, 0, 1.0) == pytest.approx(0.0)


class TestLocationRoute:
    def test_basic_finite(self):
        assert math.isfinite(f_location_route(5.0, 2.0, 3, [1.0, 1.5]))

    def test_zero_energy_projected_no_crash(self):
        assert math.isfinite(f_location_route(5.0, 0.0, 3, [1.0]))

    def test_empty_waypoints_zero(self):
        assert f_location_route(5.0, 2.0, 3, []) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Layer 3 — coherence enforcement formulas
# ---------------------------------------------------------------------------

class TestDeltaTwo:
    def test_basic_finite(self):
        assert math.isfinite(f_delta_two(1.0, 2.0, 0.5, 0.3))

    def test_zero_time_steps_no_crash(self):
        assert math.isfinite(f_delta_two(1.0, 0.0, 0.5, 0.3))

    def test_zero_pressure_gradient_no_crash(self):
        assert math.isfinite(f_delta_two(1.0, 2.0, 0.0, 0.3))


class TestTracerConsensusK:
    def test_basic(self):
        # K = |Tcv| − D
        assert f_tracer_consensus_k(2.0, 1.0) == pytest.approx(abs(2.0) - 1.0)

    def test_negative_tcv(self):
        assert f_tracer_consensus_k(-3.0, 1.0) == pytest.approx(3.0 - 1.0)


class TestTickWisdom:
    def test_below_tip_returns_zero(self):
        assert f_tick_wisdom(tracer_at_n=0.3, tip_value=0.5, tracer_consensus_k=1.0) == 0.0

    def test_at_tip_computes(self):
        result = f_tick_wisdom(0.5, 0.5, 2.0)
        assert result == pytest.approx(0.5 / 2.0)

    def test_above_tip_computes(self):
        result = f_tick_wisdom(1.0, 0.5, 2.0)
        assert result == pytest.approx(1.0 / 2.0)

    def test_zero_k_no_crash(self):
        result = f_tick_wisdom(1.0, 0.5, 0.0)
        assert math.isfinite(result)


# ---------------------------------------------------------------------------
# Z-Space
# ---------------------------------------------------------------------------

class TestCairrnZSpace:
    def _call(self, **kwargs):
        defaults = dict(
            semantic_matrix_value=0.8,
            partial_deriv_1=0.5,
            activation=1.2,
            energy_cost=0.3,
            uncertainty=0.1,
            rizomic_distance=1.0,
            sigma_accumulator=0.9,
        )
        defaults.update(kwargs)
        return f_cairrn_z_space(**defaults)

    def test_output_finite(self):
        assert math.isfinite(self._call())

    def test_zero_partial_deriv_no_crash(self):
        assert math.isfinite(self._call(partial_deriv_1=0.0))

    def test_zero_rizomic_distance_no_crash(self):
        assert math.isfinite(self._call(rizomic_distance=0.0))

    def test_scales_with_sigma_accumulator(self):
        r1 = self._call(sigma_accumulator=1.0)
        r2 = self._call(sigma_accumulator=2.0)
        assert r2 == pytest.approx(r1 * 2.0)

    def test_formula_sign(self):
        """With positive inputs, the formula output sign depends on the numerator."""
        result = self._call(
            semantic_matrix_value=1.0, partial_deriv_1=1.0,
            activation=1.0, energy_cost=0.0, uncertainty=0.0,
            rizomic_distance=1.0, sigma_accumulator=1.0,
        )
        # (1/1) * (1 - 0 + 0) / 1 * 1 = 1.0
        assert result == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# F_TP_RAR family — catalog leaf used by Phi ranker
# ---------------------------------------------------------------------------


class TestTpRar:
    def test_zero_ma_no_crash(self):
        assert math.isfinite(f_tp_rar(0.8, 1.0, 0.05, 0.0, 0.0, conf_ma=0.0))

    def test_uncertainty_penalises(self):
        sure = f_tp_rar(0.8, 1.0, 0.05, 0.0, 0.0)
        unsure = f_tp_rar(0.8, 0.0, 0.05, 0.0, 0.0)
        assert sure > unsure


class TestSecondaryModelSelect:
    def test_below_optimal_is_one(self):
        assert f_secondary_model_select(0.2, 0.5) == 1.0

    def test_at_or_above_optimal_is_zero(self):
        assert f_secondary_model_select(0.5, 0.5) == 0.0
        assert f_secondary_model_select(0.9, 0.5) == 0.0


class TestScupCanonical:
    def test_basic(self):
        assert f_scup_canonical(1.0, 0.5, 0.0, 0.0) == pytest.approx(0.5)

    def test_pressure_and_uncertainty_dilute(self):
        clean = f_scup_canonical(1.0, 1.0, 0.0, 0.0)
        loaded = f_scup_canonical(1.0, 1.0, 1.0, 1.0)
        assert loaded < clean
        assert loaded == pytest.approx(1.0 / 3.0)
