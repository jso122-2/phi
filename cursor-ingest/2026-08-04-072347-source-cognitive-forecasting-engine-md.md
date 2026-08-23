# source / cognitive-forecasting-engine.md

#doc #md

> path: source/cognitive-forecasting-engine.md  
> ext: .md  

---

# cognitive/forecasting_engine

#code #module #cognitive #code

> source_path: cognitive/forecasting_engine.py  
> package: cognitive  
> module: cognitive/forecasting_engine  
> hub: CODE  
> created_ts:   

---

**Package:** `cognitive`  
**Module:** `cognitive/forecasting_engine`  
**Source:** `cognitive/forecasting_engine.py`

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

## API

- `class ForecastState` — A single Forecast Index reading.
- `def _status_label`
- `class ForecastingEngine` — DAWN Forecasting Engine — Forecast Index from live harmonic state.

---

## Semantic links

→ [[forecasting-engine]]
→ [[live-state]]
→ [[2025-09-04-060526-2025-09-04t16-05-28-022-10-00]]
→ [[2026-01-16-174325-2026-04-17t00-33-44-969-10-00]]
→ [[2025-10-01-061550-2026-01-07t04-11-40-723-11-00]]

## Related notes

→ [[source/cognitive-init]]
→ [[s

---

## Semantic links

→ [[cognitive-forecasting-engine]]
→ [[cognitive-init]]
→ [[forecasting-engine]]
→ [[engine-forecasting-engine]]
→ [[mcp-server-tools-forecast]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-cognitive-forecasting-engine-py]]
→ [[cursor-ingest/2026-08-04-072347-cognitive-init-py]]
→ [[cursor-ingest/2026-08-04-072347-source-cognitive-index-md]]
→ [[cursor-ingest/2026-08-04-072347-source-engine-forecasting-engine-md]]
→ [[cursor-ingest/2026-08-04-072347-source-index-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
