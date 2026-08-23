"""
engine.forecasting_engine — Vault topology trend forecaster.

Reads the HealthLog time series (Euler χ, orphan_count, wikilink_count)
and produces forward forecasts using:

  1. Velocity  — first-difference of chi: Δχ = χ_t − χ_{t−1}
  2. EMA trend — exponentially weighted mean to smooth noise
  3. Forecast  — chi_{t+h} = chi_latest + h × velocity_ema

Forecast Index (from FORMULAS.md / F_FORECAST_INDEX):
    pressure      = |Δchi| / max(1, range_chi)   # normalised rate of change
    capacity      = wikilinks / max(1, notes)     # link density as headroom
    F             = min(1.0, pressure / capacity)
    F*            = α·F + (1−α)·F*_{t−1}          # EMA-smoothed

The Forecast Index answers: "Is the vault's topological drift outpacing
its ability to self-organise via wikilinks?"

Public API
----------
    fe = TopologyForecaster()
    report = fe.forecast(horizon=3)
    print(report["forecast_chi"])   # [chi_t+1, chi_t+2, chi_t+3]
    print(report["forecast_index"]) # F*
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

from engine.health_log import HealthLog


# EMA decay for velocity and Forecast Index smoothing
_EMA_ALPHA: float = 0.35
_MIN_SNAPSHOTS: int = 2   # need at least two points for a velocity


@dataclass
class TopologyForecast:
    """
    A topology forecast report.

    Attributes
    ----------
    ts              : Unix timestamp of this report.
    n_snapshots     : Number of HealthLog rows used.
    chi_latest      : Most recent Euler χ.
    velocity        : EMA-smoothed Δχ per snapshot (positive = growing).
    forecast_chi    : Projected chi for each step in the horizon.
    pressure        : Normalised rate of topological drift [0, 1].
    capacity        : Wikilink density (links / notes) — headroom proxy.
    forecast_index  : F = min(1.0, pressure / capacity).
    forecast_smooth : EMA-smoothed F*.
    direction       : 'improving' | 'stable' | 'degrading' based on velocity.
    horizon         : Number of steps forecast.
    """
    ts:             float
    n_snapshots:    int
    chi_latest:     float
    velocity:       float
    forecast_chi:   List[float]
    pressure:       float
    capacity:       float
    forecast_index: float
    forecast_smooth: float
    direction:      str
    horizon:        int

    def to_dict(self) -> Dict:
        return {
            "ts":              self.ts,
            "n_snapshots":     self.n_snapshots,
            "chi_latest":      round(self.chi_latest, 3),
            "velocity":        round(self.velocity, 4),
            "forecast_chi":    [round(c, 3) for c in self.forecast_chi],
            "pressure":        round(self.pressure, 4),
            "capacity":        round(self.capacity, 4),
            "forecast_index":  round(self.forecast_index, 4),
            "forecast_smooth": round(self.forecast_smooth, 4),
            "direction":       self.direction,
            "horizon":         self.horizon,
            "status":          _status_label(self.forecast_smooth),
        }


def _filter_outliers(series: List[float], k: float = 3.0) -> List[float]:
    """
    Remove values more than k × IQR from the median.

    If the series is too short to compute IQR (<= 3 values), returns as-is.
    This protects velocity calculation from single anomalous chi snapshots
    caused by formula changes or corrupted data.
    """
    if len(series) <= 3:
        return series
    sorted_vals = sorted(series)
    n = len(sorted_vals)
    q1 = sorted_vals[n // 4]
    q3 = sorted_vals[(3 * n) // 4]
    iqr = q3 - q1
    if iqr == 0:
        return series  # all identical — no outlier removal possible
    lo = q1 - k * iqr
    hi = q3 + k * iqr
    filtered = [v for v in series if lo <= v <= hi]
    return filtered if len(filtered) >= _MIN_SNAPSHOTS else series


def _status_label(f: float) -> str:
    if f < 0.20:
        return "stable"
    if f < 0.50:
        return "drifting"
    if f < 0.80:
        return "stressed"
    return "critical"


def _direction(velocity: float, threshold: float = 0.05) -> str:
    if velocity > threshold:
        return "growing"          # χ increasing = more complex / richer topology
    if velocity < -threshold:
        return "shrinking"        # χ decreasing = simplifying / fragmentation
    return "stable"


class TopologyForecaster:
    """
    Vault topology trend forecaster backed by the HealthLog.

    Parameters
    ----------
    db_path  : Optional path to the SQLite DB (defaults to HealthLog default).
    ema_alpha: Smoothing factor for velocity and F* EMA (default 0.35).
    """

    def __init__(self, db_path=None, ema_alpha: float = _EMA_ALPHA) -> None:
        self._log = HealthLog(db_path=db_path) if db_path else HealthLog()
        self._alpha = ema_alpha
        self._f_smooth: Optional[float] = None

    # ──────────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────────

    def forecast(self, horizon: int = 3, lookback: int = 20) -> TopologyForecast:
        """
        Compute velocity and project chi forward by `horizon` steps.

        Parameters
        ----------
        horizon  : Number of future snapshots to project (default 3).
        lookback : Number of recent HealthLog rows to consider (default 20).

        Returns
        -------
        TopologyForecast dataclass.  Call .to_dict() for JSON-serialisable output.

        Raises
        ------
        ValueError if fewer than 2 snapshots exist in the HealthLog.
        """
        rows = self._log.recent(n=lookback)
        if len(rows) < _MIN_SNAPSHOTS:
            raise ValueError(
                f"Need at least {_MIN_SNAPSHOTS} snapshots to forecast. "
                f"Currently have {len(rows)}. Run the coherence daemon or "
                f"call samba_record_coherence() to populate the log."
            )

        # rows are newest-first; reverse to chronological order
        rows = list(reversed(rows))

        chi_series = [r["chi"] for r in rows if r.get("chi") is not None]
        if len(chi_series) < _MIN_SNAPSHOTS:
            raise ValueError("Not enough non-null chi values in the log.")

        # ── Outlier filtering: IQR method ───────────────────────────────────────
        # Remove extreme jumps caused by formula changes or anomalous snapshots.
        chi_series = _filter_outliers(chi_series)
        if len(chi_series) < _MIN_SNAPSHOTS:
            raise ValueError(
                "After outlier filtering fewer than 2 chi values remain. "
                "The recorded chi values may be inconsistent — check that "
                "samba_record_coherence uses a stable formula."
            )

        # ── Velocity: EMA of first-differences ─────────────────────────────────
        deltas = [chi_series[i] - chi_series[i - 1] for i in range(1, len(chi_series))]
        velocity = self._ema_series(deltas)

        chi_latest = chi_series[-1]
        chi_range = max(chi_series) - min(chi_series) if len(chi_series) > 1 else 1.0

        # ── Projected chi ───────────────────────────────────────────────────────
        forecast_chi = [
            chi_latest + (step + 1) * velocity
            for step in range(horizon)
        ]

        # ── Forecast Index ──────────────────────────────────────────────────────
        latest_row = rows[-1]
        notes = max(1, latest_row.get("notes") or 1)
        wikilinks = max(0, latest_row.get("wikilink_count") or 0)

        # pressure = normalised rate of topological drift
        pressure = min(1.0, abs(velocity) / max(1.0, chi_range))

        # capacity = wikilink density (how well-linked the vault is)
        capacity = max(0.01, min(1.0, wikilinks / notes))

        f_raw = min(1.0, pressure / capacity)

        # EMA smooth across successive forecast() calls
        if self._f_smooth is None:
            self._f_smooth = f_raw
        else:
            self._f_smooth = self._alpha * f_raw + (1.0 - self._alpha) * self._f_smooth

        return TopologyForecast(
            ts=time.time(),
            n_snapshots=len(rows),
            chi_latest=chi_latest,
            velocity=velocity,
            forecast_chi=forecast_chi,
            pressure=pressure,
            capacity=capacity,
            forecast_index=f_raw,
            forecast_smooth=self._f_smooth,
            direction=_direction(velocity),
            horizon=horizon,
        )

    def summary(self, lookback: int = 20) -> Dict:
        """Convenience: forecast(horizon=3) as a plain dict."""
        try:
            return self.forecast(horizon=3, lookback=lookback).to_dict()
        except ValueError as e:
            return {"error": str(e)}

    # ──────────────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _ema_series(self, values: List[float]) -> float:
        """Return the EMA of a series of floats using self._alpha."""
        if not values:
            return 0.0
        ema = values[0]
        for v in values[1:]:
            ema = self._alpha * v + (1.0 - self._alpha) * ema
        return ema
