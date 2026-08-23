# source / engine-bridge-factory.md

#doc #md

> path: source/engine-bridge-factory.md  
> ext: .md  

---

# engine/bridge_factory

#code #module #engine #code

> source_path: engine/bridge_factory.py  
> package: engine  
> module: engine/bridge_factory  
> hub: CODE  
> created_ts:   

---

**Package:** `engine`  
**Module:** `engine/bridge_factory`  
**Source:** `engine/bridge_factory.py`

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

ingest_arm_scores() mutates the harmonic index WITHOUT calling propagate —
hub clocks are NOT stepped, no incoherence events are generated.

Topology key formats accepted by ingest_topology():
    "topology"       — full topology dict (node_id → adjacency list or embedding)
    "graph_snapshot" — graph snapshot dict (same semantics, different key name)

Both produce identical hub activations for the same underlying data.

## API

- `class IncoherenceEvent` — Recorded when coherence drops below threshold before a bridge reset.
- `class CAIRRNBridge` — Routes OctopusTracer arm scores into the harmonic index shards.
- `def make_bridge` — Construct a CAIRRNBridge with a fresh (or provided) HarmonicIndex.

## Internal imports

`sims.harmonic`

---

## Semantic links

→ [[2026-07-13-102400-temporal-sharding-index-cairrn-aware-ana-chi-hosted]]
→ [[2026-07-17T02-45-15Z-OctopusTracer v1 — Full Integration Summary]]
→ [[harmonic-index]]
→ [[harmonic-index]]
→ [[cairrn]]

## Related notes

→ [[source/engine-init]]
→ [[source/engine-cairrn-bridge]]
→ [[source/engine-arm-injector]]
→ [[source/mcp-server-tools-harmonic]]
→ [[source/models-arms]]

— import index  

*Imported by `gr

---

## Semantic links

→ [[engine-bridge-factory]]
→ [[engine-cairrn-bridge]]
→ [[engine-init]]
→ [[engine-arm-injector]]
→ [[mcp-server-tools-harmonic]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-engine-bridge-factory-py]]
→ [[cursor-ingest/2026-08-04-072347-source-engine-cairrn-bridge-md]]
→ [[cursor-ingest/2026-08-04-072347-engine-init-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-engine-cairrn-bridge-py]]
→ [[cursor-ingest/2026-08-04-072347-engine-cairrn-bridge-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
