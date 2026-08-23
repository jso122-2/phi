"""
Temporal sharding index — CAIRRN-aware, Ana-Chi hosted.

The temporal index is the TIME dimension of the CAIRRN graph.
While the harmonic index (sims/harmonic.py) is the SPATIAL dimension
— where activation lives across harmonic basin centres — the temporal
index tracks WHEN activation arrived and how long each hub holds it.

Architecture
------------
Each of the five CAIRRN station hubs owns a temporal trace: a sliding
window of T time-windows (temporal shards) representing lags
t=0 (now) through t=T-1 (most distant past):

    TemporalShardIndex
    ├── HOME          T windows, decay 0.98  (true_center — longest memory)
    ├── MATH          T windows, decay 0.95  (white_peak)
    ├── CODE          T windows, decay 0.93  (mirror)
    ├── COMMANDS      T windows, decay 0.90  (escape)
    └── agent-context T windows, decay 0.90  (boundary)

Ana-Chi hosting
---------------
Each hub's memory decay rate is NOT arbitrary — it is governed by its
mapped Ana-Chi basin's `memory_decay` field:

    Hub           Basin         χ        memory_decay
    ──────────    ──────────    ──────   ────────────
    HOME          true_center   1.5414   0.98   ← equilibrium, longest memory
    MATH          white_peak    1.9600   0.95   ← singularity = ALPHA
    CODE          mirror        0.9900   0.93
    COMMANDS      escape        2.6700   0.90   ← rapid action, short memory
    agent-context boundary      0.0300   0.90   ← interface layer, short memory

At each clock advance, every activation in every temporal shard decays:

    activation[hub][t+1] = activation[hub][t] × memory_decay[hub]

CAIRRN awareness
----------------
The five hubs are structurally first-class.  Recording activation via
`record(hub_name, value)` automatically routes to the correct trace and
applies the correct decay dynamics.  There is no raw shard index — every
entry carries its hub identity.

Temporal shard ring
-------------------
Each hub's trace is a deque of T TemporalShard objects.  Window 0 is
"now"; window T-1 is the most distant past.  On each call to advance():

  1. All existing window activations are multiplied by hub's memory_decay
  2. A new empty TemporalShard is prepended at t=0
  3. The oldest window (t=T-1) is dropped
  4. All t indices are reset sequentially

Default T = 8 mirrors the N = 8 harmonic shards.

Integration with HarmonicIndex
--------------------------------
The temporal index shadows the harmonic index in the time domain.
Every hub injection into the harmonic index should also call
`temporal_index.record(hub_name, value)` to keep both indices aligned.
`graph_commit` in the MCP server does this automatically.

Key formulae
------------
  Memory decay    activation[t+1] = activation[t] × memory_decay
  Temporal coh    χ_eff = Σ_h (activation_h/total) × basin_h.χ
                  coherence = exp(-|χ_eff - 1.5414| / 0.40)
  Dominant hub    argmax_h Σ_t activation[h][t]
  Dominant window argmax_t Σ_h activation[h][t]
"""
from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Final

import numpy as np

from sims.ana_chi import (
    ANA_CHI_CONSTANT,
    HUB_BASIN,
    _BASIN_BY_NAME,
    coherence as _ana_chi_coherence,
    nearest_basin as _nearest_basin,
    rattling_proximity as _rattling_proximity,
)

# Canonical CAIRRN hub order (matches HUB_BASIN insertion order)
CAIRRN_HUBS: Final[tuple[str, ...]] = tuple(HUB_BASIN.keys())

# Default temporal shard count — mirrors N = 8 harmonic shards
DEFAULT_N_WINDOWS: Final[int] = 8


# ---------------------------------------------------------------------------
# Temporal shard (one time-window slot)
# ---------------------------------------------------------------------------


@dataclass
class TemporalShard:
    """One time-window slot in a hub's temporal trace."""

    t: int                  # lag (0 = now, T-1 = oldest)
    activation: float = 0.0
    recorded_at: float = field(default_factory=time.time)

    def decay(self, rate: float) -> None:
        """Multiply activation by decay rate in-place."""
        self.activation *= rate


# ---------------------------------------------------------------------------
# Per-hub temporal trace
# ---------------------------------------------------------------------------


@dataclass
class HubTemporalTrace:
    """
    CAIRRN hub's temporal trace — a sliding window of T time-shards.

    Decay rate is sourced directly from the hub's Ana-Chi basin:
        memory_decay = AnaChiBasin.memory_decay ∈ [0.90, 0.98]

    The trace is a deque; index 0 = now, index -1 = oldest.
    """

    hub_name: str
    basin_name: str
    memory_decay: float
    n_windows: int
    _windows: deque = field(repr=False)

    @classmethod
    def build(cls, hub_name: str, n_windows: int) -> "HubTemporalTrace":
        """Construct a HubTemporalTrace from a CAIRRN hub name."""
        basin_name = HUB_BASIN[hub_name]
        basin = _BASIN_BY_NAME[basin_name]
        windows: deque[TemporalShard] = deque(
            [TemporalShard(t=i) for i in range(n_windows)],
            maxlen=n_windows,
        )
        return cls(
            hub_name=hub_name,
            basin_name=basin_name,
            memory_decay=basin.memory_decay,
            n_windows=n_windows,
            _windows=windows,
        )

    # ------------------------------------------------------------------
    # Window access
    # ------------------------------------------------------------------

    @property
    def windows(self) -> list[TemporalShard]:
        """Ordered list of shards, t=0 first."""
        return list(self._windows)

    def activation_at(self, t: int) -> float:
        """Return activation at lag t (0 = now). Returns 0.0 if t out of range."""
        if 0 <= t < len(self._windows):
            return list(self._windows)[t].activation
        return 0.0

    def total_activation(self) -> float:
        return sum(w.activation for w in self._windows)

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def record(self, value: float) -> None:
        """Add activation to the t=0 (current) window."""
        windows_list = list(self._windows)
        if windows_list:
            windows_list[0].activation += value

    def advance(self) -> None:
        """
        Clock tick for this trace.

        1. Decay all existing windows by memory_decay
        2. Prepend a fresh empty window at t=0
        3. The deque maxlen drops the oldest window automatically
        4. Re-index all t values
        """
        for w in self._windows:
            w.decay(self.memory_decay)

        new_shard = TemporalShard(t=0)
        self._windows.appendleft(new_shard)
        # Re-index
        for i, w in enumerate(self._windows):
            w.t = i

    def state(self) -> dict:
        """Serialisable snapshot."""
        return {
            "hub": self.hub_name,
            "basin": self.basin_name,
            "memory_decay": self.memory_decay,
            "total_activation": round(self.total_activation(), 8),
            "windows": [
                {"t": w.t, "activation": round(w.activation, 8)}
                for w in self._windows
            ],
        }


# ---------------------------------------------------------------------------
# TemporalShardIndex
# ---------------------------------------------------------------------------


class TemporalShardIndex:
    """
    Temporal sharding index — CAIRRN-aware, Ana-Chi hosted.

    Parameters
    ----------
    n_windows : int
        Number of temporal shards per hub (default 8, mirrors harmonic N=8).
    """

    def __init__(self, n_windows: int = DEFAULT_N_WINDOWS) -> None:
        if n_windows < 2:
            raise ValueError(f"n_windows must be >= 2; got {n_windows}")
        self.n_windows = n_windows
        self._traces: dict[str, HubTemporalTrace] = {
            hub: HubTemporalTrace.build(hub, n_windows)
            for hub in CAIRRN_HUBS
        }
        self._clock: int = 0
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------

    def record(self, hub_name: str, value: float = 1.0) -> None:
        """
        Record activation for a CAIRRN hub at t=0 (now).

        Parameters
        ----------
        hub_name : CAIRRN hub — one of HOME, MATH, CODE, COMMANDS, agent-context
        value    : activation amount (default 1.0)
        """
        if hub_name not in self._traces:
            raise ValueError(
                f"Unknown CAIRRN hub {hub_name!r}. Valid hubs: {', '.join(CAIRRN_HUBS)}"
            )
        with self._lock:
            self._traces[hub_name].record(value)

    def advance(self, steps: int = 1) -> int:
        """
        Clock tick: advance all hub traces by `steps` temporal steps.

        At each step:
          - All activations decay by their hub's Ana-Chi memory_decay
          - A new empty window is prepended at t=0 for each hub
          - The oldest window (t=T-1) is dropped

        Returns the new clock value.
        """
        if steps < 1:
            raise ValueError(f"steps must be >= 1; got {steps}")
        with self._lock:
            for _ in range(steps):
                for trace in self._traces.values():
                    trace.advance()
                self._clock += 1
            return self._clock

    def reset(self) -> None:
        """Zero all activations and reset clock to 0."""
        with self._lock:
            for trace in self._traces.values():
                for w in trace._windows:
                    w.activation = 0.0
            self._clock = 0

    # ------------------------------------------------------------------
    # Inspection
    # ------------------------------------------------------------------

    def temporal_activation(self, hub_name: str, t: int) -> float:
        """Return activation for hub_name at temporal lag t (0 = now)."""
        if hub_name not in self._traces:
            raise ValueError(
                f"Unknown CAIRRN hub {hub_name!r}. Valid hubs: {', '.join(CAIRRN_HUBS)}"
            )
        with self._lock:
            return self._traces[hub_name].activation_at(t)

    def hub_totals(self) -> dict[str, float]:
        """
        Return total activation per CAIRRN hub (summed across all time windows).
        """
        with self._lock:
            return {
                hub: round(trace.total_activation(), 8)
                for hub, trace in self._traces.items()
            }

    def dominant_hub(self) -> str:
        """Return the CAIRRN hub with the highest total activation."""
        with self._lock:
            return max(self._traces, key=lambda h: self._traces[h].total_activation())

    def dominant_window(self) -> int:
        """
        Return the temporal lag t with the highest total activation
        summed across all CAIRRN hubs.
        """
        with self._lock:
            window_totals = np.zeros(self.n_windows, dtype=float)
            for trace in self._traces.values():
                for w in trace._windows:
                    if 0 <= w.t < self.n_windows:
                        window_totals[w.t] += w.activation
            return int(np.argmax(window_totals))

    def total_activation(self) -> float:
        """Total activation across all hubs and all time windows."""
        with self._lock:
            return sum(t.total_activation() for t in self._traces.values())

    def temporal_vector(self) -> np.ndarray:
        """
        Return the (n_hubs × n_windows) activation matrix.

        Rows  = CAIRRN hubs in CAIRRN_HUBS order.
        Cols  = temporal lags t = 0, 1, …, T-1.

        This is the joint spatial-temporal activation snapshot.
        """
        with self._lock:
            matrix = np.zeros((len(CAIRRN_HUBS), self.n_windows), dtype=float)
            for i, hub in enumerate(CAIRRN_HUBS):
                trace = self._traces[hub]
                for j, w in enumerate(list(trace._windows)):
                    if j < self.n_windows:
                        matrix[i, j] = w.activation
            return matrix

    # ------------------------------------------------------------------
    # Ana-Chi coherence
    # ------------------------------------------------------------------

    def ana_chi_coherence(self) -> float:
        """
        Temporal coherence — how centred is the current hub activation in
        Ana-Chi χ-space?

        Computes a hub-activation-weighted average χ:

            χ_eff = Σ_h (activation_h / total) × basin_χ_h

        Then returns the Ana-Chi coherence at χ_eff:

            coherence = exp(-|χ_eff - 1.5414| / 0.40)

        Returns 1.0 when all activation is at HOME (true_center = 1.5414).
        Returns lower values when activation disperses toward escape or boundary.
        Defaults to coherence(𝒜_χ) = 1.0 when the index is empty.
        """
        with self._lock:
            total = sum(t.total_activation() for t in self._traces.values())
            if total < 1e-12:
                return _ana_chi_coherence(ANA_CHI_CONSTANT)

            weighted_chi = 0.0
            for hub, trace in self._traces.items():
                basin = _BASIN_BY_NAME[trace.basin_name]
                hub_total = trace.total_activation()
                weight = hub_total / total
                weighted_chi += weight * basin.chi

            return _ana_chi_coherence(weighted_chi)

    def ana_chi_state(self) -> dict:
        """
        Current Ana-Chi state of the temporal index.

        Returns the effective χ, coherence, biphasic signal, rattling
        proximity, and the dominant hub and window.
        """
        with self._lock:
            totals = {hub: trace.total_activation() for hub, trace in self._traces.items()}
            grand_total = sum(totals.values())

            if grand_total < 1e-12:
                effective_chi = ANA_CHI_CONSTANT
                dominant = "HOME"
            else:
                dominant = max(totals, key=lambda h: totals[h])
                basin = _BASIN_BY_NAME[self._traces[dominant].basin_name]
                effective_chi = basin.chi

            coherence_val = _ana_chi_coherence(effective_chi)
            rattle = _rattling_proximity(effective_chi)
            nearest = _nearest_basin(effective_chi)

        return {
            "clock":              self._clock,
            "dominant_hub":       dominant,
            "effective_chi":      round(effective_chi, 6),
            "nearest_basin":      nearest.name,
            "coherence":          round(coherence_val, 6),
            "structural_order":   round(coherence_val, 6),
            "continuous_freedom": round(1.0 - coherence_val, 6),
            "rattling_proximity": {k: round(v, 4) for k, v in rattle.items()},
            "hub_totals":         {h: round(v, 8) for h, v in totals.items()},
        }

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def state(self) -> dict:
        """Full serialisable snapshot of the temporal index."""
        with self._lock:
            return {
                "clock":              self._clock,
                "n_windows":          self.n_windows,
                "n_hubs":             len(self._traces),
                "total_activation":   round(self.total_activation(), 8),
                "dominant_hub":       self.dominant_hub() if self.total_activation() > 1e-12 else None,
                "dominant_window":    self.dominant_window(),
                "ana_chi_coherence":  round(self.ana_chi_coherence(), 6),
                "hubs":               [trace.state() for trace in self._traces.values()],
            }

    def vector_state(self) -> dict:
        """
        State snapshot including the (n_hubs × n_windows) activation matrix
        as a nested list (JSON-serialisable).
        """
        with self._lock:
            mat = self.temporal_vector()
            return {
                **self.state(),
                "hub_order": list(CAIRRN_HUBS),
                "matrix": mat.tolist(),
            }
