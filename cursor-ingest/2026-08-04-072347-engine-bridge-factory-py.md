# engine / bridge_factory.py

#source #python

> path: engine/bridge_factory.py  
> ext: .py  

---

# engine / bridge_factory.py


CAIRRN Bridge — connects OctopusTracer arm scores to the harmonic index.

Arm → shard mapping (8 arms → 8 shards, one-to-one):

    PRUNE     → shard 0   (HOME     basin 1.96)
    GRAFT     → shard 1   (MATH     basin 3.92)
    CLUSTER   → shard 2   (MATH     basin 5.88)
    RANK      → shard 3   (CODE     basin 7.84)
    TAG       → shard 4   (CODE     basin 9.80)
    RESURFACE → shard 5   (COMMANDS basin 11.76)
    MERGE     → shard 6   (agent-context basin 13.72)
    SPROUT    → shard 7   (agent-context basin 15.68)

ingest_arm_scores() mutates the harmonic index WITHOUT calling propagate 

Defines: IncoherenceEvent, CAIRRNBridge, make_bridge, __init__, ingest_arm_scores, ingest_topology, record_spawn_coherence, clear_incoherence_events, incoherence_events, step_tick, __repr__

---

## Semantic links

→ [[engine-bridge-factory]]
→ [[engine-cairrn-bridge]]
→ [[engine-init]]
→ [[2026-07-13-102400-temporal-sharding-index-cairrn-aware-ana-chi-hosted]]
→ [[mcp-server-tools-harmonic]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-engine-bridge-factory-md]]
→ [[cursor-ingest/2026-08-04-072347-source-engine-cairrn-bridge-md]]
→ [[cursor-ingest/2026-08-04-072347-engine-init-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-engine-cairrn-bridge-py]]
→ [[cursor-ingest/2026-08-04-072347-engine-cairrn-bridge-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
