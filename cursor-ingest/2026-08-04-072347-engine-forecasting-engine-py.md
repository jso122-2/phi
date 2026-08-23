# engine / forecasting_engine.py

#source #python

> path: engine/forecasting_engine.py  
> ext: .py  

---

# engine / forecasting_engine.py


engine.forecasting_engine — Vault topology trend forecaster.

Reads the HealthLog time series (Euler χ, orphan_count, wikilink_count)
and produces forward forecasts using:

  1. Velocity  — first-difference of chi: Δχ = χ_t − χ_{t−1}
  2. EMA trend — exponentially weighted mean to smooth noise
  3. Forecast  — chi_{t+h} = chi_latest + h × velocity_ema

Forecast Index (from FORMULAS.md / F_FORECAST_INDEX):
    pressure      = |Δchi| / max(1, range_chi)   # normalised rate of change
    capacity      = wikilinks / max(1, notes)     # link density as headroom
    F             = min(1.0, pressur

Defines: TopologyForecast, _filter_outliers, _status_label, _direction, TopologyForecaster, to_dict, __init__, forecast, summary, _ema_series

---

## Semantic links

→ [[engine-forecasting-engine]]
→ [[engine-health-log]]
→ [[cognitive-forecasting-engine]]
→ [[forecasting-engine]]
→ [[mcp-server-tools-forecast]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-engine-forecasting-engine-md]]
→ [[cursor-ingest/2026-08-04-072347-source-cognitive-forecasting-engine-md]]
→ [[cursor-ingest/2026-08-04-072347-cognitive-forecasting-engine-py]]
→ [[cursor-ingest/2026-08-04-072347-cognitive-init-py]]
→ [[cursor-ingest/2026-08-04-072347-mcp-server-tools-forecast-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
