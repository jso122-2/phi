"""
test_cairrn.py — direct (no MCP subprocess) CAIRRN layer tests.

Covers:
  Layer 1  — Ana-Chi basin modulation
  Layer 2  — neg_exp sharding
  Layer 3  — coherence enforcement + re-route
  Layer 4  — Active -Z scoring (ZScore, z_coherence, z_shard)
  Batch    — CAIRRNBatch, shard_summary, z_active_runs
  Index    — temporal index update on inject
"""

import math
import pytest

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------
from workers.cairrn import (
    CAIRRNBatch,
    CAIRRNResult,
    CAIRRNWorker,
    DesktopFormulaInputs,
    ZScore,
    compute_z_score,
    neg_exp_shard,
    spawn_hub_worker,
    _COHERENCE_THRESHOLD,
    _COHERENCE_SIGMA,
    NEG_EXP_FIXED_POINT,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ALL_HUBS = ("HOME", "MATH", "CODE", "COMMANDS", "agent-context")

# Expected Ana-Chi basin / gravity mapping
HUB_GRAVITY = {
    "HOME":          3.0,
    "MATH":          2.0,
    "CODE":          1.5,
    "COMMANDS":      1.0,
    "agent-context": 0.5,
}

Z_INPUTS_FULL = dict(
    semantic_matrix_value=0.8,
    partial_deriv_1=0.5,
    z_activation=1.2,
    energy_cost=0.3,          # mapped from z_energy_cost in MCP layer
    z_uncertainty=0.1,
    rizomic_distance=1.0,
    sigma_accumulator=0.9,
)


def run_hub(hub: str, metric: float = 1.0, desktop: DesktopFormulaInputs | None = None):
    w = spawn_hub_worker(hub, fn=lambda: metric, desktop_inputs=desktop)
    w.run()
    return w._cairrn_log[-1]


# ---------------------------------------------------------------------------
# Layer 1 — Ana-Chi basin modulation
# ---------------------------------------------------------------------------

class TestLayer1Modulation:
    def test_modulation_home(self):
        r = run_hub("HOME", metric=0.8)
        expected = round(0.8 * HUB_GRAVITY["HOME"], 8)
        assert abs(r.modulation.modulated_metric - expected) < 1e-5, (
            f"HOME modulated_metric={r.modulation.modulated_metric} expected={expected}"
        )

    @pytest.mark.parametrize("hub", ALL_HUBS)
    def test_modulation_all_hubs_positive(self, hub):
        r = run_hub(hub, metric=1.0)
        assert r.modulation.modulated_metric > 0, f"{hub}: modulated_metric <= 0"

    @pytest.mark.parametrize("hub", ALL_HUBS)
    def test_to_dict_has_modulation_fields(self, hub):
        d = run_hub(hub, metric=1.0).to_dict()
        for field in ("hub", "basin", "chi", "modulated_metric", "gravity"):
            assert field in d, f"{hub}: missing field '{field}'"


# ---------------------------------------------------------------------------
# Layer 2 — neg_exp sharding
# ---------------------------------------------------------------------------

class TestLayer2Sharding:
    @pytest.mark.parametrize("hub", ALL_HUBS)
    def test_natural_shard_in_range(self, hub):
        r = run_hub(hub, metric=1.0)
        d = r.to_dict()
        shard = d["natural_shard"]
        assert 0 <= shard <= 7, f"{hub}: natural_shard={shard} out of range"

    def test_shard_ordering(self):
        """agent-context (lowest chi) → smallest shard; COMMANDS (highest chi) → largest."""
        shard_ac  = run_hub("agent-context", 1.0).to_dict()["natural_shard"]
        shard_cmd = run_hub("COMMANDS",      1.0).to_dict()["natural_shard"]
        assert shard_ac < shard_cmd, (
            f"Expected agent-context ({shard_ac}) < COMMANDS ({shard_cmd})"
        )

    def test_neg_exp_fixed_point(self):
        assert abs(NEG_EXP_FIXED_POINT - (-0.5671432904097838)) < 1e-10

    def test_neg_exp_one_step_present(self):
        d = run_hub("HOME", 1.0).to_dict()
        assert "neg_exp_one_step" in d


# ---------------------------------------------------------------------------
# Layer 3 — coherence enforcement
# ---------------------------------------------------------------------------

class TestLayer3Coherence:
    @pytest.mark.parametrize("hub", ALL_HUBS)
    def test_coherence_in_range(self, hub):
        d = run_hub(hub, 1.0).to_dict()
        coh = d["coherence"]
        assert 0.0 <= coh <= 1.0, f"{hub}: coherence={coh} out of range"

    @pytest.mark.parametrize("hub", ALL_HUBS)
    def test_ana_chi_coherence_present(self, hub):
        d = run_hub(hub, 1.0).to_dict()
        assert "ana_chi_coherence" in d, f"{hub}: ana_chi_coherence missing from to_dict()"

    @pytest.mark.parametrize("hub", ALL_HUBS)
    def test_ana_chi_coherence_in_range(self, hub):
        d = run_hub(hub, 1.0).to_dict()
        acc = d["ana_chi_coherence"]
        assert 0.0 <= acc <= 1.0, f"{hub}: ana_chi_coherence={acc} out of range"

    def test_home_ana_chi_coherence_is_one(self):
        """HOME is true_center (χ = 𝒜_χ) — structural order must be 1.0."""
        d = run_hub("HOME", 1.0).to_dict()
        assert d["ana_chi_coherence"] == pytest.approx(1.0, abs=1e-6)

    def test_commands_ana_chi_coherence_low(self):
        """COMMANDS (escape χ = 2.67) is far from equilibrium — structural order < 0.1."""
        d = run_hub("COMMANDS", 1.0).to_dict()
        assert d["ana_chi_coherence"] < 0.10, (
            f"COMMANDS ana_chi_coherence={d['ana_chi_coherence']:.4f} should be < 0.10"
        )

    def test_agent_context_routing_coherent_but_structurally_low(self):
        """
        agent-context routing coherence (neg_exp) passes gate but
        Ana-Chi structural order is near-zero — the boundary inversion.
        """
        r = run_hub("agent-context", 1.0)
        assert r.coherence.coherent is True,   "agent-context should pass routing gate"
        assert r.coherence.ana_chi_coherence < 0.10, (
            f"agent-context structural order={r.coherence.ana_chi_coherence:.4f} should be < 0.10"
        )

    @pytest.mark.parametrize("hub", ALL_HUBS)
    def test_re_routed_field_present(self, hub):
        r = run_hub(hub, 1.0)
        assert hasattr(r, "re_routed"), f"{hub}: re_routed attribute missing"
        assert isinstance(r.re_routed, bool)

    @pytest.mark.parametrize("hub", ALL_HUBS)
    def test_coherent_consistent_with_threshold(self, hub):
        r = run_hub(hub, 1.0)
        d = r.to_dict()
        # Use the exact CoherenceResult score (not the rounded to_dict() value) to
        # match how `coherent` is computed — HOME sits at exp(-W(1))=W(1) exactly.
        exact_coh = r.coherence.coherence
        coherent  = d["coherent"]
        if exact_coh >= _COHERENCE_THRESHOLD:
            assert coherent is True,  f"{hub}: coh={exact_coh:.6f} >= threshold but coherent=False"
        else:
            assert coherent is False, f"{hub}: coh={exact_coh:.6f} < threshold but coherent=True"


# ---------------------------------------------------------------------------
# Layer 4 — Active -Z scoring
# ---------------------------------------------------------------------------

class TestLayer4ZScoring:
    def _z_dfi(self):
        return DesktopFormulaInputs(**Z_INPUTS_FULL)

    def test_z_score_none_without_inputs(self):
        r = run_hub("HOME", 1.0, desktop=None)
        assert r.z_score is None, "z_score should be None without Z inputs"

    def test_z_score_active_with_inputs(self):
        r = run_hub("HOME", 1.0, desktop=self._z_dfi())
        assert r.z_score is not None, "z_score should be active with full Z inputs"
        assert r.z_score.z_active is True

    def test_z_score_fields(self):
        z = run_hub("HOME", 1.0, desktop=self._z_dfi()).z_score
        assert isinstance(z.neg_z, float)
        assert 0 <= z.z_shard <= 7
        assert 0.0 <= z.z_coherence <= 1.0
        assert isinstance(z.z_coherent, bool)

    def test_z_coherence_consistent_with_threshold(self):
        z = run_hub("HOME", 1.0, desktop=self._z_dfi()).z_score
        if z.z_coherence >= _COHERENCE_THRESHOLD:
            assert z.z_coherent is True
        else:
            assert z.z_coherent is False

    def test_to_dict_exposes_z_fields(self):
        d = run_hub("MATH", 1.0, desktop=self._z_dfi()).to_dict()
        for key in ("z_active", "neg_z", "z_shard", "z_coherence", "z_coherent"):
            assert key in d, f"to_dict missing '{key}'"

    def test_to_dict_no_z_fields_without_inputs(self):
        d = run_hub("MATH", 1.0, desktop=None).to_dict()
        for key in ("z_active", "neg_z", "z_shard", "z_coherence", "z_coherent"):
            assert key not in d, f"to_dict should NOT have '{key}' without Z inputs"

    def test_compute_z_score_standalone(self):
        z = compute_z_score(
            semantic_matrix_value=0.8,
            partial_deriv_1=0.5,
            activation=1.2,
            energy_cost=0.3,
            uncertainty=0.1,
            rizomic_distance=1.0,
            sigma_accumulator=0.9,
            coherence_threshold=_COHERENCE_THRESHOLD,
        )
        assert isinstance(z, ZScore)
        assert isinstance(z.neg_z, float)
        assert 0 <= z.z_shard <= 7
        assert 0.0 <= z.z_coherence <= 1.0

    @pytest.mark.parametrize("hub", ALL_HUBS)
    def test_z_scoring_all_hubs(self, hub):
        r = run_hub(hub, 1.0, desktop=self._z_dfi())
        assert r.z_score is not None, f"{hub}: z_score should be active"
        assert 0 <= r.z_score.z_shard <= 7


# ---------------------------------------------------------------------------
# Batch — CAIRRNBatch
# ---------------------------------------------------------------------------

class TestCAIRRNBatch:
    def test_batch_runs_all_hubs(self):
        b = CAIRRNBatch(fn=lambda: 1.0, desktop_inputs=None)
        results = b.run_all()
        assert set(results.keys()) == set(ALL_HUBS)

    @pytest.mark.parametrize("hub", ALL_HUBS)
    def test_batch_result_has_cairrn_key(self, hub):
        b = CAIRRNBatch(fn=lambda: 1.0, desktop_inputs=None)
        results = b.run_all()
        wr = results[hub]
        assert wr.value is not None, f"{hub}: worker result value is None"
        assert "cairrn" in wr.value, f"{hub}: 'cairrn' key missing from result"

    def test_shard_summary_keys(self):
        b = CAIRRNBatch(fn=lambda: 1.0, desktop_inputs=None)
        b.run_all()
        summary = b.summary()
        assert set(summary.keys()) == set(ALL_HUBS)

    @pytest.mark.parametrize("hub", ALL_HUBS)
    def test_shard_summary_has_required_fields(self, hub):
        b = CAIRRNBatch(fn=lambda: 1.0, desktop_inputs=None)
        b.run_all()
        s = b.summary()[hub]
        for field in ("runs", "hub", "target_shard", "natural_shard", "mean_coherence", "fixed_point"):
            assert field in s, f"{hub} shard_summary missing '{field}'"

    def test_batch_z_active_runs(self):
        dfi = DesktopFormulaInputs(**Z_INPUTS_FULL)
        b = CAIRRNBatch(fn=lambda: 1.0, desktop_inputs=dfi)
        b.run_all()
        summary = b.summary()
        for hub in ALL_HUBS:
            s = summary[hub]
            assert "z_active_runs" in s, f"{hub}: z_active_runs missing from shard_summary"
            assert s["z_active_runs"] >= 1, f"{hub}: z_active_runs={s['z_active_runs']}"


# ---------------------------------------------------------------------------
# Injection target — effective hub (post-reroute) used by MCP
# ---------------------------------------------------------------------------

class TestRerouteTarget:
    def test_requested_hub_in_to_dict(self):
        """to_dict must carry 're_routed' and 're_route_reason' to surface injection decision."""
        d = run_hub("HOME", 1.0).to_dict()
        assert "re_routed" in d
        assert "re_route_reason" in d

    def test_reroute_uses_home_when_incoherent(self):
        """
        If coherence < threshold the worker must set re_routed=True and hub != original.
        Force this by patching measure_coherence to return coherence=0.
        """
        import workers.cairrn as _c

        orig = _c.measure_coherence

        def _force_low(signal):
            result = orig(signal)
            from dataclasses import replace
            return replace(result, coherence=0.0, coherent=False)

        try:
            _c.measure_coherence = _force_low  # type: ignore[assignment]
            r = run_hub("CODE", 1.0)
            assert r.re_routed is True, (
                f"Expected re_routed=True with forced coherence=0, got False"
            )
            assert r.hub != "CODE", f"hub should differ from 'CODE' when re-routed: {r.hub}"
        finally:
            _c.measure_coherence = orig
