# engine / coherence_gate.py

#source #python

> path: engine/coherence_gate.py  
> ext: .py  

---

# engine / coherence_gate.py


AutonomousGate — decides whether a newly discovered SymbolNode is worth
admitting to the UnifiedGraph.

Three outcomes for every symbol:
    ADMIT   Add to graph immediately
    DEFER   Re-evaluate next crawl cycle (stored in a SQLite pending queue)
    SKIP    Discard permanently (path/content excluded)

Decision rules (first match wins):
    1. Hard skip — excluded path pattern or binary/tiny content
    2. Connectivity — symbol imports ≥ N names already in the graph name index
    3. Novelty — embedding cosine distance to nearest node > threshold
    4. Quality — has a docstring ≥ min_docs

Defines: GateAction, GateDecision, AutonomousGate, __init__, evaluate, evaluate_batch, flush_pending, update_name_index, summary, _run_rules, _hard_skip, _init_db, _log, __del__

---

## Semantic links

→ [[engine-coherence-gate]]
→ [[graph-init]]
→ [[2025-05-19-104531-artifical-anderson-schema-logic-matrix-19-5-25]]
→ [[engine-gate]]
→ [[engine-coherence-daemon]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-engine-coherence-gate-md]]
→ [[cursor-ingest/2026-08-04-072347-phi-data-crawler-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-data-unified-graph-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-data-symbol-node-py]]
→ [[cursor-ingest/2026-08-04-072347-graph-init-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
