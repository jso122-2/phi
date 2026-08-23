"""
tests/test_cairrn_desktop.py — unit tests for workers/cairrn/desktop.py.

Covers:
  - DesktopFormulaInputs defaults (all None)
  - DesktopFormulaOutputs.to_dict() only returns non-None values
  - run_desktop_formulas: empty inputs → all outputs None
  - run_desktop_formulas: full Z-space inputs → neg_z computed
  - run_desktop_formulas: selective inputs → only matching outputs set
  - Dependency chain: forecast_score requires constraint_var to be computable
  - Dependency chain: tick_wisdom requires tracer_consensus_k to be computable
"""
from __future__ import annotations

import math

import pytest

from workers.cairrn.desktop import (
    DesktopFormulaInputs,
    DesktopFormulaOutputs,
    run_desktop_formulas,
)


# ---------------------------------------------------------------------------
# DesktopFormulaInputs defaults
# ---------------------------------------------------------------------------

class TestDesktopFormulaInputsDefaults:
    def test_all_fields_default_none(self):
        inp = DesktopFormulaInputs()
        for field_name, val in inp.__dict__.items():
            assert val is None, f"Field {field_name!r} expected None, got {val!r}"

    def test_selective_assignment(self):
        inp = DesktopFormulaInputs(confidence=0.8, SHI=1.0)
        assert inp.confidence == 0.8
        assert inp.SHI == 1.0
        assert inp.pressure is None


# ---------------------------------------------------------------------------
# DesktopFormulaOutputs
# ---------------------------------------------------------------------------

class TestDesktopFormulaOutputs:
    def test_all_fields_default_none(self):
        out = DesktopFormulaOutputs()
        for field_name, val in out.__dict__.items():
            assert val is None, f"Output field {field_name!r} expected None, got {val!r}"

    def test_to_dict_empty_when_all_none(self):
        assert DesktopFormulaOutputs().to_dict() == {}

    def test_to_dict_only_set_values(self):
        out = DesktopFormulaOutputs(constraint_var=1.5, neg_z=-0.3)
        d = out.to_dict()
        assert set(d.keys()) == {"constraint_var", "neg_z"}
        assert d["constraint_var"] == pytest.approx(1.5)
        assert d["neg_z"] == pytest.approx(-0.3)

    def test_to_dict_excludes_none(self):
        out = DesktopFormulaOutputs(forecast_score=None, height_node=2.0)
        d = out.to_dict()
        assert "forecast_score" not in d
        assert "height_node" in d


# ---------------------------------------------------------------------------
# run_desktop_formulas — empty inputs
# ---------------------------------------------------------------------------

class TestRunDesktopEmpty:
    def test_empty_inputs_all_none(self):
        out = run_desktop_formulas(DesktopFormulaInputs())
        assert isinstance(out, DesktopFormulaOutputs)
        for field_name, val in out.__dict__.items():
            assert val is None, f"Expected None for {field_name!r}, got {val!r}"

    def test_empty_returns_desktopformulaoutputs(self):
        assert isinstance(run_desktop_formulas(DesktopFormulaInputs()), DesktopFormulaOutputs)


# ---------------------------------------------------------------------------
# run_desktop_formulas — Z-space
# ---------------------------------------------------------------------------

class TestRunDesktopZSpace:
    def _z_inputs(self) -> DesktopFormulaInputs:
        return DesktopFormulaInputs(
            semantic_matrix_value=0.8,
            partial_deriv_1=0.5,
            z_activation=1.2,
            energy_cost=0.3,
            z_uncertainty=0.1,
            rizomic_distance=1.0,
            sigma_accumulator=0.9,
        )

    def test_neg_z_computed(self):
        out = run_desktop_formulas(self._z_inputs())
        assert out.neg_z is not None
        assert math.isfinite(out.neg_z)

    def test_non_z_outputs_none_without_inputs(self):
        """Z-space inputs alone must not trigger other formula outputs."""
        out = run_desktop_formulas(self._z_inputs())
        assert out.constraint_var is None
        assert out.energy_weighted is None
        assert out.scope_nav is None


# ---------------------------------------------------------------------------
# run_desktop_formulas — constraint var + forecast score dependency chain
# ---------------------------------------------------------------------------

class TestRunDesktopConstraintChain:
    def test_constraint_var_computed(self):
        inp = DesktopFormulaInputs(likelihood=0.6, possibility=0.4, opportunity_cost=0.1)
        out = run_desktop_formulas(inp)
        assert out.constraint_var is not None
        assert math.isfinite(out.constraint_var)

    def test_forecast_score_needs_constraint_var(self):
        """forecast_score must be None without the constraint var inputs."""
        inp = DesktopFormulaInputs(
            forecast_result=0.8, temporal_validator=1.0, energy_available=1.0
        )
        out = run_desktop_formulas(inp)
        assert out.forecast_score is None

    def test_forecast_score_computed_with_full_chain(self):
        inp = DesktopFormulaInputs(
            likelihood=0.6, possibility=0.4, opportunity_cost=0.1,
            forecast_result=0.8, temporal_validator=1.0, energy_available=1.0,
        )
        out = run_desktop_formulas(inp)
        assert out.constraint_var is not None
        assert out.forecast_score is not None
        assert math.isfinite(out.forecast_score)


# ---------------------------------------------------------------------------
# run_desktop_formulas — tracer_consensus_k + tick_wisdom chain
# ---------------------------------------------------------------------------

class TestRunDesktopTickWisdomChain:
    def test_tracer_consensus_k_computed(self):
        inp = DesktopFormulaInputs(tracer_consensus_value=2.0, SHI=0.5)
        out = run_desktop_formulas(inp)
        assert out.tracer_consensus_k is not None

    def test_tick_wisdom_needs_k_and_tracer_n(self):
        """tick_wisdom is None without tracer_at_n / tip_value."""
        inp = DesktopFormulaInputs(tracer_consensus_value=2.0, SHI=0.5)
        out = run_desktop_formulas(inp)
        assert out.tick_wisdom is None

    def test_tick_wisdom_computed_with_full_chain(self):
        inp = DesktopFormulaInputs(
            tracer_consensus_value=2.0, SHI=0.5,
            tracer_at_n=1.0, tip_value=0.5,
        )
        out = run_desktop_formulas(inp)
        assert out.tracer_consensus_k is not None
        assert out.tick_wisdom is not None
        assert math.isfinite(out.tick_wisdom)


# ---------------------------------------------------------------------------
# run_desktop_formulas — cairrn composite
# ---------------------------------------------------------------------------

class TestRunDesktopComposite:
    def test_composite_computed(self):
        inp = DesktopFormulaInputs(
            confidence=0.8, scope=0.5, dawn_data=0.6,
            energy_cost=0.3, tick_interval=5,
        )
        out = run_desktop_formulas(inp)
        assert out.cairrn_composite is not None
        assert math.isfinite(out.cairrn_composite)

    def test_composite_none_without_all_inputs(self):
        inp = DesktopFormulaInputs(confidence=0.8, scope=0.5)
        out = run_desktop_formulas(inp)
        assert out.cairrn_composite is None


# ---------------------------------------------------------------------------
# run_desktop_formulas — energy weighted
# ---------------------------------------------------------------------------

class TestRunDesktopEnergyWeighted:
    def test_energy_weighted_computed(self):
        inp = DesktopFormulaInputs(
            energies=[1.0, 2.0],
            desirability_costs=[0.5, 0.5],
            resources=2.0,
            dist_weighted_times=[1.0, 1.0],
            positive_normalisation=1.0,
        )
        out = run_desktop_formulas(inp)
        assert out.energy_weighted is not None
        assert out.energy_weighted >= 0.0

    def test_mismatched_list_lengths_skipped(self):
        """Lists of different length must not compute (skipped by guard)."""
        inp = DesktopFormulaInputs(
            energies=[1.0, 2.0],
            desirability_costs=[0.5],       # length mismatch
            resources=2.0,
            dist_weighted_times=[1.0, 1.0],
            positive_normalisation=1.0,
        )
        out = run_desktop_formulas(inp)
        assert out.energy_weighted is None
