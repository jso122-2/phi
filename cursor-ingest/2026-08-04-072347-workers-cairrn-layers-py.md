# workers / cairrn / layers.py

#source #python

> path: workers/cairrn/layers.py  
> ext: .py  

---

# workers / cairrn / layers.py


CAIRRN three-layer pipeline dataclasses and runner functions.

Layer 1 — Ana-Chi Modulation   : ModulationResult, ana_chi_modulate
Layer 2 — neg_exp Sharding     : ShardSignal, neg_exp_shard
Layer 3 — Coherence Enforcement: CoherenceResult, measure_coherence


Defines: ModulationResult, ana_chi_modulate, ShardSignal, neg_exp_shard, CoherenceResult, measure_coherence, damping_applied, fixed_point_reached

---

## Semantic links

→ [[workers-cairrn-layers]]
→ [[workers-cairrn-formulas]]
→ [[engine-cairrn-scheduler]]
→ [[workers-cairrn-worker]]
→ [[engine-cairrn-bridge]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-tests-test-cairrn-py]]
→ [[cursor-ingest/2026-08-04-072347-source-workers-cairrn-layers-md]]
→ [[cursor-ingest/2026-08-04-072347-phi-engine-cairrn-init-py]]
→ [[cursor-ingest/2026-08-04-072347-workers-cairrn-worker-py]]
→ [[cursor-ingest/2026-08-04-072347-workers-cairrn-formulas-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
