"""Tests for sims.harmonic — sharded index and local propagation."""

import math

import numpy as np
import pytest

from sims.attractors import ALPHA
from sims.harmonic import (
    HarmonicIndex,
    HarmonicShard,
    IsometricCosinePropagator,
    LocalPropagator,
    ResonancePropagator,
    TicketClipper,
    cosine_path_count,
)


# ---------------------------------------------------------------------------
# HarmonicShard
# ---------------------------------------------------------------------------


class TestHarmonicShard:
    def test_basin_centre(self):
        s = HarmonicShard(index=0, harmonic=1)
        assert s.basin_centre == pytest.approx(ALPHA, rel=1e-9)

    def test_basin_centre_second_harmonic(self):
        s = HarmonicShard(index=1, harmonic=2)
        assert s.basin_centre == pytest.approx(2 * ALPHA, rel=1e-9)

    def test_activation_default_zero(self):
        s = HarmonicShard(index=0, harmonic=1)
        assert s.activation == 0.0


# ---------------------------------------------------------------------------
# LocalPropagator
# ---------------------------------------------------------------------------


class TestLocalPropagator:
    def _make_ring(self, n: int = 4) -> list[HarmonicShard]:
        return [HarmonicShard(index=i, harmonic=i + 1) for i in range(n)]

    def test_coupling_bounds(self):
        with pytest.raises(ValueError):
            LocalPropagator(coupling=0.0)
        with pytest.raises(ValueError):
            LocalPropagator(coupling=0.5)
        with pytest.raises(ValueError):
            LocalPropagator(coupling=-0.1)

    def test_uniform_activation_is_fixed_point(self):
        """Uniform activation should not change under propagation."""
        ring = self._make_ring(4)
        for s in ring:
            s.activation = 1.0
        prop = LocalPropagator(coupling=0.15)
        prop.step(ring)
        for s in ring:
            assert s.activation == pytest.approx(1.0, abs=1e-12)

    def test_zero_activation_is_fixed_point(self):
        ring = self._make_ring(4)
        prop = LocalPropagator(coupling=0.15)
        prop.step(ring)
        for s in ring:
            assert s.activation == pytest.approx(0.0, abs=1e-12)

    def test_activation_spreads_to_neighbours(self):
        """A spike at shard 0 should partially spread to shards 1 and 3 (ring)."""
        ring = self._make_ring(4)
        ring[0].activation = 1.0
        prop = LocalPropagator(coupling=0.15)
        prop.step(ring)
        # Neighbours get positive activation
        assert ring[1].activation > 0.0
        assert ring[3].activation > 0.0
        # Centre loses some activation
        assert ring[0].activation < 1.0

    def test_total_activation_conserved(self):
        """Discrete-wave propagation conserves total activation."""
        ring = self._make_ring(6)
        ring[2].activation = 3.0
        ring[4].activation = 1.5
        total_before = sum(s.activation for s in ring)
        prop = LocalPropagator(coupling=0.2)
        for _ in range(10):
            prop.step(ring)
        total_after = sum(s.activation for s in ring)
        assert total_after == pytest.approx(total_before, rel=1e-9)


# ---------------------------------------------------------------------------
# HarmonicIndex
# ---------------------------------------------------------------------------


class TestHarmonicIndex:
    def test_default_construction(self):
        idx = HarmonicIndex()
        assert len(idx.shards) == 8
        assert idx._step_count == 0

    def test_custom_n_harmonics(self):
        idx = HarmonicIndex(n_harmonics=4)
        assert len(idx.shards) == 4

    def test_shard_basin_centres(self):
        idx = HarmonicIndex(n_harmonics=3)
        assert idx.shards[0].basin_centre == pytest.approx(ALPHA, rel=1e-9)
        assert idx.shards[1].basin_centre == pytest.approx(2 * ALPHA, rel=1e-9)
        assert idx.shards[2].basin_centre == pytest.approx(3 * ALPHA, rel=1e-9)

    def test_inject_direct(self):
        idx = HarmonicIndex(n_harmonics=4)
        idx.inject(0, 2.5)
        assert idx.shards[0].activation == pytest.approx(2.5)

    def test_inject_wrap(self):
        idx = HarmonicIndex(n_harmonics=4)
        idx.inject(4, 1.0)  # wraps to index 0
        assert idx.shards[0].activation == pytest.approx(1.0)

    def test_inject_from_trajectory_final_positive(self):
        """A trajectory ending near +α should inject into shard 0 (harmonic 1)."""
        idx = HarmonicIndex(n_harmonics=4)
        shard = idx.inject_from_trajectory_final(ALPHA)
        assert shard.index == 0
        assert shard.activation == pytest.approx(1.0)

    def test_inject_from_trajectory_final_negative(self):
        """|-α| == α, so should still hit shard 0."""
        idx = HarmonicIndex(n_harmonics=4)
        shard = idx.inject_from_trajectory_final(-ALPHA)
        assert shard.index == 0

    def test_inject_from_second_harmonic(self):
        """A value near 2·α should map to shard 1."""
        idx = HarmonicIndex(n_harmonics=4)
        shard = idx.inject_from_trajectory_final(2 * ALPHA + 0.01)
        assert shard.index == 1

    def test_propagate_increments_step(self):
        idx = HarmonicIndex()
        idx.propagate(3)
        assert idx._step_count == 3

    def test_total_activation_tracks_injections(self):
        idx = HarmonicIndex(n_harmonics=4)
        idx.inject(0, 1.0)
        idx.inject(2, 2.0)
        assert idx.total_activation() == pytest.approx(3.0)

    def test_total_activation_conserved_after_propagation(self):
        idx = HarmonicIndex(n_harmonics=8)
        idx.inject(0, 5.0)
        idx.inject(3, 2.0)
        total_before = idx.total_activation()
        idx.propagate(20)
        assert idx.total_activation() == pytest.approx(total_before, rel=1e-9)

    def test_peak_shard_after_inject(self):
        idx = HarmonicIndex(n_harmonics=4)
        idx.inject(2, 9.0)
        peak = idx.peak_shard()
        assert peak.index == 2

    def test_state_structure(self):
        idx = HarmonicIndex(n_harmonics=3)
        state = idx.state()
        assert "step" in state
        assert "shards" in state
        assert len(state["shards"]) == 3
        for entry in state["shards"]:
            assert "index" in entry
            assert "harmonic" in entry
            assert "basin_centre" in entry
            assert "activation" in entry

    def test_reset(self):
        idx = HarmonicIndex(n_harmonics=4)
        idx.inject(0, 5.0)
        idx.propagate(3)
        idx.reset()
        assert idx._step_count == 0
        assert idx.total_activation() == pytest.approx(0.0)

    def test_new_index_is_cold(self):
        idx = HarmonicIndex()
        assert idx.is_cold()

    def test_ensure_warm_seeds_home_when_cold(self):
        idx = HarmonicIndex()
        assert idx.ensure_warm() is True
        assert not idx.is_cold()
        assert idx.peak_shard().index == 0
        assert idx.total_activation() == pytest.approx(1.0)
        assert idx._step_count == 1  # one local propagate after inject

    def test_ensure_warm_is_noop_when_hot(self):
        idx = HarmonicIndex()
        idx.inject(3, 4.0)
        assert idx.ensure_warm() is False
        assert idx.shards[3].activation == pytest.approx(4.0)
        assert idx._step_count == 0

    def test_ensure_warm_is_peaked_not_uniform(self):
        from psspps.scorer import modulate_search_alpha

        idx = HarmonicIndex()
        idx.ensure_warm()
        acts = idx.activation_vector()
        assert acts.max() > acts.min()
        alpha = modulate_search_alpha(acts)
        assert alpha > 0.5  # peaked → local/harmonic, not cold 0.5 or diffuse 0.0

    def test_set_coupling_updates_local_propagator(self):
        idx = HarmonicIndex(n_harmonics=8, coupling=0.15)
        applied = idx.set_coupling(0.30)
        assert applied == pytest.approx(0.30)
        assert idx.coupling == pytest.approx(0.30)
        assert idx._propagator.coupling == pytest.approx(0.30)

    def test_set_coupling_clips_local_below_half(self):
        idx = HarmonicIndex()
        applied = idx.set_coupling(0.8)
        assert applied == pytest.approx(0.499)
        assert idx._resonance_propagator.coupling == pytest.approx(0.8)

    def test_reset_restores_base_coupling_and_clears_topology(self):
        idx = HarmonicIndex(n_harmonics=8, coupling=0.15)
        idx.set_coupling(0.30)
        idx.last_t_b_norm = 0.4
        idx.last_chi = 12.0
        idx.reset()
        assert idx.coupling == pytest.approx(0.15)
        assert idx.last_t_b_norm is None
        assert idx.last_chi is None

    def test_snapshot_roundtrip_preserves_coupling_and_t_b(self):
        idx = HarmonicIndex()
        idx.set_coupling(0.22)
        idx.last_t_b_norm = -0.3
        idx.last_chi = 4.0
        snap = idx.dump_snapshot()
        other = HarmonicIndex()
        other.load_snapshot(snap)
        assert other.coupling == pytest.approx(0.22)
        assert other.last_t_b_norm == pytest.approx(-0.3)
        assert other.last_chi == pytest.approx(4.0)

    def test_propagate_resonance_mode_increments_step(self):
        idx = HarmonicIndex()
        idx.inject(0, 4.0)
        idx.propagate(5, mode="resonance")
        assert idx._step_count == 5

    def test_propagate_unknown_mode_raises(self):
        idx = HarmonicIndex()
        with pytest.raises(ValueError, match="Unknown propagation mode"):
            idx.propagate(1, mode="bogus")

    def test_total_activation_conserved_resonance(self):
        """Resonance sharing must conserve total activation exactly."""
        idx = HarmonicIndex(n_harmonics=8)
        idx.inject(0, 8.0)
        idx.inject(3, 2.0)
        total_before = idx.total_activation()
        idx.propagate(20, mode="resonance")
        assert idx.total_activation() == pytest.approx(total_before, rel=1e-9)


# ---------------------------------------------------------------------------
# ResonancePropagator
# ---------------------------------------------------------------------------


class TestResonancePropagator:
    def _make_ring(self, n: int = 8) -> list[HarmonicShard]:
        return [HarmonicShard(index=i, harmonic=i + 1) for i in range(n)]

    def test_coupling_bounds(self):
        with pytest.raises(ValueError):
            ResonancePropagator(coupling=0.0)
        with pytest.raises(ValueError):
            ResonancePropagator(coupling=1.0)
        with pytest.raises(ValueError):
            ResonancePropagator(coupling=-0.1)

    def test_zero_activation_no_change(self):
        ring = self._make_ring()
        prop = ResonancePropagator(coupling=0.15)
        prop.step(ring)
        assert all(s.activation == pytest.approx(0.0) for s in ring)

    def test_single_shard_no_change(self):
        ring = [HarmonicShard(index=0, harmonic=1, activation=5.0)]
        prop = ResonancePropagator(coupling=0.15)
        prop.step(ring)
        assert ring[0].activation == pytest.approx(5.0)

    def test_total_activation_conserved(self):
        """Resonance sharing: hotspot donates, receivers gain, total is conserved."""
        ring = self._make_ring(8)
        ring[0].activation = 6.0
        ring[4].activation = 2.0
        total_before = sum(s.activation for s in ring)
        prop = ResonancePropagator(coupling=0.15)
        for _ in range(10):
            prop.step(ring)
        total_after = sum(s.activation for s in ring)
        assert total_after == pytest.approx(total_before, rel=1e-9)

    def test_hotspot_loses_activation(self):
        """After one step, the peak shard must have less activation than before."""
        ring = self._make_ring(8)
        ring[0].activation = 10.0
        a_before = ring[0].activation
        prop = ResonancePropagator(coupling=0.15)
        prop.step(ring)
        assert ring[0].activation < a_before

    def test_receivers_gain_activation(self):
        """Non-peak shards that were at 0 should gain activation after one step."""
        ring = self._make_ring(8)
        ring[0].activation = 10.0
        prop = ResonancePropagator(coupling=0.15)
        prop.step(ring)
        assert all(s.activation >= 0.0 for s in ring)
        assert any(s.activation > 0.0 for s in ring[1:])

    def test_dominant_hotspot_radiates_outward(self):
        """When hotspot is fully dominant, far shards receive more than near ones."""
        ring = self._make_ring(8)
        ring[0].activation = 100.0  # near-total dominance
        prop = ResonancePropagator(coupling=0.15)
        prop.step(ring)
        # Shard 4 is the antipode (ring distance = N/2 = 4 → d = 1.0 → max resonance)
        # Shard 1 is adjacent (ring distance = 1 → d = 0.25 → lower resonance)
        assert ring[4].activation > ring[1].activation

    def test_ring_distance_symmetry(self):
        """Shards equidistant from the hotspot should receive equal activation."""
        ring = self._make_ring(8)
        ring[4].activation = 8.0  # hotspot at centre of ring
        prop = ResonancePropagator(coupling=0.15)
        prop.step(ring)
        # Shards 3 and 5 are each 1 step away from hotspot 4
        assert ring[3].activation == pytest.approx(ring[5].activation, rel=1e-9)
        # Shards 2 and 6 are each 2 steps away
        assert ring[2].activation == pytest.approx(ring[6].activation, rel=1e-9)

    def test_weak_hotspot_self_reinforcement(self):
        """
        When the hotspot holds a small fraction of total activation,
        gate → -1 and the resonance kernel inverts — self-coupling dominates,
        so the donation is small and the system stays stable.
        """
        ring = self._make_ring(8)
        for s in ring:
            s.activation = 1.0      # uniform — every shard is equally 'dominant'
        ring[0].activation = 1.01   # barely dominant
        total_before = sum(s.activation for s in ring)
        prop = ResonancePropagator(coupling=0.15)
        prop.step(ring)
        assert sum(s.activation for s in ring) == pytest.approx(total_before, rel=1e-9)
        # With very small dominance ratio the donated amount is tiny
        assert ring[0].activation > 0.0


# ---------------------------------------------------------------------------
# IsometricCosinePropagator
# ---------------------------------------------------------------------------


class TestIsometricCosinePropagator:
    def _make_ring(self, n: int = 8) -> list[HarmonicShard]:
        return [HarmonicShard(index=i, harmonic=i + 1) for i in range(n)]

    def test_coupling_bounds(self):
        with pytest.raises(ValueError):
            IsometricCosinePropagator(coupling=0.0)
        with pytest.raises(ValueError):
            IsometricCosinePropagator(coupling=1.0)

    def test_zero_activation_no_change(self):
        ring = self._make_ring()
        prop = IsometricCosinePropagator(coupling=0.15)
        prop.step(ring)
        assert all(s.activation == pytest.approx(0.0) for s in ring)

    def test_single_step_spreads_to_all(self):
        """Isometric cosine couples every shard to every other in ONE step."""
        ring = self._make_ring(8)
        ring[0].activation = 10.0
        prop = IsometricCosinePropagator(coupling=0.15)
        prop.step(ring)
        # All non-zero shards now have non-zero activation (positive or negative)
        non_zero = [i for i, s in enumerate(ring) if i != 0 and abs(s.activation) > 1e-12]
        assert len(non_zero) > 0

    def test_near_shards_excitatory(self):
        """Nearest neighbours (d=1/4) must receive positive activation."""
        ring = self._make_ring(8)
        ring[4].activation = 10.0  # hotspot at centre
        prop = IsometricCosinePropagator(coupling=0.15)
        prop.step(ring)
        # Shards 3 and 5 are at ring distance 1 → d=0.25 → cos(π/4) > 0
        assert ring[3].activation > 0.0
        assert ring[5].activation > 0.0

    def test_antipodal_shard_inhibited(self):
        """Antipodal shard (d=1) must receive negative activation."""
        ring = self._make_ring(8)
        ring[0].activation = 10.0
        prop = IsometricCosinePropagator(coupling=0.15)
        prop.step(ring)
        # Shard 4 is antipodal (d=1) → cos(π) = -1 → inhibited
        assert ring[4].activation < 0.0

    def test_dissipative_total_decreases(self):
        """Isometric cosine is dissipative: total activation decays each step."""
        ring = self._make_ring(8)
        ring[0].activation = 8.0
        total_before = sum(s.activation for s in ring)
        prop = IsometricCosinePropagator(coupling=0.15)
        prop.step(ring)
        total_after = sum(s.activation for s in ring)
        # Total must decrease (cosine row-sum = -1 for N=8, so loss = κ × total)
        assert total_after < total_before

    def test_equidistant_shards_symmetric(self):
        """Shards equidistant from the source must receive equal activation."""
        ring = self._make_ring(8)
        ring[0].activation = 10.0
        prop = IsometricCosinePropagator(coupling=0.15)
        prop.step(ring)
        # Shards 1 and 7 are both at ring distance 1 from shard 0
        assert ring[1].activation == pytest.approx(ring[7].activation, rel=1e-9)
        # Shards 3 and 5 are both at ring distance 3
        assert ring[3].activation == pytest.approx(ring[5].activation, rel=1e-9)

    def test_kernel_shape_for_n8(self):
        """Verify the cosine kernel values for N=8 analytically."""
        prop = IsometricCosinePropagator(coupling=0.99)
        K = prop._build_kernel(8)
        # d=1/4 (ring distance 1): cos(π/4) = √2/2
        assert K[0, 1] == pytest.approx(math.sqrt(2) / 2, abs=1e-12)
        # d=1/2 (ring distance 2): cos(π/2) = 0
        assert K[0, 2] == pytest.approx(0.0, abs=1e-12)
        # d=3/4 (ring distance 3): cos(3π/4) = -√2/2
        assert K[0, 3] == pytest.approx(-math.sqrt(2) / 2, abs=1e-12)
        # d=1 (ring distance 4, antipodal): cos(π) = -1
        assert K[0, 4] == pytest.approx(-1.0, abs=1e-12)
        # Self-coupling excluded
        assert K[0, 0] == 0.0

    def test_index_propagate_isometric_increments_step(self):
        idx = HarmonicIndex()
        idx.inject(0, 4.0)
        idx.propagate(3, mode="isometric")
        assert idx._step_count == 3

    def test_index_propagate_isometric_dissipative(self):
        """HarmonicIndex.propagate(mode='isometric') should reduce total activation."""
        idx = HarmonicIndex(n_harmonics=8)
        idx.inject(0, 8.0)
        total_before = idx.total_activation()
        idx.propagate(1, mode="isometric")
        assert idx.total_activation() < total_before


# ---------------------------------------------------------------------------
# TicketClipper
# ---------------------------------------------------------------------------


class TestTicketClipper:
    def test_clip_on_active_hub(self):
        idx = HarmonicIndex(n_harmonics=8)
        idx.inject(0, 5.0)  # HOME hub → shard 0
        clipper = TicketClipper(idx, threshold=0.01)
        clips = clipper.clip_step(step=0)
        hub_names = [c.hub for c in clips]
        assert "HOME" in hub_names

    def test_no_clip_below_threshold(self):
        idx = HarmonicIndex(n_harmonics=8)
        clipper = TicketClipper(idx, threshold=1000.0)
        clips = clipper.clip_step(step=0)
        assert clips == []

    def test_dominance_ratio_in_range(self):
        idx = HarmonicIndex(n_harmonics=8)
        idx.inject(0, 5.0)
        clipper = TicketClipper(idx, threshold=0.01)
        clips = clipper.clip_step(step=0)
        for c in clips:
            assert 0.0 <= c.dominance_ratio <= 1.0

    def test_propagate_and_clip_records_log(self):
        idx = HarmonicIndex(n_harmonics=8)
        idx.inject(0, 5.0)
        clipper = TicketClipper(idx, threshold=0.01)
        clipper.propagate_and_clip(steps=3, mode="isometric")
        assert len(clipper.log) > 0

    def test_journey_summary_structure(self):
        idx = HarmonicIndex(n_harmonics=8)
        idx.inject(0, 5.0)
        clipper = TicketClipper(idx, threshold=0.01)
        clipper.propagate_and_clip(steps=2, mode="isometric")
        summary = clipper.journey_summary()
        assert "hubs_clipped" in summary
        assert "total_clips" in summary
        assert "peak_dominance" in summary

    def test_clear_empties_log(self):
        idx = HarmonicIndex(n_harmonics=8)
        idx.inject(0, 5.0)
        clipper = TicketClipper(idx, threshold=0.01)
        clipper.clip_step(0)
        assert len(clipper.log) > 0
        clipper.clear()
        assert clipper.log == []


# ---------------------------------------------------------------------------
# cosine_path_count
# ---------------------------------------------------------------------------


class TestCosinePathCount:
    def test_one_step_from_n_shards(self):
        # From 8 shards, 1 step: 8 × 7^1 = 56 paths
        assert cosine_path_count(8, 1) == 8 * 7

    def test_six_steps_local_vs_isometric(self):
        # Local (nearest-neighbour): 2^6 = 64 paths per source
        # Isometric: 8 × 7^6 = 8 × 117649 = 941192
        result = cosine_path_count(8, 6)
        assert result == 8 * (7 ** 6)
        assert result > 2 ** 6  # always more than nearest-neighbour


# ---------------------------------------------------------------------------
# Coherence indexing (M3 gate feedback)
# ---------------------------------------------------------------------------


class TestCoherenceIndexing:
    def test_shard_coherence_default_one(self):
        s = HarmonicShard(index=0, harmonic=1)
        assert s.coherence == pytest.approx(1.0)

    def test_coherence_vector_all_one_at_init(self):
        idx = HarmonicIndex(n_harmonics=8)
        v = idx.coherence_vector()
        assert v.shape == (8,)
        assert np.all(v == pytest.approx(1.0))

    def test_mean_coherence_one_at_init(self):
        idx = HarmonicIndex(n_harmonics=8)
        assert idx.mean_coherence() == pytest.approx(1.0)

    def test_high_m3_decays_hot_shard(self):
        """Shard 0 hot — its deviation from SHI is largest → takes the biggest hit."""
        idx = HarmonicIndex(n_harmonics=4)
        idx.inject(0, 5.0)
        idx.update_coherence_from_m3(m3=5.0, threshold=1.0)
        assert idx.shards[0].coherence < 1.0

    def test_low_m3_heals_coherence(self):
        """Accepted M3 (≤ threshold) heals all shards toward 1.0."""
        idx = HarmonicIndex(n_harmonics=4)
        idx.inject(0, 5.0)
        idx.update_coherence_from_m3(m3=5.0, threshold=1.0)
        degraded = idx.shards[0].coherence
        idx.update_coherence_from_m3(m3=0.5, threshold=1.0)
        assert idx.shards[0].coherence > degraded

    def test_coherence_bounded_after_many_high_m3(self):
        """Repeated high-M3 injections must never push coherence below 0."""
        idx = HarmonicIndex(n_harmonics=4)
        idx.inject(0, 10.0)
        for _ in range(100):
            idx.update_coherence_from_m3(m3=100.0, threshold=1.0, decay_rate=0.5)
        for shard in idx.shards:
            assert 0.0 <= shard.coherence <= 1.0

    def test_dark_ring_high_m3_no_decay(self):
        """All-zero activations → dev_sum = 0 → else branch fires → healing, not decay."""
        idx = HarmonicIndex(n_harmonics=4)
        # All shards dark; M3 > threshold but dev_sum = 0 → heals (stays at 1.0)
        idx.update_coherence_from_m3(m3=100.0, threshold=1.0)
        for shard in idx.shards:
            assert shard.coherence == pytest.approx(1.0)

    def test_heal_coherence_approaches_one(self):
        idx = HarmonicIndex(n_harmonics=4)
        idx.inject(0, 5.0)
        idx.update_coherence_from_m3(m3=5.0, threshold=1.0, decay_rate=0.5)
        degraded = min(s.coherence for s in idx.shards)
        assert degraded < 1.0
        for _ in range(200):
            idx.heal_coherence(heal_rate=0.05)
        for shard in idx.shards:
            assert shard.coherence > 0.95

    def test_reset_restores_coherence_to_one(self):
        idx = HarmonicIndex(n_harmonics=4)
        idx.inject(0, 5.0)
        idx.update_coherence_from_m3(m3=5.0)
        assert any(s.coherence < 1.0 for s in idx.shards)
        idx.reset()
        assert idx._step_count == 0
        assert idx.total_activation() == pytest.approx(0.0)
        for shard in idx.shards:
            assert shard.coherence == pytest.approx(1.0)

    def test_state_includes_coherence_per_shard(self):
        idx = HarmonicIndex(n_harmonics=3)
        state = idx.state()
        assert "mean_coherence" in state
        for entry in state["shards"]:
            assert "coherence" in entry
            assert 0.0 <= entry["coherence"] <= 1.0

    def test_state_mean_coherence_reflects_decay(self):
        idx = HarmonicIndex(n_harmonics=4)
        idx.inject(0, 5.0)
        idx.update_coherence_from_m3(m3=5.0, threshold=1.0)
        state = idx.state()
        assert state["mean_coherence"] < 1.0

    def test_hot_shard_takes_larger_hit_than_dark(self):
        """The hot shard's deviation from SHI is larger → coherence decays more."""
        idx = HarmonicIndex(n_harmonics=4)
        idx.inject(0, 10.0)  # shard 0 hot; shards 1-3 dark
        idx.update_coherence_from_m3(m3=5.0, threshold=1.0)
        # Shard 0 has the largest deviation → largest weight → most decay
        hot_coherence = idx.shards[0].coherence
        dark_coherences = [idx.shards[i].coherence for i in range(1, 4)]
        assert hot_coherence < min(dark_coherences)
