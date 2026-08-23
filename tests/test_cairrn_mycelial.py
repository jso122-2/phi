"""
tests/test_cairrn_mycelial.py — unit tests for workers/cairrn/mycelial.py.

Covers all 18 pure mycelial formula functions:

Founding spec (Rationale: Mycelial Intelligence in DAWN, 2026-07-13):
  1.  demand()                   — D_i computation
  2.  nutrient_alloc()           — softmax budget distribution
  3.  metabolise()               — metabolic conversion + clamp
  4.  conductance()              — sigmoid edge conductance
  5.  passive_flow()             — diffusion flow
  6.  active_flow()              — bloom/starve transport
  7.  weight_update()            — Hebbian + decay + entropy delta
  8.  shimmer_decay()            — exponential edge degradation
  9.  growth_gate()              — 4-condition growth check
  10. autophagy_trigger()        — starvation threshold
  11. metabolite_value()         — nutrient released on autophagy
  12. absorb_metabolite()        — neighbour absorption + clamp
  13. cluster_fusion_efficiency() — fused efficiency bonus
  14. cluster_fission_out()      — hub energy → periphery

Named canonical formulas (config/formulas/formula_dictionary.yaml):
  15. f_hebbian_learning()       — F_HEBBIAN_LEARNING: Δw = η·a_i·a_j
  16. f_connection_decay()       — F_CONNECTION_DECAY: w·(1−decay_rate)
  17. f_spore_energy_decay()     — F_SPORE_ENERGY_DECAY: E·exp(−rate)
  18. f_adaptive_capacity()      — F_ADAPTIVE_CAPACITY: w_N·N+w_S·M+w_T·S+A
"""
from __future__ import annotations

import math

import pytest

from workers.cairrn.mycelial import (
    _ALPHA_HEBBIAN,
    _BASAL_COST,
    _BETA_DECAY,
    _CHI_W,
    _E_MAX,
    _ETA,
    _GAMMA,
    _KAPPA,
    _TAU_TICKS,
    _THETA_GROW,
    _THETA_PRUNE,
    _THETA_SIM,
    absorb_metabolite,
    active_flow,
    autophagy_trigger,
    cluster_fission_out,
    cluster_fusion_efficiency,
    conductance,
    demand,
    f_adaptive_capacity,
    f_connection_decay,
    f_hebbian_learning,
    f_spore_energy_decay,
    growth_gate,
    metabolise,
    metabolite_value,
    nutrient_alloc,
    passive_flow,
    shimmer_decay,
    weight_update,
)


# ---------------------------------------------------------------------------
# 1. demand
# ---------------------------------------------------------------------------

class TestDemand:
    def test_all_positive_inputs(self):
        d = demand(pressure=1.0, drift_align=1.0, recency=1.0, entropy=0.0)
        assert d == pytest.approx(0.40 + 0.25 + 0.20, rel=1e-9)

    def test_entropy_reduces_demand(self):
        low  = demand(1.0, 0.0, 0.0, 0.0)
        high = demand(1.0, 0.0, 0.0, 1.0)
        assert low > high

    def test_zero_inputs(self):
        assert demand(0.0, 0.0, 0.0, 0.0) == pytest.approx(0.0)

    def test_negative_drift_align(self):
        d = demand(pressure=0.5, drift_align=-1.0, recency=0.5, entropy=0.0)
        assert d < demand(pressure=0.5, drift_align=0.0, recency=0.5, entropy=0.0)

    def test_custom_weights(self):
        d = demand(1.0, 0.0, 0.0, 0.0, w_pressure=1.0, w_drift=0.0, w_recency=0.0, w_entropy=0.0)
        assert d == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# 2. nutrient_alloc
# ---------------------------------------------------------------------------

class TestNutrientAlloc:
    def test_sums_to_budget(self):
        demands = [1.0, 2.0, 3.0]
        allocs = nutrient_alloc(demands, budget=10.0)
        assert sum(allocs) == pytest.approx(10.0, rel=1e-9)

    def test_higher_demand_gets_more(self):
        allocs = nutrient_alloc([0.0, 5.0], budget=1.0)
        assert allocs[1] > allocs[0]

    def test_equal_demands_equal_share(self):
        allocs = nutrient_alloc([2.0, 2.0, 2.0], budget=3.0)
        for a in allocs:
            assert a == pytest.approx(1.0, rel=1e-9)

    def test_empty_returns_empty(self):
        assert nutrient_alloc([], budget=10.0) == []

    def test_single_node_gets_full_budget(self):
        allocs = nutrient_alloc([0.5], budget=7.0)
        assert allocs[0] == pytest.approx(7.0)

    def test_large_demand_spread_stable(self):
        # numerical stability: softmax with extreme values should not overflow
        allocs = nutrient_alloc([0.0, 1000.0], budget=1.0)
        assert allocs[1] == pytest.approx(1.0, rel=1e-6)

    def test_budget_zero(self):
        allocs = nutrient_alloc([1.0, 2.0], budget=0.0)
        assert sum(allocs) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# 3. metabolise
# ---------------------------------------------------------------------------

class TestMetabolise:
    def test_energy_increases_with_nutrients(self):
        e = metabolise(energy=0.5, nutrients=0.5)
        assert e > 0.5 - _BASAL_COST  # net gain

    def test_clamp_max(self):
        e = metabolise(energy=1.0, nutrients=100.0, e_max=1.0)
        assert e == pytest.approx(1.0)

    def test_clamp_min(self):
        e = metabolise(energy=0.0, nutrients=0.0, basal_cost=10.0)
        assert e == pytest.approx(0.0)

    def test_basal_cost_drains_energy(self):
        e = metabolise(energy=0.5, nutrients=0.0, basal_cost=0.1, eta=1.0)
        assert e == pytest.approx(0.4, rel=1e-9)

    def test_eta_scales_nutrient_gain(self):
        e_high = metabolise(0.3, 0.5, basal_cost=0.0, eta=1.0, e_max=2.0)
        e_low  = metabolise(0.3, 0.5, basal_cost=0.0, eta=0.5, e_max=2.0)
        assert e_high > e_low


# ---------------------------------------------------------------------------
# 4. conductance
# ---------------------------------------------------------------------------

class TestConductance:
    def test_zero_weight_gives_half(self):
        assert conductance(0.0) == pytest.approx(0.5, rel=1e-9)

    def test_large_positive_weight_approaches_one(self):
        assert conductance(1000.0) == pytest.approx(1.0, abs=1e-6)

    def test_large_negative_weight_approaches_zero(self):
        assert conductance(-1000.0) == pytest.approx(0.0, abs=1e-6)

    def test_output_strictly_between_zero_and_one(self):
        for w in [-10.0, -1.0, 0.0, 1.0, 10.0]:
            g = conductance(w)
            assert 0.0 < g < 1.0

    def test_kappa_scaling(self):
        g_small = conductance(5.0, kappa=0.01)
        g_large = conductance(5.0, kappa=1.0)
        assert g_large > g_small

    def test_default_kappa_matches_constant(self):
        import math
        expected = 1.0 / (1.0 + math.exp(-_KAPPA * 2.0))
        assert conductance(2.0) == pytest.approx(expected, rel=1e-12)


# ---------------------------------------------------------------------------
# 5. passive_flow
# ---------------------------------------------------------------------------

class TestPassiveFlow:
    def test_flows_from_high_to_low(self):
        # positive flow: i → j (energy_i > energy_j)
        f = passive_flow(energy_i=0.8, energy_j=0.2, weight_ij=5.0)
        assert f > 0.0

    def test_flows_from_low_to_high_is_negative(self):
        f = passive_flow(energy_i=0.2, energy_j=0.8, weight_ij=5.0)
        assert f < 0.0

    def test_equal_energies_zero_flow(self):
        f = passive_flow(energy_i=0.5, energy_j=0.5, weight_ij=5.0)
        assert f == pytest.approx(0.0, abs=1e-12)

    def test_higher_weight_more_flow(self):
        f_low  = passive_flow(0.8, 0.2, weight_ij=1.0)
        f_high = passive_flow(0.8, 0.2, weight_ij=20.0)
        assert f_high > f_low


# ---------------------------------------------------------------------------
# 6. active_flow
# ---------------------------------------------------------------------------

class TestActiveFlow:
    def test_positive_bloom_generates_flow(self):
        f = active_flow(energy_i=0.9, bloom_i=1.0, starve_j=0.0, weight_ij=5.0)
        assert f > 0.0

    def test_positive_starve_generates_flow(self):
        f = active_flow(energy_i=0.9, bloom_i=0.0, starve_j=1.0, weight_ij=5.0)
        assert f > 0.0

    def test_zero_energy_no_flow(self):
        f = active_flow(energy_i=0.0, bloom_i=1.0, starve_j=1.0, weight_ij=5.0)
        assert f == pytest.approx(0.0, abs=1e-12)

    def test_zero_signals_no_active_flow(self):
        f = active_flow(energy_i=0.9, bloom_i=0.0, starve_j=0.0, weight_ij=5.0)
        assert f == pytest.approx(0.0, abs=1e-12)

    def test_gamma_scales_flow(self):
        f_low  = active_flow(0.9, 1.0, 1.0, 5.0, gamma=0.1)
        f_high = active_flow(0.9, 1.0, 1.0, 5.0, gamma=1.0)
        assert f_high > f_low

    def test_output_always_non_negative(self):
        f = active_flow(energy_i=0.5, bloom_i=0.3, starve_j=0.2, weight_ij=3.0)
        assert f >= 0.0


# ---------------------------------------------------------------------------
# 7. weight_update
# ---------------------------------------------------------------------------

class TestWeightUpdate:
    def test_high_similarity_grows_weight(self):
        delta = weight_update(
            similarity_ij=1.0, reliability_ij=1.0,
            energy_i=1.0, energy_j=1.0,
            time_decay_ij=0.0, mean_entropy_ij=0.0,
        )
        assert delta > 0.0

    def test_high_decay_shrinks_weight(self):
        delta = weight_update(
            similarity_ij=0.0, reliability_ij=0.0,
            energy_i=0.0, energy_j=0.0,
            time_decay_ij=100.0, mean_entropy_ij=0.0,
        )
        assert delta < 0.0

    def test_entropy_reduces_delta(self):
        d_no_entropy = weight_update(0.5, 0.5, 0.5, 0.5, 0.0, 0.0)
        d_entropy    = weight_update(0.5, 0.5, 0.5, 0.5, 0.0, 1.0)
        assert d_no_entropy > d_entropy

    def test_zero_energy_kills_hebbian(self):
        delta = weight_update(
            similarity_ij=1.0, reliability_ij=1.0,
            energy_i=0.0, energy_j=0.0,
            time_decay_ij=0.0, mean_entropy_ij=0.0,
        )
        assert delta == pytest.approx(0.0, abs=1e-12)

    def test_geometric_mean_energy(self):
        import math
        sim, rel = 0.8, 0.9
        ei, ej = 0.6, 0.4
        expected_hebbian = _ALPHA_HEBBIAN * sim * rel * math.sqrt(ei * ej)
        delta = weight_update(sim, rel, ei, ej, 0.0, 0.0)
        assert delta == pytest.approx(expected_hebbian, rel=1e-9)


# ---------------------------------------------------------------------------
# 8. shimmer_decay
# ---------------------------------------------------------------------------

class TestShimmerDecay:
    def test_zero_steps_no_decay(self):
        assert shimmer_decay(1.0, 0.0) == pytest.approx(1.0)

    def test_weight_decreases_over_time(self):
        assert shimmer_decay(1.0, 10.0) < 1.0

    def test_negative_time_treated_as_zero(self):
        assert shimmer_decay(0.5, -5.0) == pytest.approx(0.5)

    def test_zero_weight_stays_zero(self):
        assert shimmer_decay(0.0, 100.0) == pytest.approx(0.0)

    def test_exponential_structure(self):
        import math
        rate = 0.03
        w = shimmer_decay(2.0, 5.0, decay_rate=rate)
        assert w == pytest.approx(2.0 * math.exp(-rate * 5.0), rel=1e-9)

    def test_large_time_approaches_zero(self):
        w = shimmer_decay(1.0, 1000.0)
        assert w < 1e-5


# ---------------------------------------------------------------------------
# 9. growth_gate
# ---------------------------------------------------------------------------

class TestGrowthGate:
    def test_all_pass(self):
        assert growth_gate(0.5, 0.5, True, True) is True

    def test_energy_too_low(self):
        assert growth_gate(0.0, 0.5, True, True) is False

    def test_similarity_too_low(self):
        assert growth_gate(0.5, 0.0, True, True) is False

    def test_temporal_fail(self):
        assert growth_gate(0.5, 0.5, False, True) is False

    def test_mood_fail(self):
        assert growth_gate(0.5, 0.5, True, False) is False

    def test_boundary_energy_excluded(self):
        # energy exactly at theta_grow is NOT > theta_grow → gate closed
        assert growth_gate(_THETA_GROW, 0.5, True, True) is False

    def test_boundary_energy_just_above(self):
        assert growth_gate(_THETA_GROW + 1e-9, 0.5, True, True) is True

    def test_custom_thresholds(self):
        assert growth_gate(0.1, 0.1, True, True, theta_grow=0.05, theta_sim=0.05) is True


# ---------------------------------------------------------------------------
# 10. autophagy_trigger
# ---------------------------------------------------------------------------

class TestAutophagyTrigger:
    def test_below_threshold_long_enough(self):
        assert autophagy_trigger(0.0, starved_ticks=_TAU_TICKS) is True

    def test_not_starved_long_enough(self):
        assert autophagy_trigger(0.0, starved_ticks=_TAU_TICKS - 1) is False

    def test_energy_above_threshold_no_trigger(self):
        assert autophagy_trigger(1.0, starved_ticks=1000) is False

    def test_exactly_at_threshold_no_trigger(self):
        # energy == theta_prune is NOT < theta_prune → no trigger
        assert autophagy_trigger(_THETA_PRUNE, starved_ticks=_TAU_TICKS) is False

    def test_just_below_threshold(self):
        assert autophagy_trigger(_THETA_PRUNE - 1e-9, starved_ticks=_TAU_TICKS) is True

    def test_custom_tau(self):
        assert autophagy_trigger(0.0, starved_ticks=2, tau_ticks=2) is True
        assert autophagy_trigger(0.0, starved_ticks=1, tau_ticks=2) is False


# ---------------------------------------------------------------------------
# 11. metabolite_value
# ---------------------------------------------------------------------------

class TestMetaboliteValue:
    def test_positive_output(self):
        assert metabolite_value(0.5, 1.0) > 0.0

    def test_zero_energy_still_emits(self):
        # history_factor > 0 means something is always emitted
        assert metabolite_value(0.0, 1.0) > 0.0

    def test_scales_with_energy(self):
        low  = metabolite_value(0.1, 1.0)
        high = metabolite_value(0.9, 1.0)
        assert high > low

    def test_nutrient_factor_scales_output(self):
        m1 = metabolite_value(0.5, 1.0, nutrient_factor=0.5)
        m2 = metabolite_value(0.5, 1.0, nutrient_factor=1.0)
        assert m2 == pytest.approx(m1 * 2.0)

    def test_exact_formula(self):
        e, h, nf = 0.4, 0.8, 0.6
        assert metabolite_value(e, h, nf) == pytest.approx((e + h) * nf)


# ---------------------------------------------------------------------------
# 12. absorb_metabolite
# ---------------------------------------------------------------------------

class TestAbsorbMetabolite:
    def test_energy_increases(self):
        e = absorb_metabolite(0.3, 0.5)
        assert e > 0.3

    def test_clamp_max(self):
        e = absorb_metabolite(0.9, 100.0, e_max=1.0)
        assert e == pytest.approx(1.0)

    def test_clamp_min(self):
        e = absorb_metabolite(0.0, 0.0)
        assert e == pytest.approx(0.0)

    def test_absorption_rate_scales(self):
        e_low  = absorb_metabolite(0.3, 1.0, absorption_rate=0.1, e_max=10.0)
        e_high = absorb_metabolite(0.3, 1.0, absorption_rate=0.9, e_max=10.0)
        assert e_high > e_low

    def test_exact_formula(self):
        e, m, r, emax = 0.3, 0.5, 0.2, 1.0
        expected = min(1.0, max(0.0, e + r * m))
        assert absorb_metabolite(e, m, r, emax) == pytest.approx(expected)


# ---------------------------------------------------------------------------
# 13. cluster_fusion_efficiency
# ---------------------------------------------------------------------------

class TestClusterFusionEfficiency:
    def test_fusion_increases_efficiency(self):
        e = cluster_fusion_efficiency(0.5, 2)
        assert e > 0.5

    def test_clamped_to_one(self):
        e = cluster_fusion_efficiency(0.9, 100)
        assert e == pytest.approx(1.0)

    def test_zero_base_efficiency(self):
        e = cluster_fusion_efficiency(0.0, 2)
        assert e > 0.0

    def test_one_node_still_gets_bonus(self):
        e = cluster_fusion_efficiency(0.5, 1)
        assert e > 0.5

    def test_more_nodes_more_efficiency(self):
        e2 = cluster_fusion_efficiency(0.3, 2)
        e5 = cluster_fusion_efficiency(0.3, 5)
        assert e5 >= e2


# ---------------------------------------------------------------------------
# 14. cluster_fission_out
# ---------------------------------------------------------------------------

class TestClusterFissionOut:
    def test_correct_number_of_shares(self):
        shares = cluster_fission_out(1.0, 4)
        assert len(shares) == 4

    def test_all_equal(self):
        shares = cluster_fission_out(1.0, 3)
        assert all(s == pytest.approx(shares[0]) for s in shares)

    def test_sum_equals_fission_amount(self):
        energy, rate = 0.8, 0.25
        shares = cluster_fission_out(energy, 5, fission_rate=rate)
        assert sum(shares) == pytest.approx(energy * rate, rel=1e-9)

    def test_zero_energy_zero_shares(self):
        shares = cluster_fission_out(0.0, 4)
        assert all(s == pytest.approx(0.0) for s in shares)

    def test_no_periphery_returns_empty(self):
        assert cluster_fission_out(1.0, 0) == []

    def test_negative_periphery_returns_empty(self):
        assert cluster_fission_out(1.0, -1) == []

    def test_fission_rate_scales_output(self):
        s_low  = sum(cluster_fission_out(1.0, 4, fission_rate=0.10))
        s_high = sum(cluster_fission_out(1.0, 4, fission_rate=0.50))
        assert s_high > s_low


# ---------------------------------------------------------------------------
# 15. f_hebbian_learning  (F_HEBBIAN_LEARNING)
# ---------------------------------------------------------------------------

class TestFHebbianLearning:
    def test_basic_product(self):
        assert f_hebbian_learning(eta=0.1, a_i=0.8, a_j=0.5) == pytest.approx(0.04)

    def test_zero_activation_i_yields_zero(self):
        assert f_hebbian_learning(0.5, 0.0, 0.9) == pytest.approx(0.0)

    def test_zero_activation_j_yields_zero(self):
        assert f_hebbian_learning(0.5, 0.9, 0.0) == pytest.approx(0.0)

    def test_scales_with_eta(self):
        d_low  = f_hebbian_learning(0.01, 1.0, 1.0)
        d_high = f_hebbian_learning(1.00, 1.0, 1.0)
        assert d_high > d_low

    def test_symmetric_activations(self):
        d_ab = f_hebbian_learning(0.3, 0.6, 0.4)
        d_ba = f_hebbian_learning(0.3, 0.4, 0.6)
        assert d_ab == pytest.approx(d_ba)

    def test_exact_formula(self):
        eta, ai, aj = 0.2, 0.7, 0.3
        assert f_hebbian_learning(eta, ai, aj) == pytest.approx(eta * ai * aj)


# ---------------------------------------------------------------------------
# 16. f_connection_decay  (F_CONNECTION_DECAY)
# ---------------------------------------------------------------------------

class TestFConnectionDecay:
    def test_zero_decay_unchanged(self):
        assert f_connection_decay(1.0, 0.0) == pytest.approx(1.0)

    def test_full_decay_to_zero(self):
        assert f_connection_decay(1.0, 1.0) == pytest.approx(0.0)

    def test_partial_decay(self):
        assert f_connection_decay(2.0, 0.25) == pytest.approx(1.5)

    def test_decay_rate_clamped_above_one(self):
        # decay_rate > 1 is clamped to 1 → strength zeroed
        assert f_connection_decay(5.0, 2.0) == pytest.approx(0.0)

    def test_decay_rate_clamped_below_zero(self):
        # decay_rate < 0 is clamped to 0 → no decay
        assert f_connection_decay(3.0, -0.5) == pytest.approx(3.0)

    def test_zero_strength_stays_zero(self):
        assert f_connection_decay(0.0, 0.5) == pytest.approx(0.0)

    def test_exact_formula(self):
        s, r = 4.0, 0.3
        assert f_connection_decay(s, r) == pytest.approx(s * (1.0 - r))


# ---------------------------------------------------------------------------
# 17. f_spore_energy_decay  (F_SPORE_ENERGY_DECAY)
# ---------------------------------------------------------------------------

class TestFSporeEnergyDecay:
    def test_zero_decay_rate_unchanged(self):
        assert f_spore_energy_decay(1.0, 0.0) == pytest.approx(1.0)

    def test_positive_decay_reduces_energy(self):
        assert f_spore_energy_decay(1.0, 0.5) < 1.0

    def test_zero_energy_stays_zero(self):
        assert f_spore_energy_decay(0.0, 1.0) == pytest.approx(0.0)

    def test_large_decay_approaches_zero(self):
        assert f_spore_energy_decay(1.0, 1000.0) < 1e-10

    def test_negative_decay_rate_clamped(self):
        # negative decay_rate treated as 0 → energy unchanged
        assert f_spore_energy_decay(0.8, -1.0) == pytest.approx(0.8)

    def test_exact_formula(self):
        import math
        e, r = 0.6, 0.4
        assert f_spore_energy_decay(e, r) == pytest.approx(e * math.exp(-r), rel=1e-9)

    def test_relationship_to_connection_decay(self):
        # For r ∈ (0, 1): exp(-r) > (1-r) by Taylor expansion.
        # Linear decay (f_connection_decay) is more aggressive per step than
        # exponential decay (f_spore_energy_decay) at the same rate value.
        r = 0.3
        spore = f_spore_energy_decay(1.0, r)
        conn  = f_connection_decay(1.0, r)
        assert spore > conn


# ---------------------------------------------------------------------------
# 18. f_adaptive_capacity  (F_ADAPTIVE_CAPACITY)
# ---------------------------------------------------------------------------

class TestFAdaptiveCapacity:
    def test_all_zero_inputs(self):
        assert f_adaptive_capacity(1.0, 0.0, 1.0, 0.0, 1.0, 0.0) == pytest.approx(0.0)

    def test_nutrient_headroom_scales(self):
        ac_low  = f_adaptive_capacity(0.5, 1.0, 0.0, 0.0, 0.0, 0.0)
        ac_high = f_adaptive_capacity(2.0, 1.0, 0.0, 0.0, 0.0, 0.0)
        assert ac_high > ac_low

    def test_shi_margin_adds_capacity(self):
        ac = f_adaptive_capacity(0.0, 0.0, 1.0, 0.5, 0.0, 0.0)
        assert ac == pytest.approx(0.5)

    def test_tracer_slack_adds_capacity(self):
        ac = f_adaptive_capacity(0.0, 0.0, 0.0, 0.0, 1.0, 0.3)
        assert ac == pytest.approx(0.3)

    def test_tag_set_a_bonus(self):
        ac_no_a = f_adaptive_capacity(1.0, 1.0, 0.0, 0.0, 0.0, 0.0)
        ac_a    = f_adaptive_capacity(1.0, 1.0, 0.0, 0.0, 0.0, 0.0, tag_set_a=0.5)
        assert ac_a == pytest.approx(ac_no_a + 0.5)

    def test_exact_formula(self):
        wn, n, ws, m, wt, s, a = 0.4, 0.6, 0.3, 0.2, 0.2, 0.5, 0.1
        expected = wn * n + ws * m + wt * s + a
        assert f_adaptive_capacity(wn, n, ws, m, wt, s, a) == pytest.approx(expected)

    def test_all_components_additive(self):
        ac_n = f_adaptive_capacity(1.0, 2.0, 0.0, 0.0, 0.0, 0.0)
        ac_s = f_adaptive_capacity(0.0, 0.0, 1.0, 2.0, 0.0, 0.0)
        ac_t = f_adaptive_capacity(0.0, 0.0, 0.0, 0.0, 1.0, 2.0)
        ac_all = f_adaptive_capacity(1.0, 2.0, 1.0, 2.0, 1.0, 2.0)
        assert ac_all == pytest.approx(ac_n + ac_s + ac_t)


# ---------------------------------------------------------------------------
# Import round-trip — package __init__.py must export everything
# ---------------------------------------------------------------------------

class TestPackageExports:
    def test_all_mycelial_symbols_importable_from_package(self):
        from workers.cairrn import (
            absorb_metabolite,
            active_flow,
            autophagy_trigger,
            cluster_fission_out,
            cluster_fusion_efficiency,
            conductance,
            demand,
            f_adaptive_capacity,
            f_connection_decay,
            f_hebbian_learning,
            f_spore_energy_decay,
            growth_gate,
            metabolise,
            metabolite_value,
            nutrient_alloc,
            passive_flow,
            shimmer_decay,
            weight_update,
        )
        assert callable(demand)
        assert callable(nutrient_alloc)
        assert callable(metabolise)
        assert callable(conductance)
        assert callable(passive_flow)
        assert callable(active_flow)
        assert callable(weight_update)
        assert callable(shimmer_decay)
        assert callable(growth_gate)
        assert callable(autophagy_trigger)
        assert callable(metabolite_value)
        assert callable(absorb_metabolite)
        assert callable(cluster_fusion_efficiency)
        assert callable(cluster_fission_out)
        assert callable(f_hebbian_learning)
        assert callable(f_connection_decay)
        assert callable(f_spore_energy_decay)
        assert callable(f_adaptive_capacity)

    def test_constants_importable(self):
        from workers.cairrn import (
            _ALPHA_HEBBIAN,
            _BASAL_COST,
            _BETA_DECAY,
            _CHI_W,
            _E_MAX,
            _ETA,
            _GAMMA,
            _KAPPA,
            _TAU_TICKS,
            _THETA_GROW,
            _THETA_PRUNE,
            _THETA_SIM,
        )
        assert _KAPPA == pytest.approx(0.15)
        assert 0.0 < _THETA_GROW < 1.0
        assert 0.0 < _THETA_SIM < 1.0
        assert 0.0 < _THETA_PRUNE < _THETA_GROW
        assert _TAU_TICKS >= 1
