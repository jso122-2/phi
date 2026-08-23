# cognitive / forecasting_engine.py

#source #python

> path: cognitive/forecasting_engine.py  
> ext: .py  

---

# cognitive / forecasting_engine.py


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
    F near 0   → lots of headroom, system is underlo

Defines: ForecastState, _status_label, ForecastingEngine, to_dict, __init__, tick, latest, history, reset, _compute

---

## Semantic links

→ [[cognitive-forecasting-engine]]
→ [[forecasting-engine]]
→ [[cognitive-init]]
→ [[mcp-server-tools-forecast]]
→ [[live-state]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-cognitive-forecasting-engine-md]]
→ [[cursor-ingest/2026-08-04-072347-cognitive-init-py]]
→ [[cursor-ingest/2026-08-04-072347-live-state-md]]
→ [[cursor-ingest/2026-08-04-072347-source-engine-forecasting-engine-md]]
→ [[cursor-ingest/2026-08-04-072347-source-cognitive-index-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
