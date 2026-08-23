# phi / engine / cairrn / _constants.py

#source #python

> path: phi/engine/cairrn/_constants.py  
> ext: .py  

---

# phi / engine / cairrn / _constants.py

phi.engine.cairrn._constants — canonical physics and hub geometry for phi CAIRRN.

This is the single source of truth for all CAIRRN constants used in the phi
application.  Every other module in this package imports from here — nothing
is defined inline.

SHARD GEOMETRY
──────────────
Shards are assigned by the neg_exp formula:

    shard = floor(e^χ × N_SHARDS / SHARD_NORM)   clamped to [0, N_SHARDS−1]

This produces a strictly monotone map: higher χ → higher shard.  The five
phi hubs land at shards 0, 1, 2, 3, and 7.  Shards 4–6 are propagation
waveguides — they carry diffused activation fro

Defines: shard_priority, _validate

---

## Semantic links

→ [[engine-cairrn-scheduler]]
→ [[engine-bridge-factory]]
→ [[mcp-server-tools-cairrn]]
→ [[workers-cairrn-formulas]]
→ [[2026-07-13-102400-temporal-sharding-index-cairrn-aware-ana-chi-hosted]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-engine-cairrn-bridge-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-engine-cairrn-router-py]]
→ [[cursor-ingest/2026-08-04-072347-engine-cairrn-scheduler-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-engine-cairrn-init-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-engine-hub-ring-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
