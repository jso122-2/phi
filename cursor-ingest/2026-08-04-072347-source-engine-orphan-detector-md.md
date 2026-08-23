# source / engine-orphan-detector.md

#doc #md

> path: source/engine-orphan-detector.md  
> ext: .md  

---

# engine/orphan_detector

#code #module #engine #code

> source_path: engine/orphan_detector.py  
> package: engine  
> module: engine/orphan_detector  
> hub: CODE  
> created_ts:   

---

**Package:** `engine`  
**Module:** `engine/orphan_detector`  
**Source:** `engine/orphan_detector.py`

OrphanDetector — identifies notes that are semantically adrift.

A note is an "orphan" if its maximum soft-assignment score across all K cluster
prototypes falls below `threshold`. These notes don't belong clearly to any
coherent topic region; they are the primary targets for link patching.

Public API:
    OrphanDetector(orchestrator, threshold=0.15)
    .scan(top_k_links=5) -> List[OrphanResult]

Each OrphanResult contains:
    title       Note title
    path        Absolute path to the .md file
    max_score   Highest cluster affinity (the closer to 0.0, the more adrift)
    best_cluster_id  Which cluster this note weakly belongs to
    suggestions  Link suggestions from suggest_links (may be empty)

## API

- `class OrphanResult`
- `class OrphanDetector` — Scans the vault for notes with weak cluster membership.

---

## Semantic links

→ [[index]]
→ [[graph]]
→ [[2026-07-17T02-45-15Z-OctopusTracer v1 — Full Integration Summary]]
→ [[scratch]]
→ [[graph]]

## Related notes

→ [[source/engine-arm-injector]]
→ [[source/graph-linker]]
→ [[source/scripts-inference]]
→ [[source/graph-init]]
→ [[source/tools-enrich-c7]]

— import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[engine-arm-injector]]
→ [[engine-main]]
→ [[engine-index]]
→ [[engine-coherence-daemon]]
→ [[engine-health-log]]
→ [[graph-init]]

---

## Semantic links

→ [[engine-orphan-detector]]
→ [[engine-arm-injector]]
→ [[engine-phi-session]]
→ [[graph-init]]
→ [[engine-vault-writer]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-engine-orphan-detector-py]]
→ [[cursor-ingest/2026-08-04-072347-engine-coherence-daemon-py]]
→ [[cursor-ingest/2026-08-04-072347-engine-arm-injector-py]]
→ [[cursor-ingest/2026-08-04-072347-source-md]]
→ [[cursor-ingest/2026-08-04-072347-phi-core-rank-scoring-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
