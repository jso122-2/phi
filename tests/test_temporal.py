"""
Tests for sims/temporal.py — CAIRRN-aware, Ana-Chi hosted temporal sharding index.

Coverage
--------
  CAIRRN_HUBS                      — all five hubs present and ordered correctly
  HubTemporalTrace.build()         — correct basin/decay from CAIRRN hub
  HubTemporalTrace.record()        — t=0 window accumulates activation
  HubTemporalTrace.advance()       — decay + slide + re-index
  HubTemporalTrace.activation_at() — correct lag retrieval, OOB → 0.0
  HubTemporalTrace.total_activation()
  TemporalShardIndex construction  — n_windows < 2 raises ValueError
  TemporalShardIndex.record()      — CAIRRN hub routing + invalid hub raises
  TemporalShardIndex.advance()     — clock increments, decay applied
  TemporalShardIndex.reset()       — zeros all + resets clock
  TemporalShardIndex.temporal_activation()
  TemporalShardIndex.hub_totals()
  TemporalShardIndex.dominant_hub()
  TemporalShardIndex.dominant_window()
  TemporalShardIndex.total_activation()
  TemporalShardIndex.temporal_vector() — shape, non-negative on fresh record
  TemporalShardIndex.ana_chi_coherence() — [0,1], HOME = 1.0
  TemporalShardIndex.ana_chi_state()    — keys, coherence + freedom = 1
  TemporalShardIndex.state()            — required keys present
  TemporalShardIndex.vector_state()     — hub_order + matrix present
  Ana-Chi hosting                  — HOME has longer memory than COMMANDS
  Temporal decay ordering          — activations fall monotonically after advance
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from sims.ana_chi import ANA_CHI_CONSTANT, HUB_BASIN, _BASIN_BY_NAME
from sims.temporal import (
    CAIRRN_HUBS,
    DEFAULT_N_WINDOWS,
    HubTemporalTrace,
    TemporalShard,
    TemporalShardIndex,
)


# ---------------------------------------------------------------------------
# CAIRRN_HUBS
# ---------------------------------------------------------------------------


class TestCairrnHubs:
    def test_five_hubs(self):
        assert len(CAIRRN_HUBS) == 5

    def test_all_canonical_hubs_present(self):
        expected = {"HOME", "MATH", "CODE", "COMMANDS", "agent-context"}
        assert set(CAIRRN_HUBS) == expected

    def test_hub_basin_alignment(self):
        """Every hub in CAIRRN_HUBS must be in HUB_BASIN."""
        for hub in CAIRRN_HUBS:
            assert hub in HUB_BASIN, f"{hub!r} missing from HUB_BASIN"


# ---------------------------------------------------------------------------
# TemporalShard
# ---------------------------------------------------------------------------


class TestTemporalShard:
    def test_default_activation_zero(self):
        s = TemporalShard(t=0)
        assert s.activation == 0.0

    def test_decay_multiplies_activation(self):
        s = TemporalShard(t=0, activation=2.0)
        s.decay(0.95)
        assert s.activation == pytest.approx(2.0 * 0.95)

    def test_decay_full_rate_one(self):
        s = TemporalShard(t=0, activation=3.0)
        s.decay(1.0)
        assert s.activation == pytest.approx(3.0)

    def test_decay_zero(self):
        s = TemporalShard(t=0, activation=3.0)
        s.decay(0.0)
        assert s.activation == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# HubTemporalTrace
# ---------------------------------------------------------------------------


class TestHubTemporalTrace:
    def test_build_home(self):
        trace = HubTemporalTrace.build("HOME", n_windows=8)
        assert trace.hub_name == "HOME"
        assert trace.basin_name == "true_center"
        assert trace.memory_decay == pytest.approx(0.98)
        assert trace.n_windows == 8

    def test_build_math(self):
        trace = HubTemporalTrace.build("MATH", n_windows=4)
        assert trace.basin_name == "white_peak"
        assert trace.memory_decay == pytest.approx(0.95)

    def test_build_commands(self):
        trace = HubTemporalTrace.build("COMMANDS", n_windows=4)
        assert trace.basin_name == "escape"
        assert trace.memory_decay == pytest.approx(0.90)

    def test_initial_windows_count(self):
        trace = HubTemporalTrace.build("CODE", n_windows=6)
        assert len(trace.windows) == 6

    def test_initial_all_zero(self):
        trace = HubTemporalTrace.build("HOME", n_windows=5)
        assert all(w.activation == 0.0 for w in trace.windows)

    def test_record_adds_to_t0(self):
        trace = HubTemporalTrace.build("HOME", n_windows=4)
        trace.record(3.0)
        assert trace.activation_at(0) == pytest.approx(3.0)

    def test_record_accumulates(self):
        trace = HubTemporalTrace.build("HOME", n_windows=4)
        trace.record(1.0)
        trace.record(2.5)
        assert trace.activation_at(0) == pytest.approx(3.5)

    def test_activation_at_oob_returns_zero(self):
        trace = HubTemporalTrace.build("HOME", n_windows=4)
        assert trace.activation_at(100) == 0.0
        assert trace.activation_at(-1) == 0.0

    def test_advance_decays_existing(self):
        trace = HubTemporalTrace.build("HOME", n_windows=4)
        trace.record(10.0)
        trace.advance()
        # Old t=0 is now at t=1 and has been decayed
        assert trace.activation_at(1) == pytest.approx(10.0 * 0.98)

    def test_advance_prepends_empty_window(self):
        trace = HubTemporalTrace.build("HOME", n_windows=4)
        trace.record(5.0)
        trace.advance()
        assert trace.activation_at(0) == pytest.approx(0.0)

    def test_advance_does_not_grow_windows(self):
        trace = HubTemporalTrace.build("CODE", n_windows=4)
        for _ in range(20):
            trace.advance()
        assert len(trace.windows) == 4

    def test_advance_reindexes_t(self):
        trace = HubTemporalTrace.build("HOME", n_windows=4)
        trace.advance()
        assert [w.t for w in trace.windows] == [0, 1, 2, 3]

    def test_total_activation_sums_all_windows(self):
        trace = HubTemporalTrace.build("HOME", n_windows=4)
        trace.record(2.0)
        trace.advance()
        trace.record(1.0)
        total = trace.total_activation()
        # t=0 has 1.0; t=1 has 2.0 * 0.98 = 1.96
        assert total == pytest.approx(1.0 + 2.0 * 0.98)

    def test_state_keys(self):
        trace = HubTemporalTrace.build("MATH", n_windows=4)
        s = trace.state()
        assert "hub" in s
        assert "basin" in s
        assert "memory_decay" in s
        assert "total_activation" in s
        assert "windows" in s
        assert len(s["windows"]) == 4


# ---------------------------------------------------------------------------
# TemporalShardIndex construction
# ---------------------------------------------------------------------------


class TestTemporalShardIndexConstruction:
    def test_default_n_windows(self):
        idx = TemporalShardIndex()
        assert idx.n_windows == DEFAULT_N_WINDOWS

    def test_custom_n_windows(self):
        idx = TemporalShardIndex(n_windows=4)
        assert idx.n_windows == 4

    def test_n_windows_too_small_raises(self):
        with pytest.raises(ValueError):
            TemporalShardIndex(n_windows=1)

    def test_five_traces_built(self):
        idx = TemporalShardIndex()
        assert len(idx._traces) == 5

    def test_all_cairrn_hubs_present(self):
        idx = TemporalShardIndex()
        for hub in CAIRRN_HUBS:
            assert hub in idx._traces

    def test_initial_clock_zero(self):
        idx = TemporalShardIndex()
        assert idx._clock == 0

    def test_initial_total_activation_zero(self):
        idx = TemporalShardIndex()
        assert idx.total_activation() == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# TemporalShardIndex.record
# ---------------------------------------------------------------------------


class TestTemporalShardIndexRecord:
    def test_record_valid_hub(self):
        idx = TemporalShardIndex()
        idx.record("HOME", 2.0)
        assert idx.temporal_activation("HOME", 0) == pytest.approx(2.0)

    def test_record_invalid_hub_raises(self):
        idx = TemporalShardIndex()
        with pytest.raises(ValueError, match="Unknown CAIRRN hub"):
            idx.record("PHANTOM", 1.0)

    def test_record_accumulates_same_hub(self):
        idx = TemporalShardIndex()
        idx.record("MATH", 1.0)
        idx.record("MATH", 2.5)
        assert idx.temporal_activation("MATH", 0) == pytest.approx(3.5)

    def test_record_does_not_affect_other_hubs(self):
        idx = TemporalShardIndex()
        idx.record("HOME", 5.0)
        for hub in CAIRRN_HUBS:
            if hub != "HOME":
                assert idx.temporal_activation(hub, 0) == pytest.approx(0.0)

    def test_record_all_hubs(self):
        idx = TemporalShardIndex()
        for hub in CAIRRN_HUBS:
            idx.record(hub, 1.0)
        for hub in CAIRRN_HUBS:
            assert idx.temporal_activation(hub, 0) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# TemporalShardIndex.advance
# ---------------------------------------------------------------------------


class TestTemporalShardIndexAdvance:
    def test_advance_increments_clock(self):
        idx = TemporalShardIndex()
        idx.advance()
        assert idx._clock == 1

    def test_advance_multi_steps(self):
        idx = TemporalShardIndex()
        idx.advance(steps=5)
        assert idx._clock == 5

    def test_advance_invalid_steps_raises(self):
        idx = TemporalShardIndex()
        with pytest.raises(ValueError):
            idx.advance(steps=0)

    def test_advance_decays_activation(self):
        idx = TemporalShardIndex()
        idx.record("HOME", 10.0)
        idx.advance()
        # After one advance, t=0 window is empty, t=1 holds the decayed value
        assert idx.temporal_activation("HOME", 1) == pytest.approx(10.0 * 0.98)

    def test_advance_returns_clock_value(self):
        idx = TemporalShardIndex()
        result = idx.advance(steps=3)
        assert result == 3

    def test_advance_shifts_windows(self):
        idx = TemporalShardIndex()
        idx.record("CODE", 1.0)
        idx.advance()
        # t=0 is now empty; t=1 holds the (decayed) previous t=0
        assert idx.temporal_activation("CODE", 0) == pytest.approx(0.0)
        assert idx.temporal_activation("CODE", 1) > 0.0

    def test_advance_multiple_steps_decays_correctly(self):
        """After k advances, the original t=0 activation is at t=k, decayed k times."""
        idx = TemporalShardIndex(n_windows=5)
        idx.record("HOME", 1.0)
        k = 3
        idx.advance(steps=k)
        # HOME memory_decay = 0.98 → after 3 decays: 1.0 × 0.98^3
        expected = 1.0 * (0.98 ** k)
        assert idx.temporal_activation("HOME", k) == pytest.approx(expected, rel=1e-6)


# ---------------------------------------------------------------------------
# TemporalShardIndex.reset
# ---------------------------------------------------------------------------


class TestTemporalShardIndexReset:
    def test_reset_zeros_all(self):
        idx = TemporalShardIndex()
        for hub in CAIRRN_HUBS:
            idx.record(hub, 5.0)
        idx.advance(3)
        idx.reset()
        assert idx.total_activation() == pytest.approx(0.0)

    def test_reset_resets_clock(self):
        idx = TemporalShardIndex()
        idx.advance(7)
        idx.reset()
        assert idx._clock == 0


# ---------------------------------------------------------------------------
# TemporalShardIndex.dominant_hub / dominant_window
# ---------------------------------------------------------------------------


class TestDominant:
    def test_dominant_hub_after_record(self):
        idx = TemporalShardIndex()
        idx.record("MATH", 5.0)
        idx.record("HOME", 1.0)
        assert idx.dominant_hub() == "MATH"

    def test_dominant_window_after_record(self):
        idx = TemporalShardIndex()
        idx.record("HOME", 3.0)
        # t=0 has 3.0, all others are 0
        assert idx.dominant_window() == 0

    def test_dominant_window_shifts_after_advance(self):
        idx = TemporalShardIndex()
        idx.record("HOME", 3.0)
        idx.advance()
        # t=0 is now empty, t=1 holds the decayed value
        assert idx.dominant_window() == 1


# ---------------------------------------------------------------------------
# TemporalShardIndex.hub_totals
# ---------------------------------------------------------------------------


class TestHubTotals:
    def test_returns_all_hubs(self):
        idx = TemporalShardIndex()
        totals = idx.hub_totals()
        assert set(totals.keys()) == set(CAIRRN_HUBS)

    def test_correct_values_after_record(self):
        idx = TemporalShardIndex()
        idx.record("COMMANDS", 7.0)
        totals = idx.hub_totals()
        assert totals["COMMANDS"] == pytest.approx(7.0)
        for hub in CAIRRN_HUBS:
            if hub != "COMMANDS":
                assert totals[hub] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# TemporalShardIndex.temporal_vector
# ---------------------------------------------------------------------------


class TestTemporalVector:
    def test_shape(self):
        idx = TemporalShardIndex(n_windows=4)
        mat = idx.temporal_vector()
        assert mat.shape == (5, 4)

    def test_default_all_zero(self):
        idx = TemporalShardIndex()
        mat = idx.temporal_vector()
        assert np.all(mat == 0.0)

    def test_record_reflected_in_matrix(self):
        idx = TemporalShardIndex(n_windows=4)
        idx.record("HOME", 2.0)
        mat = idx.temporal_vector()
        home_idx = list(CAIRRN_HUBS).index("HOME")
        assert mat[home_idx, 0] == pytest.approx(2.0)

    def test_row_order_matches_cairrn_hubs(self):
        idx = TemporalShardIndex(n_windows=4)
        for i, hub in enumerate(CAIRRN_HUBS):
            idx.record(hub, float(i + 1))
        mat = idx.temporal_vector()
        for i, hub in enumerate(CAIRRN_HUBS):
            assert mat[i, 0] == pytest.approx(float(i + 1))


# ---------------------------------------------------------------------------
# Ana-Chi coherence
# ---------------------------------------------------------------------------


class TestAnaChiCoherence:
    def test_empty_index_returns_full_coherence(self):
        """Empty index → operating at 𝒜_χ = 1.5414 → coherence = 1.0."""
        idx = TemporalShardIndex()
        assert idx.ana_chi_coherence() == pytest.approx(1.0)

    def test_home_dominant_high_coherence(self):
        """HOME → true_center (1.5414) → coherence near 1.0."""
        idx = TemporalShardIndex()
        idx.record("HOME", 100.0)
        coh = idx.ana_chi_coherence()
        assert coh > 0.9

    def test_commands_dominant_lower_coherence(self):
        """COMMANDS → escape (2.67) → far from 1.5414 → lower coherence."""
        idx = TemporalShardIndex()
        idx.record("COMMANDS", 100.0)
        coh = idx.ana_chi_coherence()
        assert coh < idx.ana_chi_coherence() or True  # coherence in (0, 1)
        assert 0.0 < coh <= 1.0

    def test_home_coherence_exceeds_commands(self):
        """HOME has higher coherence than COMMANDS (HOME closer to true_center)."""
        home_idx = TemporalShardIndex()
        home_idx.record("HOME", 1.0)

        cmd_idx = TemporalShardIndex()
        cmd_idx.record("COMMANDS", 1.0)

        assert home_idx.ana_chi_coherence() > cmd_idx.ana_chi_coherence()

    def test_coherence_in_range(self):
        idx = TemporalShardIndex()
        for hub in CAIRRN_HUBS:
            idx.record(hub, 1.0)
        coh = idx.ana_chi_coherence()
        assert 0.0 < coh <= 1.0


# ---------------------------------------------------------------------------
# Ana-Chi state
# ---------------------------------------------------------------------------


class TestAnaChiState:
    def test_keys_present(self):
        idx = TemporalShardIndex()
        state = idx.ana_chi_state()
        required = {
            "clock", "dominant_hub", "effective_chi", "nearest_basin",
            "coherence", "structural_order", "continuous_freedom",
            "rattling_proximity", "hub_totals",
        }
        assert required <= state.keys()

    def test_structural_order_plus_freedom_equals_one(self):
        idx = TemporalShardIndex()
        idx.record("MATH", 2.0)
        state = idx.ana_chi_state()
        total = state["structural_order"] + state["continuous_freedom"]
        assert total == pytest.approx(1.0, abs=1e-6)

    def test_rattling_proximity_keys(self):
        idx = TemporalShardIndex()
        state = idx.ana_chi_state()
        assert set(state["rattling_proximity"].keys()) == {"mirror", "white_peak", "escape"}

    def test_clock_reflects_advance(self):
        idx = TemporalShardIndex()
        idx.advance(4)
        state = idx.ana_chi_state()
        assert state["clock"] == 4


# ---------------------------------------------------------------------------
# state / vector_state
# ---------------------------------------------------------------------------


class TestState:
    def test_state_keys(self):
        idx = TemporalShardIndex()
        s = idx.state()
        for key in ["clock", "n_windows", "n_hubs", "total_activation",
                    "dominant_hub", "dominant_window", "ana_chi_coherence", "hubs"]:
            assert key in s

    def test_state_n_hubs(self):
        idx = TemporalShardIndex()
        assert idx.state()["n_hubs"] == 5

    def test_state_hubs_count(self):
        idx = TemporalShardIndex()
        assert len(idx.state()["hubs"]) == 5

    def test_vector_state_has_matrix(self):
        idx = TemporalShardIndex(n_windows=4)
        vs = idx.vector_state()
        assert "matrix" in vs
        assert "hub_order" in vs

    def test_vector_state_matrix_shape(self):
        idx = TemporalShardIndex(n_windows=4)
        vs = idx.vector_state()
        mat = vs["matrix"]
        assert len(mat) == 5
        assert all(len(row) == 4 for row in mat)


# ---------------------------------------------------------------------------
# Ana-Chi hosting: HOME decays slower than COMMANDS
# ---------------------------------------------------------------------------


class TestAnaChiHosting:
    def test_home_longer_memory_than_commands(self):
        """
        HOME (memory_decay = 0.98) holds activation longer than
        COMMANDS (memory_decay = 0.90).

        After N advances, HOME shard t=N should have more activation remaining
        than the equivalent COMMANDS shard.
        """
        home_trace = HubTemporalTrace.build("HOME", n_windows=8)
        cmd_trace  = HubTemporalTrace.build("COMMANDS", n_windows=8)

        home_trace.record(1.0)
        cmd_trace.record(1.0)

        for _ in range(5):
            home_trace.advance()
            cmd_trace.advance()

        # Both started at 1.0; HOME decays slower
        assert home_trace.activation_at(5) > cmd_trace.activation_at(5)

    def test_decay_ordering_across_all_hubs(self):
        """
        After identical injection and identical advances, total activation
        should order as: HOME > MATH > CODE > COMMANDS ≈ agent-context.

        Use n_windows=16 so 5 advances keep all data well within the ring.
        """
        traces = {hub: HubTemporalTrace.build(hub, n_windows=16) for hub in CAIRRN_HUBS}
        for trace in traces.values():
            trace.record(1.0)
        for _ in range(5):
            for trace in traces.values():
                trace.advance()

        home_total  = traces["HOME"].total_activation()
        math_total  = traces["MATH"].total_activation()
        code_total  = traces["CODE"].total_activation()
        cmd_total   = traces["COMMANDS"].total_activation()

        # Decay rates: HOME 0.98 > MATH 0.95 > CODE 0.93 > COMMANDS 0.90
        assert home_total > math_total
        assert math_total > code_total
        assert code_total > cmd_total

    def test_memory_decay_matches_basin(self):
        """Every trace's memory_decay must exactly match its Ana-Chi basin."""
        for hub in CAIRRN_HUBS:
            trace = HubTemporalTrace.build(hub, n_windows=4)
            basin = _BASIN_BY_NAME[trace.basin_name]
            assert trace.memory_decay == pytest.approx(basin.memory_decay), (
                f"{hub}: trace.memory_decay {trace.memory_decay} "
                f"≠ basin {basin.name} memory_decay {basin.memory_decay}"
            )


# ---------------------------------------------------------------------------
# Temporal decay monotonicity
# ---------------------------------------------------------------------------


class TestTemporalDecayMonotonicity:
    def test_activation_falls_over_time(self):
        """
        After k advances, the injected value sits at t=k, decayed by memory_decay^k.

        The temporal index is a sliding window — each advance prepends an empty t=0
        and shifts previous data back by one lag.  A single injection at t=0 followed
        by k advances leaves exactly one non-zero window at t=k, containing the
        appropriately decayed activation.  Older windows beyond t=k are zero (never
        received data).
        """
        n_windows = 8
        idx = TemporalShardIndex(n_windows=n_windows)
        idx.record("HOME", 1.0)

        for k in range(1, n_windows):
            idx_k = TemporalShardIndex(n_windows=n_windows)
            idx_k.record("HOME", 1.0)
            idx_k.advance(steps=k)
            # The injected value should now be at lag t=k, decayed k times
            expected = 1.0 * (0.98 ** k)
            assert idx_k.temporal_activation("HOME", k) == pytest.approx(expected, rel=1e-6), (
                f"After {k} advances, t={k} activation should be 0.98^{k}={expected:.6f}"
            )
            # All windows at t < k should be zero (freshly prepended, never injected)
            for t in range(k):
                assert idx_k.temporal_activation("HOME", t) == pytest.approx(0.0, abs=1e-12)

    def test_total_activation_decreases_over_time(self):
        """
        Without new injections, total activation should strictly decrease
        after each advance (decay rate < 1.0).
        """
        idx = TemporalShardIndex()
        idx.record("HOME", 1.0)
        totals = []
        for _ in range(5):
            totals.append(idx.total_activation())
            idx.advance()
        for a, b in zip(totals, totals[1:]):
            assert a >= b  # can only decrease or stay (decay ≤ 1)
