"""
Tests for engine.tracer_daemon.TracerDaemon (14 tests).

Coverage:
  - Cold start always spawns ≥1 tracer with SPAWN_COLD_START condition
  - TracerSummary has all 8 arm fields + aggregated_tag + aggregated_merge
  - Ana-Chi weight decreases with tick (rattling decay property)
  - Harmonic index changes after run_once() (arm → CAIRRN routing live)
  - max_tracers cap respected
  - Tick gate fires at configured interval
"""
from __future__ import annotations

import numpy as np
import pytest

from engine.tracer_daemon import (
    TracerDaemon,
    TracerSummary,
    Tracer,
    SPAWN_COLD_START,
    SPAWN_TICK_GATE,
    SPAWN_SHARD_DROP,
    SPAWN_DEGREE_ANOMALY,
    SPAWN_EMBEDDING_DRIFT,
)
from sims.harmonic import HarmonicIndex


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def small_A(N: int = 6) -> np.ndarray:
    """Sparse ring graph — ensures complement G̅ is non-trivial (non-zero edges)."""
    A = np.zeros((N, N))
    for i in range(N):
        A[i, (i + 1) % N] = 1.0
        A[(i + 1) % N, i] = 1.0
    return A


def make_daemon(**kw) -> TracerDaemon:
    defaults = dict(d=16, max_tracers=8, tick_gate_interval=4)
    defaults.update(kw)
    return TracerDaemon(**defaults)


# ===========================================================================
# Cold start
# ===========================================================================

class TestColdStart:
    def test_first_run_spawns_at_least_one_tracer(self):
        daemon = make_daemon()
        daemon.run_once(small_A())
        assert len(daemon.tracers) >= 1

    def test_first_tracer_has_cold_start_condition(self):
        daemon = make_daemon()
        daemon.run_once(small_A())
        assert daemon.tracers[0].spawn_condition == SPAWN_COLD_START

    def test_cold_start_only_on_first_tick(self):
        daemon = make_daemon()
        daemon.run_once(small_A())
        n_after_1 = len(daemon.tracers)
        daemon.run_once(small_A())
        # second tick adds no cold-start tracer
        cold_starts = [t for t in daemon.tracers if t.spawn_condition == SPAWN_COLD_START]
        assert len(cold_starts) == 1


# ===========================================================================
# TracerSummary fields
# ===========================================================================

class TestTracerSummaryFields:
    def test_summary_has_all_8_arm_fields(self):
        daemon = make_daemon()
        summary = daemon.run_once(small_A())
        assert hasattr(summary, "arm_prune")
        assert hasattr(summary, "arm_graft")
        assert hasattr(summary, "arm_cluster")
        assert hasattr(summary, "arm_rank")
        assert hasattr(summary, "arm_tag")
        assert hasattr(summary, "arm_resurface")
        assert hasattr(summary, "arm_merge")
        assert hasattr(summary, "arm_sprout")

    def test_summary_has_aggregated_tag(self):
        daemon = make_daemon()
        summary = daemon.run_once(small_A())
        assert hasattr(summary, "aggregated_tag")

    def test_summary_has_aggregated_merge(self):
        daemon = make_daemon()
        summary = daemon.run_once(small_A())
        assert hasattr(summary, "aggregated_merge")

    def test_aggregated_tag_equals_arm_tag(self):
        daemon = make_daemon()
        summary = daemon.run_once(small_A())
        assert summary.aggregated_tag == pytest.approx(summary.arm_tag)

    def test_aggregated_merge_equals_arm_merge(self):
        daemon = make_daemon()
        summary = daemon.run_once(small_A())
        assert summary.aggregated_merge == pytest.approx(summary.arm_merge)

    def test_summary_as_dict_has_all_keys(self):
        daemon = make_daemon()
        summary = daemon.run_once(small_A())
        d = summary.as_dict()
        for key in ("arm_prune", "arm_graft", "arm_cluster", "arm_rank",
                    "arm_tag", "arm_resurface", "arm_merge", "arm_sprout",
                    "aggregated_tag", "aggregated_merge", "n_tracers"):
            assert key in d


# ===========================================================================
# Ana-Chi weight (rattling decay)
# ===========================================================================

class TestAnaChiDecay:
    def test_weight_decreases_with_ticks(self):
        daemon = make_daemon()
        A = small_A()
        daemon.run_once(A)
        t = daemon.tracers[0]
        w0 = t.ana_chi_weight
        daemon.run_once(A)
        w1 = t.ana_chi_weight
        assert w1 < w0

    def test_weight_strictly_positive(self):
        daemon = make_daemon()
        A = small_A()
        for _ in range(20):
            daemon.run_once(A)
        for t in daemon.tracers:
            assert t.ana_chi_weight > 0.0


# ===========================================================================
# Harmonic index changes after run_once()
# ===========================================================================

class TestHarmonicIndexLive:
    def test_index_changes_after_run_once(self):
        idx = HarmonicIndex(n_harmonics=8, coupling=0.15)
        daemon = TracerDaemon(d=16, harmonic_index=idx)
        before = [s.activation for s in idx.shards]
        daemon.run_once(small_A())
        after = [s.activation for s in idx.shards]
        assert before != after


# ===========================================================================
# max_tracers cap
# ===========================================================================

class TestMaxTracersCap:
    def test_cap_respected_over_many_ticks(self):
        daemon = make_daemon(max_tracers=3, tick_gate_interval=1)
        A = small_A()
        for _ in range(20):
            daemon.run_once(A)
        assert len(daemon.tracers) <= 3


# ===========================================================================
# Tick gate
# ===========================================================================

class TestTickGate:
    def test_tick_gate_fires_at_interval(self):
        daemon = make_daemon(max_tracers=10, tick_gate_interval=4)
        A = small_A()
        # After tick 0 (cold start) + tick 4 (gate), should have ≥2
        for _ in range(5):
            daemon.run_once(A)
        gate_spawns = [t for t in daemon.tracers if t.spawn_condition == SPAWN_TICK_GATE]
        assert len(gate_spawns) >= 1
