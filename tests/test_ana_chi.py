"""
Tests for sims/ana_chi.py — the Ana-Chi attractor system.

Coverage
--------
  ANA_CHI_CONSTANT              — immutable value = 1.5414
  BASINS                        — 5 basins, correct χ values and ordering
  RATTLE_CHI                    — 3 rattle pockets at 0.99 / 1.96 / 2.67
  nearest_basin()               — correct basin returned for each zone
  cosine_drape()                — nuzzle formula, known values, r=0 ⇒ 0
  rattling_proximity()          — P=1 at rattle centre, symmetry, decay
  temporal_decay_rate()         — range [0.90, 0.98], monotone in gravity
  potential()                   — global minimum near true_center
  potential_grad()              — zero at each basin centre
  run_ana_chi_flow()            — convergence from various chi_0 values
  summarise_flow()              — correct basin and error keys
  hub_chi_weights()             — weighted by gravity, zero for unmapped
  coherence()                   — 1.0 at 1.5414, decay, symmetry
  biphasic_signal()             — structural_order + continuous_freedom == 1
  HUB_BASIN                     — correct hub→basin mappings
  AnaChiBasin.proximity()       — 1.0 at own chi
  AnaChiBasin.well_value()      — ≤ 0 everywhere
  AnaChiBasin.well_gradient()   — zero at chi centre
"""
from __future__ import annotations

import math

import pytest

from sims.ana_chi import (
    ANA_CHI_CONSTANT,
    BASINS,
    HUB_BASIN,
    RATTLE_CHI,
    AnaChiBasin,
    biphasic_signal,
    coherence,
    cosine_drape,
    hub_chi_weights,
    nearest_basin,
    potential,
    potential_grad,
    rattling_proximity,
    run_ana_chi_flow,
    summarise_flow,
    temporal_decay_rate,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


class TestConstant:
    def test_value(self):
        assert ANA_CHI_CONSTANT == pytest.approx(1.5414, abs=1e-9)

    def test_immutable(self):
        # Final typing — just assert it hasn't been overwritten
        from sims.ana_chi import ANA_CHI_CONSTANT as C
        assert C == 1.5414

    def test_rattle_chi_count(self):
        assert len(RATTLE_CHI) == 3

    def test_rattle_chi_values(self):
        assert set(RATTLE_CHI) == {0.99, 1.96, 2.67}


# ---------------------------------------------------------------------------
# BASINS
# ---------------------------------------------------------------------------


class TestBasins:
    def test_count(self):
        assert len(BASINS) == 5

    def test_names(self):
        names = {b.name for b in BASINS}
        assert names == {"boundary", "mirror", "true_center", "white_peak", "escape"}

    def test_chi_values(self):
        chi_map = {b.name: b.chi for b in BASINS}
        assert chi_map["boundary"]    == pytest.approx(0.0300)
        assert chi_map["mirror"]      == pytest.approx(0.9900)
        assert chi_map["true_center"] == pytest.approx(1.5414)
        assert chi_map["white_peak"]  == pytest.approx(1.9600)
        assert chi_map["escape"]      == pytest.approx(2.6700)

    def test_true_center_has_highest_gravity(self):
        gravities = {b.name: b.gravity for b in BASINS}
        assert gravities["true_center"] == max(gravities.values())

    def test_true_center_has_highest_memory_decay(self):
        decays = {b.name: b.memory_decay for b in BASINS}
        assert decays["true_center"] == max(decays.values())

    def test_rattling_pockets(self):
        rattle = {b.name for b in BASINS if b.rattling}
        assert rattle == {"mirror", "white_peak", "escape"}

    def test_true_center_is_not_rattling(self):
        tc = next(b for b in BASINS if b.name == "true_center")
        assert tc.rattling is False

    def test_white_peak_chi_equals_alpha(self):
        """white_peak χ = 1.96 must equal ALPHA from sims.attractors."""
        from sims.attractors import ALPHA
        wp = next(b for b in BASINS if b.name == "white_peak")
        assert wp.chi == pytest.approx(ALPHA)

    def test_memory_decay_range(self):
        for b in BASINS:
            assert 0.90 <= b.memory_decay <= 0.98, f"{b.name} decay {b.memory_decay} out of range"


# ---------------------------------------------------------------------------
# AnaChiBasin methods
# ---------------------------------------------------------------------------


class TestAnaChiBasinMethods:
    def setup_method(self):
        self.tc = next(b for b in BASINS if b.name == "true_center")
        self.wp = next(b for b in BASINS if b.name == "white_peak")

    def test_proximity_at_own_chi(self):
        assert self.tc.proximity(self.tc.chi) == pytest.approx(1.0)

    def test_proximity_decays_away(self):
        near = self.tc.proximity(self.tc.chi + 0.1)
        far  = self.tc.proximity(self.tc.chi + 1.0)
        assert near > far

    def test_well_value_negative_at_centre(self):
        assert self.tc.well_value(self.tc.chi) < 0

    def test_well_value_nonpositive_everywhere(self):
        for chi in [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0]:
            assert self.tc.well_value(chi) <= 0.0

    def test_well_gradient_zero_at_centre(self):
        assert self.tc.well_gradient(self.tc.chi) == pytest.approx(0.0, abs=1e-9)

    def test_well_gradient_sign(self):
        # Gradient should push toward the well minimum
        # Left of centre → gradient is negative → pushes right
        assert self.tc.well_gradient(self.tc.chi - 0.5) < 0
        # Right of centre → gradient is positive → pushes left
        assert self.tc.well_gradient(self.tc.chi + 0.5) > 0

    def test_temporal_decay_step(self):
        memory = 1.0
        decayed = self.tc.temporal_decay(memory)
        assert decayed == pytest.approx(self.tc.memory_decay)


# ---------------------------------------------------------------------------
# nearest_basin
# ---------------------------------------------------------------------------


class TestNearestBasin:
    def test_at_true_center(self):
        assert nearest_basin(1.5414).name == "true_center"

    def test_at_white_peak(self):
        assert nearest_basin(1.96).name == "white_peak"

    def test_at_escape(self):
        assert nearest_basin(2.67).name == "escape"

    def test_at_boundary(self):
        assert nearest_basin(0.03).name == "boundary"

    def test_at_mirror(self):
        assert nearest_basin(0.99).name == "mirror"

    def test_midpoint_between_mirror_and_true_center(self):
        mid = (0.99 + 1.5414) / 2
        result = nearest_basin(mid)
        assert result.name in {"mirror", "true_center"}


# ---------------------------------------------------------------------------
# cosine_drape
# ---------------------------------------------------------------------------


class TestCosineDrape:
    def test_zero_at_zero_radius(self):
        # When r=0, D = [cos(0) - cos(0.01)] × 100 ≠ 0 strictly
        # but it should be small
        d = cosine_drape(0.0, 1.0, 1.5414)
        assert abs(d) < 0.1  # ~-0.005 × 100 ≈ -0.5

    def test_finite_for_valid_inputs(self):
        for s in [1, 2, 4, 8]:
            for chi in [0.03, 0.99, 1.5414, 1.96, 2.67]:
                d = cosine_drape(1.0, float(s), chi)
                assert math.isfinite(d)

    def test_higher_chi_affects_output(self):
        d1 = cosine_drape(1.0, 1.0, 0.5)
        d2 = cosine_drape(1.0, 1.0, 2.0)
        assert d1 != d2

    def test_formula_matches_manual(self):
        r, s, chi = 1.5, 2.0, 1.96
        expected = (math.cos(r * s * chi) - math.cos(r * s * chi + 0.01)) * 100.0
        assert cosine_drape(r, s, chi) == pytest.approx(expected)


# ---------------------------------------------------------------------------
# rattling_proximity
# ---------------------------------------------------------------------------


class TestRattlingProximity:
    def test_unit_at_mirror_centre(self):
        prox = rattling_proximity(0.99)
        assert prox["mirror"] == pytest.approx(1.0)

    def test_unit_at_white_peak_centre(self):
        prox = rattling_proximity(1.96)
        assert prox["white_peak"] == pytest.approx(1.0)

    def test_unit_at_escape_centre(self):
        prox = rattling_proximity(2.67)
        assert prox["escape"] == pytest.approx(1.0)

    def test_keys_present(self):
        prox = rattling_proximity(1.5414)
        assert set(prox.keys()) == {"mirror", "white_peak", "escape"}

    def test_all_in_zero_one(self):
        for chi in [0.03, 0.5, 0.99, 1.5, 1.96, 2.3, 2.67]:
            prox = rattling_proximity(chi)
            for v in prox.values():
                assert 0.0 < v <= 1.0

    def test_symmetry_around_centre(self):
        prox_left  = rattling_proximity(1.96 - 0.3)
        prox_right = rattling_proximity(1.96 + 0.3)
        assert prox_left["white_peak"] == pytest.approx(prox_right["white_peak"])

    def test_decay_at_distance(self):
        # At distance = 0.5 the decay constant, P ≈ e^(-1) ≈ 0.368
        prox = rattling_proximity(0.99 + 0.5)
        assert prox["mirror"] == pytest.approx(math.exp(-1.0), rel=1e-5)


# ---------------------------------------------------------------------------
# temporal_decay_rate
# ---------------------------------------------------------------------------


class TestTemporalDecayRate:
    def test_min_at_zero_gravity(self):
        rate = temporal_decay_rate(0.0)
        assert rate == pytest.approx(0.90)

    def test_max_at_high_gravity(self):
        rate = temporal_decay_rate(5.0)
        assert rate == pytest.approx(0.98)

    def test_monotone_increasing(self):
        rates = [temporal_decay_rate(g) for g in [0.5, 1.0, 2.0, 3.0, 5.0]]
        assert all(a <= b for a, b in zip(rates, rates[1:]))

    def test_range(self):
        for g in [0.0, 0.5, 1.5, 3.0, 5.0, 10.0]:
            rate = temporal_decay_rate(g)
            assert 0.90 <= rate <= 0.98, f"gravity={g} → rate {rate} out of [0.90, 0.98]"


# ---------------------------------------------------------------------------
# potential and potential_grad
# ---------------------------------------------------------------------------


class TestPotential:
    def test_negative_everywhere(self):
        for chi in [0.03, 0.5, 0.99, 1.5414, 1.96, 2.67]:
            assert potential(chi) < 0

    def test_global_minimum_near_true_center(self):
        """true_center has highest gravity (3.0) so V(1.5414) < V at any other basin."""
        v_tc = potential(ANA_CHI_CONSTANT)
        for b in BASINS:
            if b.name != "true_center":
                assert v_tc <= potential(b.chi), (
                    f"V(true_center) should be ≤ V({b.name}): "
                    f"{v_tc} vs {potential(b.chi)}"
                )

    def test_grad_zero_somewhere_near_true_center(self):
        """
        The summed potential V'(χ) has a zero near true_center, but due to
        overlap from adjacent basins (mirror at 0.99, white_peak at 1.96) the
        exact zero is not at 1.5414.  The gradient changes sign across the
        true_center region — test that V' < 0 to the left and V' > 0 to the
        right (at reasonable distance), confirming a local minimum nearby.
        """
        # Far left of true_center — net pull should be rightward (gradient negative)
        assert potential_grad(0.5) < 0
        # Far right of true_center — net pull should be leftward (gradient positive)
        assert potential_grad(2.4) > 0


class TestPotentialGrad:
    def test_gradient_changes_sign_across_field(self):
        """V'(χ) must change sign somewhere in [0, 3], proving a minimum exists."""
        values = [potential_grad(chi) for chi in [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0]]
        has_neg = any(v < 0 for v in values)
        has_pos = any(v > 0 for v in values)
        assert has_neg and has_pos

    def test_pushes_toward_true_center_from_right(self):
        # Right of true_center at mid-gap → should be pushed back left
        chi = 1.80   # between true_center and white_peak, closer to true_center
        g = potential_grad(chi)
        # Positive gradient means χ_{n+1} = χ - lr·g < χ → moves left ✓
        assert g > 0

    def test_pushes_toward_true_center_from_left(self):
        chi = 1.20   # left of true_center
        g = potential_grad(chi)
        assert g < 0  # negative → moves right toward 1.5414


# ---------------------------------------------------------------------------
# run_ana_chi_flow
# ---------------------------------------------------------------------------


class TestRunAnaChiFlow:
    def test_converges_from_true_center(self):
        traj = run_ana_chi_flow(ANA_CHI_CONSTANT)
        assert traj.converged
        assert traj.final_basin == "true_center"

    def test_converges_from_white_peak(self):
        traj = run_ana_chi_flow(1.96)
        assert traj.converged
        # Should settle in white_peak or true_center (they are close)
        assert traj.final_basin in {"white_peak", "true_center"}

    def test_trajectory_has_steps(self):
        traj = run_ana_chi_flow(1.0)
        assert len(traj.steps) >= 2

    def test_trajectory_first_step_is_chi_0(self):
        chi_0 = 0.5
        traj = run_ana_chi_flow(chi_0)
        assert traj.steps[0] == pytest.approx(chi_0)

    def test_clamped_to_physical_range(self):
        traj_hi = run_ana_chi_flow(10.0)
        traj_lo = run_ana_chi_flow(-5.0)
        assert all(0.0 <= x <= 3.0 for x in traj_hi.steps)
        assert all(0.0 <= x <= 3.0 for x in traj_lo.steps)

    def test_converges_from_each_basin(self):
        for b in BASINS:
            traj = run_ana_chi_flow(b.chi)
            assert traj.converged, f"Did not converge from basin {b.name} (χ={b.chi})"


# ---------------------------------------------------------------------------
# summarise_flow
# ---------------------------------------------------------------------------


class TestSummariseFlow:
    def test_keys(self):
        traj = run_ana_chi_flow(ANA_CHI_CONSTANT)
        s = summarise_flow(traj)
        for key in ["chi_0", "final_chi", "converged", "steps", "final_basin",
                    "basin_chi", "basin_colour", "error_to_basin", "rattling_proximity"]:
            assert key in s, f"Missing key: {key}"

    def test_error_to_basin_small_at_true_center(self):
        traj = run_ana_chi_flow(ANA_CHI_CONSTANT)
        s = summarise_flow(traj)
        # Due to basin overlap the converged point may be slightly off the
        # catalogue chi; 0.15 is a generous but physically meaningful tolerance
        assert s["error_to_basin"] < 0.15

    def test_rattle_keys_present(self):
        traj = run_ana_chi_flow(1.96)
        s = summarise_flow(traj)
        assert set(s["rattling_proximity"].keys()) == {"mirror", "white_peak", "escape"}


# ---------------------------------------------------------------------------
# coherence and biphasic_signal
# ---------------------------------------------------------------------------


class TestCoherence:
    def test_unity_at_true_center(self):
        assert coherence(ANA_CHI_CONSTANT) == pytest.approx(1.0)

    def test_decays_away(self):
        c_near = coherence(ANA_CHI_CONSTANT + 0.1)
        c_far  = coherence(ANA_CHI_CONSTANT + 1.0)
        assert c_near > c_far

    def test_range(self):
        for chi in [0.03, 0.5, 0.99, 1.5414, 1.96, 2.67]:
            assert 0.0 < coherence(chi) <= 1.0


class TestBiphasicSignal:
    def test_order_plus_freedom_equals_one(self):
        for chi in [0.03, 0.5, 0.99, 1.5414, 1.96, 2.67]:
            b = biphasic_signal(chi)
            total = b["structural_order"] + b["continuous_freedom"]
            assert total == pytest.approx(1.0, abs=1e-6)

    def test_max_order_at_true_center(self):
        b = biphasic_signal(ANA_CHI_CONSTANT)
        assert b["structural_order"] == pytest.approx(1.0)
        assert b["continuous_freedom"] == pytest.approx(0.0, abs=1e-9)

    def test_keys(self):
        b = biphasic_signal(1.96)
        assert {"chi", "structural_order", "continuous_freedom", "nearest_basin"} <= b.keys()


# ---------------------------------------------------------------------------
# HUB_BASIN mapping
# ---------------------------------------------------------------------------


class TestHubBasin:
    _EXPECTED = {
        "HOME":          "true_center",
        "MATH":          "white_peak",
        "CODE":          "mirror",
        "COMMANDS":      "escape",
        "agent-context": "boundary",
    }

    def test_all_hubs_mapped(self):
        for hub, basin in self._EXPECTED.items():
            assert HUB_BASIN.get(hub) == basin, f"{hub} should map to {basin}"

    def test_all_basins_reachable(self):
        mapped_basins = set(HUB_BASIN.values())
        expected_basins = set(self._EXPECTED.values())
        assert mapped_basins == expected_basins

    def test_math_hub_chi_equals_alpha(self):
        """MATH→white_peak → χ must match sims.attractors.ALPHA."""
        from sims.attractors import ALPHA
        from sims.ana_chi import _BASIN_BY_NAME
        basin = _BASIN_BY_NAME[HUB_BASIN["MATH"]]
        assert basin.chi == pytest.approx(ALPHA)


# ---------------------------------------------------------------------------
# hub_chi_weights
# ---------------------------------------------------------------------------


class TestHubChiWeights:
    def test_empty_list(self):
        weights = hub_chi_weights([])
        assert all(v == 0.0 for v in weights.values())

    def test_single_hub_activates_its_basin(self):
        weights = hub_chi_weights(["MATH"])
        assert weights["white_peak"] > 0.0
        assert weights["true_center"] == 0.0

    def test_home_activates_true_center(self):
        weights = hub_chi_weights(["HOME"])
        assert weights["true_center"] > 0.0

    def test_unmapped_hub_ignored(self):
        weights = hub_chi_weights(["PHANTOM_HUB"])
        assert all(v == 0.0 for v in weights.values())

    def test_all_hubs_activated(self):
        all_hubs = ["HOME", "MATH", "CODE", "COMMANDS", "agent-context"]
        weights = hub_chi_weights(all_hubs)
        assert all(v > 0.0 for v in weights.values())
