# source / engine-forecasting-engine.md

#doc #md

> path: source/engine-forecasting-engine.md  
> ext: .md  

---

# engine/forecasting_engine

#code #module #engine #code

> source_path: engine/forecasting_engine.py  
> package: engine  
> module: engine/forecasting_engine  
> hub: CODE  
> created_ts:   

---

**Package:** `engine`  
**Module:** `engine/forecasting_engine`  
**Source:** `engine/forecasting_engine.py`

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

## API

- `class TopologyForecast` — A topology forecast report.
- `def _filter_outliers` — Remove values more than k × IQR from the median.
- `def _status_label`
- `def _direction`
- `class TopologyForecaster` — Vault topology trend forecaster backed by the HealthLog.

## Internal imports

`engine.health_log`

---

## Semantic links

→ [[forecasting-engine]]
→ [[2025-10-05-034506-monday-formula-sheet-sheet]]
→ [[2025-10-01-061550-2026-01-07t04-11-40-723-11-00]]
→ [[2025-09-04-063034-2025-09-04t16-30-34-670-10-00]]
→ [[2025-05-27-174633-2025-05-28t03-46-33-990-10-00]]

## Related notes

→ [[source/cognitive-forecasting-engine]]
→ [[source/engine-health-log]]
→ [[source/mcp-server-tools-for

---

## Semantic links

→ [[engine-forecasting-engine]]
→ [[mcp-server-tools-forecast]]
→ [[engine-health-log]]
→ [[cognitive-forecasting-engine]]
→ [[engine-index]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-engine-forecasting-engine-py]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-forecast-md]]
→ [[cursor-ingest/2026-08-04-072347-source-cognitive-forecasting-engine-md]]
→ [[cursor-ingest/2026-08-04-072347-mcp-server-tools-forecast-py]]
→ [[cursor-ingest/2026-08-04-072347-source-engine-cairrn-scheduler-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
