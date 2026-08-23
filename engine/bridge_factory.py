"""
CAIRRN Bridge — connects OctopusTracer arm scores to the harmonic index.

Arm → shard mapping (8 arms → 8 shards, one-to-one):

    PRUNE     → shard 0   (HOME     basin 1.96)
    GRAFT     → shard 1   (MATH     basin 3.92)
    CLUSTER   → shard 2   (MATH     basin 5.88)
    RANK      → shard 3   (CODE     basin 7.84)
    TAG       → shard 4   (CODE     basin 9.80)
    RESURFACE → shard 5   (COMMANDS basin 11.76)
    MERGE     → shard 6   (agent-context basin 13.72)
    SPROUT    → shard 7   (agent-context basin 15.68)

ingest_arm_scores() mutates the harmonic index WITHOUT calling propagate —
hub clocks are NOT stepped, no incoherence events are generated.

Topology key formats accepted by ingest_topology():
    "topology"       — full topology dict (node_id → adjacency list or embedding)
    "graph_snapshot" — graph snapshot dict (same semantics, different key name)

Both produce identical hub activations for the same underlying data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np

from sims.harmonic import HarmonicIndex


# ---------------------------------------------------------------------------
# Arm → shard map
# ---------------------------------------------------------------------------

ARM_SHARD_MAP: dict[str, int] = {
    "PRUNE":     0,
    "GRAFT":     1,
    "CLUSTER":   2,
    "RANK":      3,
    "TAG":       4,
    "RESURFACE": 5,
    "MERGE":     6,
    "SPROUT":    7,
}


# ---------------------------------------------------------------------------
# Incoherence event
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class IncoherenceEvent:
    """Recorded when coherence drops below threshold before a bridge reset."""
    arm_name: str
    shard: int
    coherence_before_reset: float
    tick: int


# ---------------------------------------------------------------------------
# Bridge
# ---------------------------------------------------------------------------

class CAIRRNBridge:
    """
    Routes OctopusTracer arm scores into the harmonic index shards.

    Parameters
    ----------
    harmonic_index : HarmonicIndex
        The live harmonic ring to inject into.
    coherence_threshold : float
        Events below this coherence are recorded as incoherence events.
    """

    def __init__(
        self,
        harmonic_index: HarmonicIndex,
        coherence_threshold: float = 0.50,
    ) -> None:
        self._index = harmonic_index
        self.coherence_threshold = coherence_threshold
        self._incoherence_events: list[IncoherenceEvent] = []
        self._tick: int = 0
        self._pre_reset_coherence: Optional[float] = None

    # ------------------------------------------------------------------
    # Core injection — no propagation, no hub clock step
    # ------------------------------------------------------------------

    def ingest_arm_scores(self, arm_scores: dict[str, float]) -> None:
        """
        Inject arm mean scores into the corresponding shards.

        Does NOT call harmonic_index.propagate() — hub clocks are NOT stepped.
        Does NOT emit incoherence events — silent injection only.

        Parameters
        ----------
        arm_scores : dict mapping arm_name → scalar score
        """
        for arm_name, score in arm_scores.items():
            shard = ARM_SHARD_MAP.get(arm_name)
            if shard is not None:
                self._index.inject(shard, float(score))

    # ------------------------------------------------------------------
    # Topology ingestion (both key formats)
    # ------------------------------------------------------------------

    def ingest_topology(self, topology_payload: dict[str, Any]) -> dict[str, list[float]]:
        """
        Accept a topology or graph_snapshot payload and route activations
        to hubs.

        Handles two equivalent key formats:
            {"topology": {node_id: ...}}
            {"graph_snapshot": {node_id: ...}}

        Activation per hub = number of nodes whose id hash maps to that hub's
        shard range, normalised by total nodes.  Both key formats produce
        identical hub activations for the same underlying node data.

        Returns
        -------
        dict mapping hub_name → [shard_activation, ...]
        """
        nodes: dict[str, Any] = (
            topology_payload.get("topology")
            or topology_payload.get("graph_snapshot")
            or {}
        )
        n_nodes = len(nodes)
        hub_activations: dict[str, list[float]] = {}

        if n_nodes == 0:
            return hub_activations

        # Distribute node embeddings across shards by content hash
        shard_totals = np.zeros(8, dtype=np.float64)
        for node_id, payload in nodes.items():
            shard_idx = hash(node_id) % 8
            value = 1.0 / n_nodes
            shard_totals[shard_idx] += value

        for shard_idx, val in enumerate(shard_totals):
            if val > 0.0:
                self._index.inject(shard_idx, val)

        # Build return dict (hub → shard activations after injection)
        from sims.harmonic import HUB_SHARD_MAP
        for hub, shard_indices in HUB_SHARD_MAP.items():
            hub_activations[hub] = [
                self._index.shards[i].activation for i in shard_indices
            ]

        return hub_activations

    # ------------------------------------------------------------------
    # Coherence tracking
    # ------------------------------------------------------------------

    def record_spawn_coherence(self, arm_name: str, coherence: float) -> None:
        """
        Record coherence captured just before a tracer spawn or reset.

        If coherence < threshold this becomes an IncoherenceEvent.
        Called by TracerDaemon before resetting a tracer.
        """
        self._pre_reset_coherence = coherence
        if coherence < self.coherence_threshold:
            shard = ARM_SHARD_MAP.get(arm_name, 0)
            self._incoherence_events.append(IncoherenceEvent(
                arm_name=arm_name,
                shard=shard,
                coherence_before_reset=coherence,
                tick=self._tick,
            ))

    def clear_incoherence_events(self) -> list[IncoherenceEvent]:
        """
        Clear and return the current incoherence event list.

        Called at the start of each new ingest cycle.
        """
        events = list(self._incoherence_events)
        self._incoherence_events.clear()
        return events

    @property
    def incoherence_events(self) -> list[IncoherenceEvent]:
        return list(self._incoherence_events)

    def step_tick(self) -> None:
        """Advance the bridge tick counter (called by TracerDaemon)."""
        self._tick += 1

    def __repr__(self) -> str:
        return (
            f"<CAIRRNBridge tick={self._tick} "
            f"incoherence_events={len(self._incoherence_events)}>"
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def make_bridge(harmonic_index: Optional[HarmonicIndex] = None) -> CAIRRNBridge:
    """
    Construct a CAIRRNBridge with a fresh (or provided) HarmonicIndex.
    """
    if harmonic_index is None:
        harmonic_index = HarmonicIndex(n_harmonics=8, coupling=0.15)
    return CAIRRNBridge(harmonic_index)
