"""
Tests for engine.bridge_factory.CAIRRNBridge (12 tests).

Regression guards:
  Bug 1 — spawn signals capture pre-reset coherence
  _incoherence_events cleared on next ingest cycle
  Both key formats (topology vs. graph_snapshot) → identical hub activations
  ingest_arm_scores() mutates index without stepping hub clocks or generating events
  Harmonic index bounded after repeated arm routing
"""
from __future__ import annotations

import pytest
import numpy as np

from sims.harmonic import HarmonicIndex
from engine.bridge_factory import (
    CAIRRNBridge,
    make_bridge,
    ARM_SHARD_MAP,
    IncoherenceEvent,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fresh_bridge() -> tuple[HarmonicIndex, CAIRRNBridge]:
    idx = HarmonicIndex(n_harmonics=8, coupling=0.15)
    bridge = CAIRRNBridge(idx)
    return idx, bridge


def all_arm_scores(val: float = 1.0) -> dict[str, float]:
    from models.arms import ARM_NAMES
    return {name: val for name in ARM_NAMES}


# ===========================================================================
# 1. Spawn signals capture pre-reset coherence (Bug 1 regression guard)
# ===========================================================================

class TestSpawnSignalCoherence:
    def test_record_spawn_coherence_stores_value(self):
        _, bridge = fresh_bridge()
        bridge.record_spawn_coherence("TAG", 0.72)
        assert bridge._pre_reset_coherence == pytest.approx(0.72)

    def test_incoherent_spawn_creates_event(self):
        _, bridge = fresh_bridge()
        bridge.record_spawn_coherence("MERGE", 0.30)
        assert len(bridge.incoherence_events) == 1

    def test_coherent_spawn_no_event(self):
        _, bridge = fresh_bridge()
        bridge.record_spawn_coherence("PRUNE", 0.80)
        assert len(bridge.incoherence_events) == 0

    def test_event_captures_arm_and_coherence(self):
        _, bridge = fresh_bridge()
        bridge.record_spawn_coherence("SPROUT", 0.20)
        ev = bridge.incoherence_events[0]
        assert ev.arm_name == "SPROUT"
        assert ev.coherence_before_reset == pytest.approx(0.20)


# ===========================================================================
# 2. _incoherence_events cleared on next ingest cycle
# ===========================================================================

class TestIncoherenceEventClear:
    def test_clear_returns_events_and_empties_list(self):
        _, bridge = fresh_bridge()
        bridge.record_spawn_coherence("GRAFT", 0.10)
        bridge.record_spawn_coherence("RANK", 0.05)
        returned = bridge.clear_incoherence_events()
        assert len(returned) == 2
        assert len(bridge.incoherence_events) == 0

    def test_clear_idempotent(self):
        _, bridge = fresh_bridge()
        bridge.clear_incoherence_events()
        assert bridge.incoherence_events == []


# ===========================================================================
# 3. Both key formats reach hubs with identical activations
# ===========================================================================

class TestTopologyKeyFormats:
    def _nodes(self) -> dict:
        return {"node_a": 1, "node_b": 2, "node_c": 3}

    def test_topology_and_graph_snapshot_identical(self):
        nodes = self._nodes()

        idx1 = HarmonicIndex(n_harmonics=8, coupling=0.15)
        b1 = CAIRRNBridge(idx1)
        hubs1 = b1.ingest_topology({"topology": nodes})

        idx2 = HarmonicIndex(n_harmonics=8, coupling=0.15)
        b2 = CAIRRNBridge(idx2)
        hubs2 = b2.ingest_topology({"graph_snapshot": nodes})

        assert set(hubs1.keys()) == set(hubs2.keys())
        for hub in hubs1:
            np.testing.assert_allclose(hubs1[hub], hubs2[hub], atol=1e-12)

    def test_empty_topology_returns_empty_dict(self):
        _, bridge = fresh_bridge()
        result = bridge.ingest_topology({"topology": {}})
        assert result == {}


# ===========================================================================
# 4. ingest_arm_scores() mutates index without stepping hub clocks or events
# ===========================================================================

class TestIngestArmScores:
    def test_index_changes_after_ingest(self):
        idx, bridge = fresh_bridge()
        before = [s.activation for s in idx.shards]
        bridge.ingest_arm_scores(all_arm_scores(1.0))
        after = [s.activation for s in idx.shards]
        assert before != after

    def test_no_incoherence_events_generated(self):
        _, bridge = fresh_bridge()
        bridge.ingest_arm_scores(all_arm_scores(0.9))
        assert bridge.incoherence_events == []

    def test_arm_shard_map_coverage(self):
        idx, bridge = fresh_bridge()
        bridge.ingest_arm_scores(all_arm_scores(2.0))
        # All 8 shards should have received activation
        assert all(s.activation > 0.0 for s in idx.shards)


# ===========================================================================
# 5. Harmonic index bounded after repeated arm routing
# ===========================================================================

class TestIndexBounded:
    def test_activations_finite_after_100_ingest_cycles(self):
        idx, bridge = fresh_bridge()
        for i in range(100):
            bridge.ingest_arm_scores(all_arm_scores(float(i % 5 + 1)))
        for shard in idx.shards:
            assert math.isfinite(shard.activation)

    def test_make_bridge_factory(self):
        bridge = make_bridge()
        assert isinstance(bridge, CAIRRNBridge)

    def test_arm_shard_map_has_8_entries(self):
        assert len(ARM_SHARD_MAP) == 8
        assert set(ARM_SHARD_MAP.values()) == set(range(8))


import math
