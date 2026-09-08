"""Forecasting tool: forecast_state (init-free)."""
from __future__ import annotations

from typing import Any

from mcp_server._state import _dom_queue, _get_forecasting_engine, _vault_hub, mcp


def forecast_state() -> dict[str, Any]:
    """
    Compute the current DAWN Forecast Index from the live harmonic activation state.

    F = P/A  (passion / acquaintance)
        passion      = mean shard activation (cognitive pressure)
        acquaintance = 1 − normalised Shannon entropy (coherence / focus)
        F*           = EMA-smoothed F across successive ticks

    Returns: passion, acquaintance, entropy, forecast_index, forecast_smooth,
             n_shards, status ('underloaded'|'nominal'|'elevated'|'saturated'), ts

    Init-free — listed in _INIT_FREE_TOOLS.
    """
    with _dom_queue.gate("forecast_state"):
        engine = _get_forecasting_engine()
        state = engine.tick()
        result = state.to_dict()
        _vault_hub.push_forecast(result)
        return result
