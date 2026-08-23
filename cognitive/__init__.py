"""
cognitive — DAWN cognitive subsystems for the vault.

Submodules
----------
forecasting_engine   Core Forecast Index (F = P/A) with EMA smoothing,
                     computed live from the HarmonicIndex activation state.
"""
from .forecasting_engine import ForecastingEngine, ForecastState

__all__ = ["ForecastingEngine", "ForecastState"]
