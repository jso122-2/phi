# engine / orphan_detector.py

#source #python

> path: engine/orphan_detector.py  
> ext: .py  

---

# engine / orphan_detector.py


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
    best_cluster_i

Defines: OrphanResult, OrphanDetector, to_dict, __init__, scan, summary

---

## Semantic links

→ [[engine-orphan-detector]]
→ [[tools-fix-dead-links]]
→ [[graph-linker]]
→ [[engine-arm-injector]]
→ [[scripts-inference]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-engine-orphan-detector-md]]
→ [[cursor-ingest/2026-08-04-072347-engine-coherence-daemon-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-worker-py]]
→ [[cursor-ingest/2026-08-04-072347-engine-arm-injector-py]]
→ [[cursor-ingest/2026-08-04-072347-graph-linker-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
