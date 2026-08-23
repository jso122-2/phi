# source / engine-coherence-gate.md

#doc #md

> path: source/engine-coherence-gate.md  
> ext: .md  

---

# engine/coherence_gate

#code #module #engine #code

> source_path: engine/coherence_gate.py  
> package: engine  
> module: engine/coherence_gate  
> hub: CODE  
> created_ts:   

---

**Package:** `engine`  
**Module:** `engine/coherence_gate`  
**Source:** `engine/coherence_gate.py`

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
    4. Quality — has a docstring ≥ min_docstring_len chars
    5. Default → DEFER

Every decision is persisted to logs/gate.db for inspection.

## API

- `class GateAction`
- `class GateDecision`
- `class AutonomousGate` — Rule-based + embedding-based admission gate for the unified graph.

---

## Semantic links

→ [[2025-05-19-104531-artifical-anderson-schema-logic-matrix-19-5-25]]
→ [[2026-01-18-014905-no-greedy-pathfinding]]
→ [[graph]]
→ [[graph]]
→ [[logger]]

## Related notes

→ [[source/engine-gate]]
→ [[source/graph-init]]
→ [[source/engine-cairrn-dispatch]]
→ [[source/engine-coherence-daemon]]
→ [[source/engine-vault-garden]]

— import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[engine-gate]]
→ [[engine-index]]
→ [[engine-main]]
→ [[index]]
→ [[engine-health-log]]
→ [[engine-init]]

---

## Semantic links

→ [[engine-coherence-gate]]
→ [[engine-gate]]
→ [[engine-coherence-daemon]]
→ [[engine-init]]
→ [[engine-cairrn-dispatch]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-engine-coherence-gate-py]]
→ [[cursor-ingest/2026-08-04-072347-source-engine-gate-md]]
→ [[cursor-ingest/2026-08-04-072347-source-engine-init-md]]
→ [[cursor-ingest/2026-08-04-072347-engine-gate-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-gate-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
