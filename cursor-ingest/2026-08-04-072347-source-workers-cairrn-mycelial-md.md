# source / workers-cairrn-mycelial.md

#doc #md

> path: source/workers-cairrn-mycelial.md  
> ext: .md  

---

# workers/cairrn/mycelial

#code #module #workers #code

> source_path: workers/cairrn/mycelial.py  
> package: workers  
> module: workers/cairrn/mycelial  
> hub: CODE  
> created_ts:   

---

**Package:** `workers`  
**Module:** `workers/cairrn/mycelial`  
**Source:** `workers/cairrn/mycelial.py`

CAIRRN Mycelial Formula Set — pure math, no state.

Implements the full metabolic substrate formula set from:
    "Rationale: Mycelial Intelligence in DAWN"
    (Keep note, 2026-07-13 → keep/2025-08-09-024311-*.md → mycelial-layer.md)

The mycelial layer treats the CAIRRN node graph as a living metabolic
substrate.  Every node carries an energy state; every edge is a conductive
channel.  Each tick the system computes demand, allocates nutrients, converts
them to energy, diffuses and transports resources, updates edge weights, and
applies growth/decay mechanics.

All functions here are **pure** — they operate on float scalars or lists and
return floats or lists.  No node state, no class instances, no side effects.
State lives in the calling substrate (tick engine, CAIRRNDispatcher, etc.).

Formula source: mycelial-layer.md — the canonical vault node for this spec.

## API

- `def demand` — Compute the metabolic demand score for a single node.
- `def nutrient_alloc` — Distribute a global nutrient budget proportionally to node demand.
- `def metabolise` — Convert incoming nutrients into node energy, subtract basal cost, clamp.
- `def conductance` — Compute edge conductance from edge weight via sigmoid.
- `def passive_flow` — Energy diffusion from node i to node j along edge ij.
- `def active_flow` — Active transport: blooms push energy outward; starved nodes pull it in.
- `def weight_update` — Compute the weight delta for edge ij over one tick.
- `def shimmer_decay` — Exponential decay of an edge weight over unused time.
- `def growth_gate` — Check all four Growth Gate conditions before forming a new edge.
- `def autophagy_trigger` — Determine whether a node should self-di

---

## Semantic links

→ [[workers-cairrn-mycelial]]
→ [[workers-cairrn-init]]
→ [[workers-cairrn-worker]]
→ [[workers-index]]
→ [[workers-cairrn-desktop]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-workers-cairrn-init-md]]
→ [[cursor-ingest/2026-08-04-072347-source-workers-cairrn-worker-md]]
→ [[cursor-ingest/2026-08-04-072347-source-workers-cairrn-z-space-md]]
→ [[cursor-ingest/2026-08-04-072347-source-workers-cairrn-constants-md]]
→ [[cursor-ingest/2026-08-04-072347-source-workers-index-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
