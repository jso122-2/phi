"""
TracerDaemon — manages a pool of OctopusTracers.

Architecture (LOCKED — pow.md):

    Spawn conditions:
      COLD_START       — always fires on first run_once()
      SHARD_DROP       — CAIRRN shard coherence drops below threshold
      DEGREE_ANOMALY   — degree distribution anomaly in complement graph G̅
      EMBEDDING_DRIFT  — BERT embedding drift exceeds threshold
      TICK_GATE        — scheduled tick gate at tick_gate_interval

    max_tracers cap:  hard ceiling on concurrent live tracers

    Tracers cohere by sharing the R signal over the same complement graph slice.

    Ana-Chi weight:   decreases with tick (rattling decay property from ana_chi.py)

    CAIRRN routing:   arm scores routed to harmonic index via CAIRRNBridge after
                      every run_once() — index changes after each call.

TracerSummary
    Aggregates across all live tracers:
      arm_prune, arm_graft, arm_cluster, arm_rank,
      arm_tag, arm_resurface, arm_merge, arm_sprout
      aggregated_tag, aggregated_merge   (mean over all tracer × tag/merge scores)
      mean_tick
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from models.arms import OctopusArms, ArmScores, ARM_NAMES
from models.bert_clipper import BERTClipper
from models.regression import compute_R
from models.ssm import SSMCore
from engine.gate import gate_coherence, gate_pass, COHERENCE_THRESHOLD
from sims.harmonic import HarmonicIndex


# ---------------------------------------------------------------------------
# Spawn condition tokens
# ---------------------------------------------------------------------------

SPAWN_COLD_START:    str = "COLD_START"
SPAWN_SHARD_DROP:    str = "SHARD_DROP"
SPAWN_DEGREE_ANOMALY: str = "DEGREE_ANOMALY"
SPAWN_EMBEDDING_DRIFT: str = "EMBEDDING_DRIFT"
SPAWN_TICK_GATE:     str = "TICK_GATE"


# ---------------------------------------------------------------------------
# Individual tracer
# ---------------------------------------------------------------------------

@dataclass
class Tracer:
    """
    One OctopusTracer instance.

    Holds its own arm score snapshot and tick counter.
    Ana-Chi weight (from sims.ana_chi rattling decay) reduces over ticks.
    """
    id: int
    spawn_condition: str
    arm_scores: dict[str, float] = field(default_factory=dict)
    tick: int = 0
    ana_chi_weight: float = 1.0          # starts at 1.0; decays each step

    # Ana-Chi rattling decay rate — mirrors memory_decay from the true_center basin
    _DECAY_RATE: float = 0.98

    def step(self, arm_scores: dict[str, float]) -> None:
        """Update with new arm scores and advance tick counter."""
        self.arm_scores = dict(arm_scores)
        self.tick += 1
        self.ana_chi_weight *= self._DECAY_RATE

    @property
    def coherence(self) -> float:
        """Tracer-level coherence: exp(−tick / tau) with tau=10."""
        return math.exp(-self.tick / 10.0)


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

@dataclass
class TracerSummary:
    """
    Aggregated view across all live tracers after one run_once() pass.

    All arm_* fields are mean scores across tracers for that arm.
    aggregated_tag / aggregated_merge are alias means (identical to arm_tag /
    arm_merge — provided as named fields matching the integration contract).
    """
    n_tracers: int
    arm_prune: float
    arm_graft: float
    arm_cluster: float
    arm_rank: float
    arm_tag: float
    arm_resurface: float
    arm_merge: float
    arm_sprout: float
    aggregated_tag: float
    aggregated_merge: float
    mean_tick: float
    mean_coherence: float
    mean_ana_chi_weight: float

    def as_dict(self) -> dict:
        return {
            "n_tracers":           self.n_tracers,
            "arm_prune":           self.arm_prune,
            "arm_graft":           self.arm_graft,
            "arm_cluster":         self.arm_cluster,
            "arm_rank":            self.arm_rank,
            "arm_tag":             self.arm_tag,
            "arm_resurface":       self.arm_resurface,
            "arm_merge":           self.arm_merge,
            "arm_sprout":          self.arm_sprout,
            "aggregated_tag":      self.aggregated_tag,
            "aggregated_merge":    self.aggregated_merge,
            "mean_tick":           self.mean_tick,
            "mean_coherence":      self.mean_coherence,
            "mean_ana_chi_weight": self.mean_ana_chi_weight,
        }


def _aggregate_tracers(tracers: list[Tracer]) -> TracerSummary:
    n = len(tracers)
    if n == 0:
        zero = TracerSummary(
            n_tracers=0,
            arm_prune=0.0, arm_graft=0.0, arm_cluster=0.0, arm_rank=0.0,
            arm_tag=0.0, arm_resurface=0.0, arm_merge=0.0, arm_sprout=0.0,
            aggregated_tag=0.0, aggregated_merge=0.0,
            mean_tick=0.0, mean_coherence=0.0, mean_ana_chi_weight=0.0,
        )
        return zero

    def _mean(arm: str) -> float:
        vals = [t.arm_scores.get(arm, 0.0) for t in tracers]
        return float(sum(vals) / n)

    tag_val  = _mean("TAG")
    merge_val = _mean("MERGE")

    return TracerSummary(
        n_tracers=n,
        arm_prune=     _mean("PRUNE"),
        arm_graft=     _mean("GRAFT"),
        arm_cluster=   _mean("CLUSTER"),
        arm_rank=      _mean("RANK"),
        arm_tag=       tag_val,
        arm_resurface= _mean("RESURFACE"),
        arm_merge=     merge_val,
        arm_sprout=    _mean("SPROUT"),
        aggregated_tag=   tag_val,
        aggregated_merge= merge_val,
        mean_tick=         sum(t.tick for t in tracers) / n,
        mean_coherence=    sum(t.coherence for t in tracers) / n,
        mean_ana_chi_weight= sum(t.ana_chi_weight for t in tracers) / n,
    )


# ---------------------------------------------------------------------------
# Daemon
# ---------------------------------------------------------------------------

class TracerDaemon:
    """
    Manages the pool of live OctopusTracers.

    Parameters
    ----------
    max_tracers       : hard ceiling on concurrent tracers
    tick_gate_interval: spawn a new tracer every this many ticks (tick-gate spawn)
    d                 : state / embedding dimension
    coherence_tau     : CAIRRN coherence time constant
    harmonic_index    : optional HarmonicIndex; creates one if None
    degree_anomaly_threshold : z-score at which degree distribution triggers spawn
    embedding_drift_threshold: norm-change above which embedding drift triggers spawn
    """

    def __init__(
        self,
        max_tracers: int = 8,
        tick_gate_interval: int = 4,
        d: int = 256,
        coherence_tau: float = 10.0,
        harmonic_index: Optional[HarmonicIndex] = None,
        degree_anomaly_threshold: float = 2.0,
        embedding_drift_threshold: float = 0.5,
        vault_root=None,
    ) -> None:
        self.max_tracers = max_tracers
        self.tick_gate_interval = tick_gate_interval
        self.d = d
        self.coherence_tau = coherence_tau
        self.degree_anomaly_threshold = degree_anomaly_threshold
        self.embedding_drift_threshold = embedding_drift_threshold

        self._tracers: list[Tracer] = []
        self._tick: int = 0
        self._bert = BERTClipper.load_default(d=d)
        self._ssm = SSMCore.load_default(d=d, n_layers=4)
        self._arms = OctopusArms.load_default(d_in=d)
        self._prev_H: Optional[np.ndarray] = None
        self._lora_proj: Optional[np.ndarray] = None   # updated each tick by BERT

        if harmonic_index is None:
            harmonic_index = HarmonicIndex(n_harmonics=8, coupling=0.15)
        self._harmonic_index = harmonic_index

        # Late import to avoid circular; bridge injected after construction
        from engine.bridge_factory import CAIRRNBridge
        self._bridge = CAIRRNBridge(self._harmonic_index)

        # SambaWriter — None until vault_root is provided (avoids writing during tests)
        self._samba = None
        if vault_root is not None:
            from engine.vault_writer import SambaWriter
            from pathlib import Path
            self._samba = SambaWriter(vault_root=Path(vault_root))

    # ------------------------------------------------------------------
    # Spawn helpers
    # ------------------------------------------------------------------

    def _spawn(self, condition: str) -> Optional[Tracer]:
        """Attempt to spawn a new tracer if cap allows."""
        if len(self._tracers) >= self.max_tracers:
            return None
        t = Tracer(
            id=len(self._tracers),
            spawn_condition=condition,
        )
        self._tracers.append(t)
        return t

    def _check_degree_anomaly(self, A: np.ndarray) -> bool:
        """True when complement-graph degree distribution is anomalous (z-score)."""
        A_bar = 1.0 - A
        np.fill_diagonal(A_bar, 0.0)
        degrees = A_bar.sum(axis=1)
        if degrees.std() < 1e-9:
            return False
        z_scores = np.abs((degrees - degrees.mean()) / degrees.std())
        return bool(z_scores.max() > self.degree_anomaly_threshold)

    def _check_embedding_drift(self, H: np.ndarray) -> bool:
        """True when mean embedding shift from last tick exceeds threshold."""
        if self._prev_H is None or self._prev_H.shape != H.shape:
            return False
        delta = np.linalg.norm(H - self._prev_H) / max(H.shape[0], 1)
        return bool(delta > self.embedding_drift_threshold)

    def _check_shard_drop(self) -> bool:
        """True when any harmonic shard coherence drops (activation sudden drop)."""
        acts = np.array([s.activation for s in self._harmonic_index.shards])
        if acts.max() < 1e-9:
            return False
        # Coherence proxy: ratio of min to max activation
        ratio = acts.min() / acts.max()
        return bool(ratio < (1.0 - COHERENCE_THRESHOLD))

    # ------------------------------------------------------------------
    # Main tick
    # ------------------------------------------------------------------

    def run_once(
        self,
        A: np.ndarray,
        X: Optional[np.ndarray] = None,
    ) -> TracerSummary:
        """
        One TracerDaemon tick.

        Parameters
        ----------
        A : (N, N) adjacency matrix of the current graph snapshot
        X : (N, d) optional node embeddings; random if None

        Returns
        -------
        TracerSummary — aggregated across all live tracers after this tick
        """
        A = np.asarray(A, dtype=np.float64)
        N = A.shape[0]

        if X is None:
            rng = np.random.default_rng(self._tick)
            X = rng.standard_normal((N, self.d)).astype(np.float64)
        else:
            X = np.asarray(X, dtype=np.float64)

        # ── BERT Clipping Network ────────────────────────────────────
        # Encode X → H_bert (node embeddings), tau, lora_proj for sucker inheritance
        H_bert, tau_bert, self._lora_proj = self._bert.encode(X)
        self._bert.update(X, lr=1e-4)   # perpetual pretraining step (gradient clipped)

        # ── SSM tick ────────────────────────────────────────────────
        H, tau = self._ssm.tick(H_bert)

        # ── Regression pipeline ─────────────────────────────────────
        R, A_bar, Theta, F = compute_R(A, H, tau)

        # ── Arm forward pass ────────────────────────────────────────
        arm_scores_obj: ArmScores = self._arms.forward(R)
        arm_means: dict[str, float] = arm_scores_obj.mean_scores()

        # ── Spawn logic ──────────────────────────────────────────────

        # Cold start: first ever tick → always spawn
        if self._tick == 0:
            self._spawn(SPAWN_COLD_START)

        # Tick gate: spawn at configured interval
        if self._tick > 0 and self._tick % self.tick_gate_interval == 0:
            self._spawn(SPAWN_TICK_GATE)

        # Shard drop
        if self._check_shard_drop():
            self._spawn(SPAWN_SHARD_DROP)

        # Degree anomaly
        if self._check_degree_anomaly(A):
            self._spawn(SPAWN_DEGREE_ANOMALY)

        # Embedding drift
        if self._check_embedding_drift(H):
            self._spawn(SPAWN_EMBEDDING_DRIFT)

        # ── Update all live tracers ──────────────────────────────────
        for tracer in self._tracers:
            tracer.step(arm_means)

        # ── Route arm scores to harmonic index ──────────────────────
        self._bridge.ingest_arm_scores(arm_means)
        self._bridge.step_tick()

        # ── Samba MCP: arm scores → vault writes ─────────────────────
        if self._samba is not None:
            _, coherence = gate_pass(self._tick, self.coherence_tau)
            self._samba.process(arm_means, coherence)

        # ── Housekeeping ─────────────────────────────────────────────
        self._prev_H = H.copy()
        self._tick += 1

        return _aggregate_tracers(self._tracers)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def tracers(self) -> list[Tracer]:
        return list(self._tracers)

    @property
    def tick(self) -> int:
        return self._tick

    @property
    def harmonic_index(self) -> HarmonicIndex:
        return self._harmonic_index

    @property
    def bridge(self):
        return self._bridge

    @property
    def bert(self) -> BERTClipper:
        return self._bert

    @property
    def lora_proj(self) -> Optional[np.ndarray]:
        """Last lora_proj emitted by BERTClipper; None before first run_once()."""
        return self._lora_proj

    def __repr__(self) -> str:
        return (
            f"<TracerDaemon tick={self._tick} "
            f"tracers={len(self._tracers)}/{self.max_tracers}>"
        )
