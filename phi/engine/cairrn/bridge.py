# -*- coding: utf-8 -*-
"""phi.engine.cairrn.bridge — three-layer CAIRRN pipeline for phi.

The CairnBridge is the physics engine.  It owns:

    - Five HubState instances (one per phi hub)
    - An 8-shard harmonic ring (the index)
    - Per-hub WelfordWindow z-score trackers

Every phi operation that needs to interact with the CAIRRN substrate calls
``bridge.step(hub_name, metric)`` once, then calls ``bridge.propagate()``
to diffuse the activation through the ring.

The three layers
────────────────

    Layer 1  Ana-Chi modulation
        modulated = metric × gravity × (decay^steps  if rattling  else 1)

    Layer 2  neg_exp sharding
        shard = floor(e^χ × 8 / 14.44)   clamped to [0, 7]
        The backwards-e map places high-χ hubs at high shards.
        f(x) = −eˣ is closed under differentiation.

    Layer 3  coherence enforcement
        coherence = exp(−steps / τ_hub)    per-hub time constant
        τ = −1 / log(decay)  — each hub decays at its own rate
        If coherence < 0.50 → flag incoherent → re-route to HOME

Constants
─────────
All shared constants live in ``_constants.py`` — never inline them here.
"""
from __future__ import annotations

import math
import logging
from collections import deque
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from phi.engine.cairrn._constants import (
    HUB_PARAMS,
    KAPPA,
    ALPHA,
    N_SHARDS,
    COHERENCE_FLOOR,
)

_log = logging.getLogger("phi.cairrn.bridge")


# ── Welford sliding-window z-score tracker ────────────────────────────────────

class WelfordWindow:
    """
    Online mean / variance over a fixed-size sliding window.

    Uses compensated-sum for O(1) amortised updates.  On eviction of the
    oldest value, its contribution is subtracted from _sum and _sum_sq.

    z_score(x) returns the z-score of x against the current window,
    or 0.0 when fewer than 2 samples exist (undefined variance).
    """

    def __init__(self, window: int = 32) -> None:
        self._buf: deque     = deque(maxlen=window)
        self._sum:    float  = 0.0
        self._sum_sq: float  = 0.0

    # Maximum absolute value stored — prevents float overflow in variance when
    # a runaway metric (e.g. from a GNN producing Inf/very-large outputs) enters
    # the ring.  Values outside [-1e6, 1e6] indicate a pipeline bug, but we
    # guard here so the router never crashes the UI thread.
    _MAX_VAL: float = 1e6

    def push(self, x: float) -> None:
        x = max(-self._MAX_VAL, min(self._MAX_VAL, x))  # clamp before storing
        if len(self._buf) == self._buf.maxlen:
            old          = self._buf[0]
            self._sum    -= old
            self._sum_sq -= old * old
        self._buf.append(x)
        self._sum    += x
        self._sum_sq += x * x

    @property
    def n(self) -> int:
        return len(self._buf)

    @property
    def mean(self) -> float:
        return self._sum / self.n if self.n > 0 else 0.0

    @property
    def variance(self) -> float:
        if self.n < 2:
            return 0.0
        mu = self.mean
        try:
            return max(0.0, sum((x - mu) ** 2 for x in self._buf) / (self.n - 1))
        except (OverflowError, ValueError):
            # Buffer contains pre-clamp runaway values — flush and recover.
            self._buf.clear()
            self._sum = 0.0
            self._sum_sq = 0.0
            return 0.0

    @property
    def std(self) -> float:
        return math.sqrt(self.variance)

    def z_score(self, x: float) -> float:
        """z-score of x relative to the current window.  Returns 0.0 if std ≈ 0."""
        s = self.std
        return (x - self.mean) / s if s >= 1e-8 else 0.0


# ── Hub and pipeline data structures ─────────────────────────────────────────

@dataclass
class HubState:
    """Live state of one phi CAIRRN hub."""
    name:         str
    chi:          float
    gravity:      float
    rattling:     bool
    memory_decay: float
    tau:          float     # coherence time constant: −1/log(decay)
    activation:   float = 0.0
    shard:        int   = 0
    steps:        int   = 0
    coherence:    float = 1.0
    last_metric:  float = 0.0
    z_awareness:  float = 0.0


@dataclass
class PipelineResult:
    """Result of running one metric through the three-layer pipeline."""
    hub:         str
    metric:      float
    modulated:   float
    shard:       int
    coherence:   float
    coherent:    bool
    rerouted:    bool
    z_awareness: float = 0.0


# ── CairnBridge ───────────────────────────────────────────────────────────────

class CairnBridge:
    """
    Phi CAIRRN three-layer pipeline — standalone, no MCP dependency.

    Args
    ----
    coherence_floor  : soft floor for coherence (default 0.50 — reroute fires below)
    z_spawn_threshold: z-awareness threshold for spawn events (default 2.5)
    z_window         : WelfordWindow size per hub (default 32)
    harmonic_shards  : number of shards in the ring (default 8)
    """

    def __init__(
        self,
        coherence_floor:    float = COHERENCE_FLOOR,
        z_spawn_threshold:  float = 2.5,
        z_window:           int   = 32,
        harmonic_shards:    int   = N_SHARDS,
    ) -> None:
        self.coherence_floor   = coherence_floor
        self.z_spawn_threshold = z_spawn_threshold
        self.harmonic_shards   = harmonic_shards

        self._hubs: Dict[str, HubState] = {
            name: HubState(
                name         = name,
                chi          = p["chi"],
                gravity      = p["gravity"],
                rattling     = p["rattling"],
                memory_decay = p["decay"],
                tau          = p["tau"],
                shard        = p["shard"],
            )
            for name, p in HUB_PARAMS.items()
        }

        self._z_stats: Dict[str, WelfordWindow] = {
            name: WelfordWindow(window=z_window)
            for name in HUB_PARAMS
        }

        self._index: List[float] = [0.0] * harmonic_shards
        self._global_step: int   = 0

        # Events captured during the last ingest cycle.
        # Cleared at the start of each ingest_vault_snapshot() call.
        self._incoherence_events: Dict[str, float] = {}
        self._z_events:           Dict[str, float] = {}

    # ── Layer 1 — Ana-Chi modulation ──────────────────────────────────────────

    def _ana_chi_modulate(self, hub: HubState, metric: float) -> float:
        """
        modulated = metric × gravity × (decay^steps  if rattling  else 1)

        Rattling hubs (CODE, MATH, COMMANDS) apply exponential memory decay
        so activation naturally diminishes without new input.  Non-rattling
        hubs (HOME, agent-context) apply gravity only — they are stable
        background signals.
        """
        if hub.rattling:
            mem = hub.memory_decay ** max(hub.steps, 1)
            return metric * hub.gravity * mem
        return metric * hub.gravity

    # ── Layer 2 — neg_exp sharding ────────────────────────────────────────────

    @staticmethod
    def _chi_to_shard(chi: float) -> int:
        """
        shard = floor(e^χ × 8 / 14.44)   clamped to [0, 7]

        f(x) = −eˣ is the neg_exp map.  d/dx(−eˣ) = −eˣ — the map is closed
        under differentiation.  Higher χ → higher shard → more urgent priority.
        """
        return min(N_SHARDS - 1, int(math.exp(chi) * N_SHARDS / 14.44))

    # ── Layer 3 — coherence enforcement ──────────────────────────────────────

    def _coherence(self, steps: int, tau: float) -> float:
        """exp(−steps / τ_hub) — per-hub time constant."""
        return math.exp(-steps / tau) if tau > 0 else 0.0

    # ── Main pipeline entry ───────────────────────────────────────────────────

    def step(self, hub_name: str, metric: float) -> PipelineResult:
        """
        Run one metric through the full three-layer CAIRRN pipeline.

        Layer 1: Ana-Chi modulation  (gravity × decay)
        Layer 2: neg_exp sharding    (target shard on the ring)
        Layer 3: coherence check     (flag, reroute if incoherent)

        Injects the modulated value into the harmonic index at the target shard.
        If incoherent, re-routes to HOME shard and resets the hub step counter.

        Args
        ----
        hub_name : one of HOME, MATH, CODE, COMMANDS, agent-context
        metric   : normalised [0, 1] input signal

        Returns
        -------
        PipelineResult with all intermediate values
        """
        if hub_name not in self._hubs:
            raise ValueError(
                f"Unknown CAIRRN hub: {hub_name!r}.  Valid: {sorted(self._hubs)}"
            )

        hub = self._hubs[hub_name]
        hub.steps       += 1
        hub.last_metric  = metric
        self._global_step += 1

        # Layer 1
        modulated    = self._ana_chi_modulate(hub, metric)
        hub.activation = modulated

        # Layer 2
        shard = self._chi_to_shard(hub.chi)

        # Layer 3
        coherence = self._coherence(hub.steps, hub.tau)
        hub.coherence = coherence
        coherent  = coherence >= self.coherence_floor
        rerouted  = False

        if not coherent:
            _log.debug(
                "Hub %s incoherent (coh=%.3f) — rerouting to HOME", hub_name, coherence
            )
            self._incoherence_events[hub_name] = coherence
            hub.steps     = 0
            hub.coherence = 1.0
            shard         = self._hubs["HOME"].shard
            rerouted      = True

        # Inject into ring
        self._index[shard] = modulated

        # z-awareness
        stats = self._z_stats[hub_name]
        stats.push(modulated)
        z = stats.z_score(modulated)
        hub.z_awareness = z

        if abs(z) >= self.z_spawn_threshold:
            self._z_events[hub_name] = z
            _log.debug("Hub %s z-spike z=%.3f", hub_name, z)

        _log.debug(
            "CAIRRN %s  metric=%.3f  mod=%.3f  shard=%d  coh=%.3f  z=%+.3f  %s",
            hub_name, metric, modulated, shard, coherence, z,
            "→HOME" if rerouted else "✓",
        )
        return PipelineResult(
            hub=hub_name, metric=metric, modulated=modulated,
            shard=shard, coherence=coherence, coherent=coherent,
            rerouted=rerouted, z_awareness=z,
        )

    # ── Harmonic ring propagation ─────────────────────────────────────────────

    def propagate(self, steps: int = 1) -> List[float]:
        """
        Diffuse activation through the harmonic ring for *steps* steps.

        Each step:
            index[i] += κ × (index[i−1] + index[i+1]) − α × index[i]

        Ring is circular (periodic boundary conditions).

        Returns
        -------
        List[float]
            Final ring activation state (N_SHARDS values).
        """
        n = self.harmonic_shards
        for _ in range(steps):
            new = list(self._index)
            for i in range(n):
                left  = self._index[(i - 1) % n]
                right = self._index[(i + 1) % n]
                new[i] = (
                    self._index[i]
                    + KAPPA * (left + right)
                    - ALPHA * self._index[i]
                )
            self._index = new
        return list(self._index)

    # ── Memory decay ──────────────────────────────────────────────────────────

    def decay_all(self) -> None:
        """Apply per-hub memory_decay to all hub activations (one cycle tick)."""
        for hub in self._hubs.values():
            hub.activation *= hub.memory_decay

    # ── Spawn signals ─────────────────────────────────────────────────────────

    def spawn_signals(
        self,
        threshold: Optional[float] = None,
        include_z: bool = False,
    ) -> Dict[str, float]:
        """
        Return {hub_name: coherence} for hubs that went incoherent during the
        last ingest_vault_snapshot() cycle.

        Values are pre-reset coherence scores (how far below the floor the hub
        dropped before being rerouted to HOME).

        Args
        ----
        threshold : override coherence_floor (default: self.coherence_floor)
        include_z : if True, merge z-awareness spike events into the dict.
                    Z-triggered keys use the raw z-score as value.
                    Key collisions are won by the coherence signal.
        """
        floor   = threshold if threshold is not None else self.coherence_floor
        signals = dict(self._incoherence_events)

        for name, hub in self._hubs.items():
            if hub.coherence < floor and name not in signals:
                signals[name] = hub.coherence

        if include_z:
            for name, z in self._z_events.items():
                if name not in signals:
                    signals[name] = z

        return signals

    def z_awareness_signals(
        self,
        threshold: Optional[float] = None,
    ) -> Dict[str, float]:
        """
        Return {hub_name: z_score} for hubs whose |z_awareness| exceeded the
        z_spawn_threshold during the last ingest_vault_snapshot() cycle.

        Positive z → hub is unusually active.  Negative z → sudden quiet.
        """
        floor  = threshold if threshold is not None else self.z_spawn_threshold
        events = {k: v for k, v in self._z_events.items() if abs(v) >= floor}
        for name, hub in self._hubs.items():
            if abs(hub.z_awareness) >= floor and name not in events:
                events[name] = hub.z_awareness
        return events

    # ── Vault snapshot ingest ─────────────────────────────────────────────────

    def ingest_vault_snapshot(self, snapshot: dict) -> None:
        """
        Feed vault topology metrics into CAIRRN hubs.

        Accepts both key formats:
          Full topology:   "chi", "beta_1", "V", "orphan_count", "links_written"
          Lightweight:     "euler_chi", "nodes", "edges", "density", "components"

        Routing:
            chi / euler_chi             → HOME          (graph shape)
            beta_1 / edges              → MATH          (structural complexity)
            V / nodes                   → CODE          (symbol density)
            orphan_count / components   → COMMANDS      (actionable isolation)
            links_written / density     → agent-context (write activity)
        """
        self._incoherence_events.clear()
        self._z_events.clear()

        inv_chi   = float(snapshot.get("chi",          snapshot.get("euler_chi",   0.0)))
        beta_1    = float(snapshot.get("beta_1",       snapshot.get("edges",       0)))
        V         = float(snapshot.get("V",             snapshot.get("nodes",       1)))
        orphans   = float(snapshot.get("orphan_count",  snapshot.get("components",  0)))
        links_out = float(snapshot.get("links_written", snapshot.get("density",    0.0)))

        V = max(V, 1)
        self.step("HOME",          min(1.0, abs(inv_chi) / 10.0))
        self.step("MATH",          min(1.0, beta_1 / V))
        self.step("CODE",          min(1.0, V / 5000.0))
        self.step("COMMANDS",      min(1.0, orphans / V))
        self.step("agent-context", min(1.0, links_out))

    def ingest_arm_scores(self, arm_scores: Dict[str, float]) -> None:
        """
        Blend OctopusTracer arm score means into the harmonic index shards.

        Unlike ingest_vault_snapshot(), this does NOT step hub coherence clocks
        and does NOT generate spawn signals.  It blends arm feedback into ring
        propagation without inflating spawn pressure.

        Arm → hub routing:
            prune + sprout   → COMMANDS      (structural interventions)
            graft + rank     → HOME          (graph topology / centrality)
            cluster + tag    → MATH          (conceptual structure)
            merge            → CODE          (content density)
            resurface        → agent-context (discovery backlog)

        Harmonic blending (EMA, α=0.5):
            index[shard] = 0.5 × old + 0.5 × modulated
        """
        def _clip(key: str) -> float:
            return min(1.0, max(0.0, float(arm_scores.get(key, 0.0))))

        routing = {
            "COMMANDS":      0.5 * (_clip("prune")   + _clip("sprout")),
            "HOME":          0.5 * (_clip("graft")   + _clip("rank")),
            "MATH":          0.5 * (_clip("cluster") + _clip("tag")),
            "CODE":          _clip("merge"),
            "agent-context": _clip("resurface"),
        }

        for hub_name, metric in routing.items():
            hub       = self._hubs[hub_name]
            modulated = self._ana_chi_modulate(hub, metric)
            shard     = hub.shard
            self._index[shard] = 0.5 * self._index[shard] + 0.5 * modulated

    # ── State inspection ──────────────────────────────────────────────────────

    def hub_state(self) -> Dict[str, dict]:
        """Full hub state snapshot (suitable for logging and serialisation)."""
        return {
            name: {
                "activation":  round(hub.activation, 4),
                "shard":       hub.shard,
                "tau":         round(hub.tau, 1),
                "coherence":   round(hub.coherence, 4),
                "steps":       hub.steps,
                "coherent":    hub.coherence >= self.coherence_floor,
                "z_awareness": round(hub.z_awareness, 4),
                "z_window_n":  self._z_stats[name].n,
            }
            for name, hub in self._hubs.items()
        }

    def index_state(self) -> List[float]:
        """Current harmonic ring activation (N_SHARDS values)."""
        return [round(v, 4) for v in self._index]

    def global_coherence(self) -> float:
        """Mean coherence across all hubs."""
        scores = [hub.coherence for hub in self._hubs.values()]
        return sum(scores) / len(scores)

    def global_z_awareness(self) -> float:
        """
        System-level z-awareness: gravity-weighted mean |z_awareness|.

        0.0–1.0  normal operating range
        1.0–2.5  mildly anomalous
        ≥ 2.5    z-hot: at least one hub is statistically unusual
        """
        total_w = weighted_z = 0.0
        for name, hub in self._hubs.items():
            w = HUB_PARAMS[name]["gravity"]
            weighted_z += abs(hub.z_awareness) * w
            total_w    += w
        return weighted_z / total_w if total_w > 0 else 0.0

    def all_coherent(self) -> bool:
        return all(hub.coherence >= self.coherence_floor for hub in self._hubs.values())

    def report(self) -> str:
        """Human-readable one-line summary including z-awareness."""
        coh  = self.global_coherence()
        gz   = self.global_z_awareness()
        step = self._global_step
        bad  = [n for n, h in self._hubs.items() if h.coherence < self.coherence_floor]
        hot  = [
            f"{n}({h.z_awareness:+.2f})"
            for n, h in self._hubs.items()
            if abs(h.z_awareness) >= self.z_spawn_threshold
        ]
        coh_flag = f"  ⚠ incoherent: {bad}" if bad else "  ✓ all coherent"
        z_flag   = f"  ⚡ z-hot: {hot}" if hot else ""
        return f"CAIRRN step={step}  global_coh={coh:.3f}  global_z={gz:.3f}{coh_flag}{z_flag}"

    # ── State restore (inverse of hub_state + index_state) ───────────────────

    def load_hub_state(
        self,
        hub_state: Dict[str, dict],
        index: Optional[List[float]] = None,
    ) -> None:
        """
        Restore hub activations from a previously saved hub_state() dict.

        Restores per-hub: activation, steps, coherence, z_awareness.
        Seeds each hub's WelfordWindow with synthetic pushes to approximate
        the activation history so z-scoring starts from the restored level.

        This is the inverse of hub_state() + index_state() — call it after
        loading a persisted state file to skip the cold-start warmup period.

        Args
        ----
        hub_state : dict as returned by hub_state()
        index     : list as returned by index_state() (optional)
        """
        for name, state in hub_state.items():
            if name not in self._hubs:
                continue
            hub             = self._hubs[name]
            hub.activation  = float(state.get("activation",  0.0))
            hub.steps       = int(state.get("steps",        0))
            hub.coherence   = float(state.get("coherence",   1.0))
            hub.z_awareness = float(state.get("z_awareness", 0.0))
            n_seed = min(8, max(1, int(state.get("z_window_n", 1))))
            if hub.activation != 0.0:
                for _ in range(n_seed):
                    self._z_stats[name].push(hub.activation)

        if index and len(index) == self.harmonic_shards:
            self._index = [float(v) for v in index]

        _log.info(
            "CairnBridge.load_hub_state: restored %d hubs  index=%s",
            len(hub_state),
            [round(v, 3) for v in self._index],
        )
