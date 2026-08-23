"""
MycelialSubstrate — living metabolic layer for the phi node graph.

Connects workers/cairrn/mycelial.py (pure formulas) to the real phi system.
One substrate instance wraps one PhiGraphSnapshot and runs per-tick
metabolism across all track nodes and their similarity edges.

Architecture
------------
The PhiGraphSnapshot provides:
    tracks  : N SongNodes  →  one energy state per node
    H       : (N, 256)     →  cosine similarity used for Hebbian/growth gate
    A       : (N, N)       →  binary adjacency matrix → initial edge weights

Substrate mutable state (evolves on each tick):
    energy        : np.ndarray (N,)   — node energy ∈ [0, E_max]
    weights       : np.ndarray (N, N) — edge weights (float, evolved from A)
    starved_ticks : np.ndarray (N,)   — consecutive starvation ticks per node
    tick_count    : int                — total ticks run

Tick lifecycle (one gate-open = one tick):
    1. demand()           — D_i from CODE hub pressure + embedding signals
    2. nutrient_alloc()   — softmax budget → allocation per node
    3. metabolise()       — energy_i ← clamp(energy + η·nutrients - cost, 0, E_max)
    4. passive_flow()     — energy diffusion along every edge
    5. active_flow()      — bloom/starve transport for high/low energy nodes
    6. weight_update()    — Hebbian + decay + entropy per edge
    7. shimmer_decay()    — cold edge degradation (edges not recently active)
    8. autophagy_trigger()— flag nodes held below θ_prune for τ_ticks
    9. growth_gate()      — allow new edges when all four conditions pass

Wiring
------
Called from CAIRRNDispatcher via PhiActionKind.MYCELIAL_TICK:
    dispatcher.enqueue(PhiAction(PhiActionKind.MYCELIAL_TICK, {"budget": 1.0}))
or from _run_cairrn_code_tick() directly when a substrate is attached.

Nutrient budget
---------------
budget = CODE_hub_activation * N  (total energy units to distribute this tick).
Higher CODE activation → more nutrients → faster growth.

Edge activity tracking
----------------------
Each edge (i, j) has a "last_active" tick counter; edges with no recent
flow receive shimmer_decay.  Activity is set when passive or active flow
is non-zero above the flow threshold _FLOW_THRESH.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np

from workers.cairrn.mycelial import (
    _BASAL_COST,
    _E_MAX,
    _ETA,
    _GAMMA,
    _THETA_GROW,
    _THETA_PRUNE,
    _THETA_SIM,
    _TAU_TICKS,
    absorb_metabolite,
    active_flow,
    autophagy_trigger,
    conductance,
    demand,
    growth_gate,
    metabolise,
    metabolite_value,
    nutrient_alloc,
    passive_flow,
    shimmer_decay,
    weight_update,
)


# ---------------------------------------------------------------------------
# Substrate constants
# ---------------------------------------------------------------------------

_FLOW_THRESH: float = 1e-4
"""Minimum flow magnitude to count as "edge active" this tick."""

_SHIMMER_RATE: float = 0.02
"""Shimmer decay rate for cold edges (per tick not active)."""

_BUDGET_SCALE: float = 1.0
"""Default per-node budget multiplier (total budget = scale × N × code_act)."""

_NEW_EDGE_WEIGHT: float = 0.5
"""Initial weight assigned when the growth gate opens a new edge."""

_BEETLE_RING_SIZE: int = 10
"""Number of recent Δw_ij deltas retained per edge for volatility computation.
V = std(ΔT_edge) + avg(|ΔT_edge|) · W  (W = 1.0, from DAWN formula)."""

_SHI_GROWTH_THRESHOLD: float = 0.50
"""Minimum SHI for the growth gate mood_ok condition to pass."""

# SHI component weights (α, β, γ, δ, ε) — sum to 1.0 across five terms
_SHI_W_COLD:  float = 0.20   # α — cold-edge fraction penalty
_SHI_W_VOLT:  float = 0.20   # β — mean Beetle edge volatility penalty
_SHI_W_DISP:  float = 0.20   # γ — energy dispersion (tracer divergence proxy)
_SHI_W_COHER: float = 0.20   # δ — coherence deficit (1 − mean_energy)
_SHI_W_SOOT:  float = 0.20   # ε — composting backpressure: Soot/(Ash+1)


# ---------------------------------------------------------------------------
# Tick result
# ---------------------------------------------------------------------------


@dataclass
class MycelialTickResult:
    """
    Summary of one MycelialSubstrate tick.

    Attributes
    ----------
    tick        : tick index (0-based)
    n_nodes     : total nodes
    n_edges     : edges with weight > 0
    mean_energy : mean node energy after tick
    max_energy  : peak node energy
    total_flow  : sum of |passive + active| flow across all edges
    new_edges   : number of new edges formed via growth gate this tick
    autolysed   : indices of nodes that triggered autophagy this tick
    budget_used : total nutrients distributed
    """
    tick: int
    n_nodes: int
    n_edges: int
    mean_energy: float
    max_energy: float
    total_flow: float
    new_edges: int
    autolysed: list[int]
    budget_used: float

    def as_dict(self) -> dict:
        return {
            "tick":         self.tick,
            "n_nodes":      self.n_nodes,
            "n_edges":      self.n_edges,
            "mean_energy":  round(self.mean_energy, 6),
            "max_energy":   round(self.max_energy, 6),
            "total_flow":   round(self.total_flow, 6),
            "new_edges":    self.new_edges,
            "autolysed":    self.autolysed,
            "budget_used":  round(self.budget_used, 6),
        }


# ---------------------------------------------------------------------------
# MycelialSubstrate
# ---------------------------------------------------------------------------


class MycelialSubstrate:
    """
    Living metabolic layer bound to one PhiGraphSnapshot.

    Parameters
    ----------
    snapshot        : PhiGraphSnapshot — tracks, H (N×256), A (N×N adjacency)
    harmonic_index  : live HarmonicIndex — provides CODE hub activation
    eta             : metabolic conversion rate (default _ETA)
    basal_cost      : energy cost per tick per node (default _BASAL_COST)
    e_max           : energy ceiling per node (default _E_MAX)
    gamma           : active transport gain (default _GAMMA)
    budget_scale    : budget = scale × N × code_activation (default 1.0)
    """

    _CODE_SHARDS: tuple[int, int] = (3, 4)

    def __init__(
        self,
        snapshot: Any,
        harmonic_index: Any,
        eta: float = _ETA,
        basal_cost: float = _BASAL_COST,
        e_max: float = _E_MAX,
        gamma: float = _GAMMA,
        budget_scale: float = _BUDGET_SCALE,
    ) -> None:
        self._snap = snapshot
        self._index = harmonic_index
        self._eta = eta
        self._basal = basal_cost
        self._e_max = e_max
        self._gamma = gamma
        self._budget_scale = budget_scale

        N = len(snapshot.tracks)
        self._N = N

        # Node state
        self.energy: np.ndarray = np.zeros(N, dtype=np.float64)
        self.starved_ticks: np.ndarray = np.zeros(N, dtype=np.int32)

        # Edge state — initialized from binary adjacency, evolved by mycelial mechanics
        # weights[i, j] > 0 ↔ edge exists; 0 = no edge
        A = snapshot.A.astype(np.float64)
        self.weights: np.ndarray = A.copy()

        # Track how many ticks ago each edge last had flow (for shimmer decay)
        # -1 means never active
        self._edge_cold_ticks: np.ndarray = np.where(A > 0, 0, -1).astype(np.int32)

        # H normalised for cosine similarity
        norms = np.linalg.norm(snapshot.H, axis=1, keepdims=True)
        norms = np.where(norms < 1e-12, 1.0, norms)
        self._H_norm: np.ndarray = snapshot.H / norms  # (N, 256), unit rows

        # Beetle ring buffer: (i, j) → deque of last _BEETLE_RING_SIZE Δw_ij deltas
        # Used to compute edge volatility V = std(ΔT) + avg(|ΔT|)·W
        self._beetle_ring: dict[tuple[int, int], deque] = {}

        self.tick_count: int = 0

        # Compost state — updated externally via set_compost_state()
        # Soot: unenriched tracks in the enrichment queue
        # Ash:  fully enriched + ELO-rated tracks (coherent-play streak accumulated)
        self._soot_count: int = 0
        self._ash_count:  int = 0

    # ------------------------------------------------------------------
    # Main tick
    # ------------------------------------------------------------------

    def tick(self, budget: Optional[float] = None) -> MycelialTickResult:
        """
        Run one full metabolic cycle.

        Parameters
        ----------
        budget : total nutrient units to distribute this tick.
                 Default: budget_scale × N × CODE_hub_activation.

        Returns
        -------
        MycelialTickResult — summary statistics for this tick.
        """
        code_act = self._code_activation()

        if budget is None:
            budget = self._budget_scale * self._N * code_act

        # 1. Demand per node
        demands = self._compute_demands(code_act)

        # 2. Nutrient allocation (softmax over demand)
        nutrients = nutrient_alloc(demands, budget)
        budget_used = sum(nutrients)

        # 3. Metabolic conversion
        for i in range(self._N):
            self.energy[i] = metabolise(
                self.energy[i], nutrients[i],
                basal_cost=self._basal, eta=self._eta, e_max=self._e_max,
            )

        # 4 + 5. Flow (passive + active) across edges
        total_flow = self._run_flows()

        # 6. Edge weight update + 7. Shimmer decay
        self._update_weights()

        # 8. Autophagy check
        autolysed = self._check_autophagy()

        # 9. Growth gate — new edges
        new_edges = self._check_growth_gate()

        self.tick_count += 1
        n_edges = int(np.sum(self.weights > 0))

        return MycelialTickResult(
            tick=self.tick_count - 1,
            n_nodes=self._N,
            n_edges=n_edges,
            mean_energy=float(np.mean(self.energy)),
            max_energy=float(np.max(self.energy)) if self._N > 0 else 0.0,
            total_flow=total_flow,
            new_edges=new_edges,
            autolysed=autolysed,
            budget_used=budget_used,
        )

    # ------------------------------------------------------------------
    # State accessors
    # ------------------------------------------------------------------

    def node_energy(self, i: int) -> float:
        """Energy of node i."""
        return float(self.energy[i])

    def top_k_energy(self, k: int = 10) -> list[int]:
        """Indices of the k highest-energy nodes (descending)."""
        if self._N == 0:
            return []
        k = min(k, self._N)
        return list(np.argsort(self.energy)[::-1][:k])

    def edge_weight(self, i: int, j: int) -> float:
        """Weight of edge i→j."""
        return float(self.weights[i, j])

    def state(self) -> dict:
        """Serialisable substrate state snapshot."""
        return {
            "tick_count":    self.tick_count,
            "n_nodes":       self._N,
            "n_edges":       int(np.sum(self.weights > 0)),
            "mean_energy":   round(float(np.mean(self.energy)), 6),
            "max_energy":    round(float(np.max(self.energy)) if self._N > 0 else 0.0, 6),
            "code_act":      round(self._code_activation(), 6),
            "shi":           round(self.compute_shi(), 6),
        }

    def edge_volatility(self, i: int, j: int) -> float:
        """
        Beetle edge volatility for edge (i, j).

        V = std(ΔT_edge) + avg(|ΔT_edge|) · W   (W = 1.0)

        Computed from the last _BEETLE_RING_SIZE weight deltas stored in the
        ring buffer.  Returns 0.0 when the ring is empty (edge not yet active).

        Parameters
        ----------
        i, j : node indices of the directed edge
        """
        ring = self._beetle_ring.get((i, j))
        if not ring:
            return 0.0
        deltas = list(ring)
        n = len(deltas)
        if n == 0:
            return 0.0
        mean_d = sum(deltas) / n
        std_d  = (sum((d - mean_d) ** 2 for d in deltas) / n) ** 0.5
        avg_abs = sum(abs(d) for d in deltas) / n
        return std_d + avg_abs  # W = 1.0

    def set_compost_state(self, soot: int, ash: int) -> None:
        """
        Inject enrichment pipeline state as the Soot/Ash composting term.

        Call periodically from the CAIRRN dispatcher or enrich-daemon callback
        whenever the enrichment queue depth changes.

        Parameters
        ----------
        soot : int
            Unenriched tracks currently waiting in the enrichment queue.
        ash  : int
            Fully enriched tracks with non-default ELO (coherent-play streak
            accumulated).  +1 Laplace smoothing applied inside compute_shi().
        """
        self._soot_count = max(0, soot)
        self._ash_count  = max(0, ash)

    def compute_shi(self) -> float:
        """
        Schema Health Index for the current substrate state.

        SHI = 1 − (α·E_s + β·V_e + γ·D_t + δ·(1−S_c) + ε·Soot/(Ash+1))

        E_s        — cold-edge fraction: edges silent for > 5 ticks / total edges
        V_e        — mean Beetle volatility across all edges with ring data (normalised)
        D_t        — energy dispersion proxy: std(energy) / E_max  (tracer divergence)
        S_c        — mean node energy (substrate coherence ∈ [0, E_max])
        Soot/Ash+1 — enrichment backpressure (set via set_compost_state())
                     normalised to [0, 1] via min(1.0, …); +1 prevents div-by-zero

        All five weights sum to 1.0 so SHI ∈ [0, 1].
        SHI > 0.5 → substrate is healthy enough for new edge formation.

        Composting feedback loop (closes automatically once set_compost_state is wired):
            ingestion → Soot rises → SHI falls → G rises → e5 falls
            → fewer tracks surface → enrichment catches up → Ash rises
            → Soot/Ash falls → SHI rises → e5 rises → tracks surface again
        """
        if self._N == 0:
            return 1.0  # empty substrate is vacuously healthy

        total_edges = int(np.sum(self.weights > 0))

        # E_s — cold edge fraction
        if total_edges > 0:
            cold_count = int(np.sum(self._edge_cold_ticks > 5))
            e_s = cold_count / total_edges
        else:
            e_s = 0.0

        # V_e — mean Beetle volatility, normalised to [0, 1] by expected ceiling
        volt_values = []
        for ring in self._beetle_ring.values():
            if ring:
                deltas = list(ring)
                n = len(deltas)
                mean_d = sum(deltas) / n
                std_d  = (sum((d - mean_d) ** 2 for d in deltas) / n) ** 0.5
                avg_abs = sum(abs(d) for d in deltas) / n
                volt_values.append(std_d + avg_abs)
        v_e = min(1.0, (sum(volt_values) / len(volt_values)) if volt_values else 0.0)

        # D_t — energy dispersion (normalised std)
        d_t = float(np.std(self.energy)) / max(self._e_max, 1e-9)
        d_t = min(1.0, d_t)

        # S_c — coherence deficit (low mean energy = incoherent substrate)
        mean_e = float(np.mean(self.energy))
        s_c_deficit = 1.0 - min(1.0, mean_e / max(self._e_max, 1e-9))

        # Soot/(Ash+1) — enrichment backpressure, normalised to [0, 1]
        soot_ratio = min(1.0, self._soot_count / (self._ash_count + 1))

        penalty = (
            _SHI_W_COLD  * e_s
            + _SHI_W_VOLT  * v_e
            + _SHI_W_DISP  * d_t
            + _SHI_W_COHER * s_c_deficit
            + _SHI_W_SOOT  * soot_ratio
        )
        return round(max(0.0, 1.0 - penalty), 4)

    # ------------------------------------------------------------------
    # Snapshot rebind — call when PhiGraph rebuilds
    # ------------------------------------------------------------------

    def rebind(self, snapshot: Any) -> None:
        """
        Rebind the substrate to a new snapshot (same or different N).

        Preserves existing energy state for nodes that survive (by index).
        New nodes start at 0 energy.  Edge weights are re-initialised
        where the new adjacency adds edges not previously present.
        """
        new_N = len(snapshot.tracks)
        new_A = snapshot.A.astype(np.float64)

        # Extend or trim energy state
        if new_N > self._N:
            extra = np.zeros(new_N - self._N, dtype=np.float64)
            self.energy = np.concatenate([self.energy, extra])
            extra_s = np.zeros(new_N - self._N, dtype=np.int32)
            self.starved_ticks = np.concatenate([self.starved_ticks, extra_s])
        else:
            self.energy = self.energy[:new_N]
            self.starved_ticks = self.starved_ticks[:new_N]

        # Merge new adjacency into existing weights
        old_W = self.weights
        new_W = np.zeros((new_N, new_N), dtype=np.float64)
        min_n = min(self._N, new_N)
        new_W[:min_n, :min_n] = old_W[:min_n, :min_n]
        # New edges from snapshot get initial weight
        new_edges = (new_A > 0) & (new_W == 0)
        new_W[new_edges] = _NEW_EDGE_WEIGHT

        self.weights = new_W
        self._edge_cold_ticks = np.where(new_W > 0, 0, -1).astype(np.int32)
        self._beetle_ring.clear()  # stale deltas would corrupt SHI after rebuild

        norms = np.linalg.norm(snapshot.H, axis=1, keepdims=True)
        norms = np.where(norms < 1e-12, 1.0, norms)
        self._H_norm = snapshot.H / norms

        self._snap = snapshot
        self._N = new_N

    # ------------------------------------------------------------------
    # Internal: demand
    # ------------------------------------------------------------------

    def _compute_demands(self, code_act: float) -> list[float]:
        """
        Compute demand D_i for every node using mycelial.demand().

        pressure    = CODE hub activation (broadcast to all nodes)
        drift_align = dot product of H_norm[i] with the mean H_norm
                      (how aligned this node is with the current embedding centroid)
        recency     = 0.5 (uniform — TODO: wire per-node recency when available)
        entropy     = normalised std of H[i] projected onto [0, 1]
        """
        if self._N == 0:
            return []

        # Drift alignment: cosine of each row with the centroid
        centroid = self._H_norm.mean(axis=0)
        centroid_norm = np.linalg.norm(centroid)
        if centroid_norm > 1e-12:
            centroid = centroid / centroid_norm
        drift_aligns = self._H_norm @ centroid  # (N,) ∈ [-1, 1]

        # Entropy proxy: std of embedding row, clipped to [0, 1]
        entropies = np.clip(self._snap.H.std(axis=1) / 10.0, 0.0, 1.0)

        return [
            demand(
                pressure=code_act,
                drift_align=float(drift_aligns[i]),
                recency=0.5,
                entropy=float(entropies[i]),
            )
            for i in range(self._N)
        ]

    # ------------------------------------------------------------------
    # Internal: flow
    # ------------------------------------------------------------------

    def _run_flows(self) -> float:
        """
        Apply passive + active flow on every edge where weights > 0.

        Returns total absolute flow (diagnostic scalar).
        """
        total = 0.0
        delta = np.zeros(self._N, dtype=np.float64)

        bloom = np.maximum(0.0, self.energy - 0.70)
        starve = np.maximum(0.0, 0.30 - self.energy)

        rows, cols = np.nonzero(self.weights > 0)
        for i, j in zip(rows, cols):
            if i == j:
                continue
            w = float(self.weights[i, j])
            ei, ej = float(self.energy[i]), float(self.energy[j])

            fp = passive_flow(ei, ej, w)
            fa = active_flow(ei, float(bloom[i]), float(starve[j]), w, self._gamma)
            net = fp + fa

            if abs(net) > _FLOW_THRESH:
                self._edge_cold_ticks[i, j] = 0
            else:
                if self._edge_cold_ticks[i, j] >= 0:
                    self._edge_cold_ticks[i, j] += 1

            delta[j] += net
            delta[i] -= net
            total += abs(net)

        # Apply clamped delta
        self.energy = np.clip(self.energy + delta, 0.0, self._e_max)
        return total

    # ------------------------------------------------------------------
    # Internal: edge weight update + shimmer decay
    # ------------------------------------------------------------------

    def _update_weights(self) -> None:
        """
        Hebbian weight update + shimmer decay on all edges.
        """
        rows, cols = np.nonzero(self.weights > 0)
        for i, j in zip(rows, cols):
            if i == j:
                continue
            sim = float(np.dot(self._H_norm[i], self._H_norm[j]))
            cold = int(self._edge_cold_ticks[i, j])

            if cold > 0:
                # Edge has not had flow — apply shimmer decay
                w_before = float(self.weights[i, j])
                self.weights[i, j] = shimmer_decay(w_before, cold, decay_rate=_SHIMMER_RATE)
                dw = float(self.weights[i, j]) - w_before
                ring = self._beetle_ring.setdefault((i, j), deque(maxlen=_BEETLE_RING_SIZE))
                ring.append(dw)
            else:
                # Edge was active — Hebbian update
                dw = weight_update(
                    similarity_ij=max(0.0, sim),
                    reliability_ij=0.8,
                    energy_i=float(self.energy[i]),
                    energy_j=float(self.energy[j]),
                    time_decay_ij=0.0,
                    mean_entropy_ij=0.0,
                )
                self.weights[i, j] = max(0.0, float(self.weights[i, j]) + dw)
                # Beetle: push delta into ring buffer (both decay and active paths)
                ring = self._beetle_ring.setdefault((i, j), deque(maxlen=_BEETLE_RING_SIZE))
                ring.append(dw)

    # ------------------------------------------------------------------
    # Internal: autophagy
    # ------------------------------------------------------------------

    def _check_autophagy(self) -> list[int]:
        """
        Update starvation counters and emit metabolites to neighbours
        of nodes that trigger autophagy.

        Returns list of autolysed node indices.
        """
        autolysed = []
        for i in range(self._N):
            if self.energy[i] < _THETA_PRUNE:
                self.starved_ticks[i] += 1
            else:
                self.starved_ticks[i] = 0

            if autophagy_trigger(float(self.energy[i]), int(self.starved_ticks[i])):
                met = metabolite_value(float(self.energy[i]), history_factor=1.0)
                # Emit metabolite to all neighbours
                neighbours = np.nonzero(self.weights[i] > 0)[0]
                for j in neighbours:
                    self.energy[j] = absorb_metabolite(
                        float(self.energy[j]), met, e_max=self._e_max
                    )
                # Zero out this node's energy and reset
                self.energy[i] = 0.0
                self.starved_ticks[i] = 0
                self.weights[i, :] = 0.0
                self.weights[:, i] = 0.0
                autolysed.append(i)

        return autolysed

    # ------------------------------------------------------------------
    # Internal: growth gate
    # ------------------------------------------------------------------

    def _check_growth_gate(self) -> int:
        """
        Scan high-energy nodes for new edge formation via growth_gate().

        Only checks high-energy nodes (energy > θ_grow) against their
        k-nearest H-space neighbours to keep the cost bounded.

        Returns the number of new edges formed.
        """
        new_count = 0
        # Only candidate nodes with enough energy
        candidates = np.where(self.energy > _THETA_GROW)[0]
        if len(candidates) == 0:
            return 0

        # SHI gate: compute once per growth check (not per edge pair)
        shi = self.compute_shi()
        mood_ok = shi >= _SHI_GROWTH_THRESHOLD

        for i in candidates:
            # Top-5 H-space neighbours not yet connected
            sims = self._H_norm @ self._H_norm[i]  # (N,)
            sims[i] = -1.0  # exclude self
            top = np.argsort(sims)[::-1][:5]
            for j in top:
                if self.weights[i, j] > 0:
                    continue  # already connected
                sim = float(sims[j])
                if growth_gate(
                    energy_i=float(self.energy[i]),
                    similarity_ij=sim,
                    temporal_ok=True,
                    mood_ok=mood_ok,  # SHI-gated: schema must be healthy to grow
                ):
                    self.weights[i, j] = _NEW_EDGE_WEIGHT
                    self.weights[j, i] = _NEW_EDGE_WEIGHT
                    self._edge_cold_ticks[i, j] = 0
                    self._edge_cold_ticks[j, i] = 0
                    new_count += 1

        return new_count

    # ------------------------------------------------------------------
    # Internal: CODE hub activation
    # ------------------------------------------------------------------

    def _code_activation(self) -> float:
        try:
            shards = self._index.shards
            vals = [
                shards[k].activation
                for k in self._CODE_SHARDS
                if k < len(shards)
            ]
            return float(sum(vals) / len(vals)) if vals else 0.0
        except Exception:
            return 0.0

    def __repr__(self) -> str:
        return (
            f"<MycelialSubstrate N={self._N} "
            f"tick={self.tick_count} "
            f"mean_e={self.energy.mean():.4f} "
            f"edges={int(np.sum(self.weights > 0))}>"
        )
