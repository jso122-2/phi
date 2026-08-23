"""
cognitive.forecasting_engine — DAWN Forecast Index (F = P/A).

Reconstructed from FORMULAS.md (F_FORECAST_INDEX, F_FORECAST_SMOOTHED)
and the tick-loop Cursor prompts in the vault's Keep notes.

Core formula
------------
    passion      = SCUP analog  → mean shard activation across the HarmonicIndex
    acquaintance = 1 - entropy  → focus of the activation distribution
    F            = min(1.0, passion / acquaintance)   # raw Forecast Index
    F*           = α·F + (1−α)·F*_{t−1}              # EMA-smoothed

Interpretation
--------------
    F near 0   → lots of headroom, system is underloaded, vault focus is wide
    F near 1   → pressure matches capacity, approaching saturation
    F > 1 (raw before clamp) → predicted stress exceeds available capacity
                              → system is "underreserved" for predicted load

The Forecast Index is structurally analogous to an insurer's claims-to-surplus
ratio (as noted in the pitch notes).  High F means the vault's cognitive
pressure outstrips its adaptive capacity.

Usage
-----
    engine = ForecastingEngine(harmonic_index)
    state  = engine.tick()       # call once per cycle
    print(state.forecast_index)  # 0.0 – 1.0
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from threading import Lock
from typing import Optional

import numpy as np


# ---------------------------------------------------------------------------
# EMA smoothing factor  (α = 0.3 → moderate smoothing, responsive to change)
# ---------------------------------------------------------------------------
_EMA_ALPHA: float = 0.30


@dataclass
class ForecastState:
    """
    A single Forecast Index reading.

    Attributes
    ----------
    ts            : Unix timestamp of this reading.
    passion       : Mean shard activation (P) — the "pressure" term.
    acquaintance  : 1 − normalised entropy (A) — the "capacity" term.
    entropy       : Normalised Shannon entropy of activation distribution [0, 1].
    forecast_index: Raw F = min(1.0, P/A).
    forecast_smooth: EMA-smoothed F* across successive ticks.
    n_shards      : Number of shards sampled.
    """
    ts:              float
    passion:         float
    acquaintance:    float
    entropy:         float
    forecast_index:  float
    forecast_smooth: float
    n_shards:        int

    def to_dict(self) -> dict:
        return {
            "ts":               self.ts,
            "passion":          round(self.passion, 6),
            "acquaintance":     round(self.acquaintance, 6),
            "entropy":          round(self.entropy, 6),
            "forecast_index":   round(self.forecast_index, 6),
            "forecast_smooth":  round(self.forecast_smooth, 6),
            "n_shards":         self.n_shards,
            "status":           _status_label(self.forecast_smooth),
        }


def _status_label(f_smooth: float) -> str:
    if f_smooth < 0.25:
        return "underloaded"
    if f_smooth < 0.55:
        return "nominal"
    if f_smooth < 0.80:
        return "elevated"
    return "saturated"


class ForecastingEngine:
    """
    DAWN Forecasting Engine — Forecast Index from live harmonic state.

    Parameters
    ----------
    harmonic_index : HarmonicIndex instance (from sims.harmonic).
    ema_alpha      : Smoothing factor for F* (default 0.30).
    """

    def __init__(self, harmonic_index, ema_alpha: float = _EMA_ALPHA) -> None:
        self._harmonic = harmonic_index
        self._alpha = ema_alpha
        self._f_smooth: Optional[float] = None
        self._history: list[ForecastState] = []
        self._lock = Lock()

    # ──────────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────────

    def tick(self) -> ForecastState:
        """
        Compute the Forecast Index from the current harmonic activation state.

        Returns a ForecastState and appends it to the internal history.
        Thread-safe.
        """
        activations: np.ndarray = self._harmonic.activation_vector()
        state = self._compute(activations)
        with self._lock:
            self._history.append(state)
        return state

    def latest(self) -> Optional[ForecastState]:
        """Return the most recent ForecastState, or None if tick() has not been called."""
        with self._lock:
            return self._history[-1] if self._history else None

    def history(self, n: int = 20) -> list[ForecastState]:
        """Return the last N ForecastStates, oldest first."""
        with self._lock:
            return list(self._history[-n:])

    def reset(self) -> None:
        """Clear history and reset EMA state."""
        with self._lock:
            self._history.clear()
            self._f_smooth = None

    # ──────────────────────────────────────────────────────────────────────────
    # Internal computation
    # ──────────────────────────────────────────────────────────────────────────

    def _compute(self, activations: np.ndarray) -> ForecastState:
        n = len(activations)

        # ── P: passion = mean activation (cognitive pressure) ──────────────────
        passion = float(np.mean(activations)) if n > 0 else 0.0
        passion = max(0.01, passion)

        # ── Entropy: normalised Shannon entropy of distribution ─────────────────
        total = float(np.sum(activations))
        if total > 1e-9 and n > 1:
            probs = activations / total
            # clip to avoid log(0)
            probs = np.clip(probs, 1e-10, 1.0)
            raw_entropy = float(-np.sum(probs * np.log(probs)))
            max_entropy = math.log(n)
            normalised_entropy = raw_entropy / max_entropy
        else:
            normalised_entropy = 1.0  # uniform / no signal → maximum entropy

        # ── A: acquaintance = 1 − entropy (focus = adaptive capacity) ──────────
        acquaintance = max(0.01, 1.0 - normalised_entropy)

        # ── F: raw Forecast Index ───────────────────────────────────────────────
        f_raw = min(1.0, passion / acquaintance)

        # ── F*: EMA smoothing ───────────────────────────────────────────────────
        with self._lock:
            if self._f_smooth is None:
                self._f_smooth = f_raw
            else:
                self._f_smooth = self._alpha * f_raw + (1.0 - self._alpha) * self._f_smooth
            f_smooth = self._f_smooth

        return ForecastState(
            ts=time.time(),
            passion=passion,
            acquaintance=acquaintance,
            entropy=normalised_entropy,
            forecast_index=f_raw,
            forecast_smooth=f_smooth,
            n_shards=n,
        )
