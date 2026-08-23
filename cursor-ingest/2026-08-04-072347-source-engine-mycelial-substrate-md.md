# source / engine-mycelial-substrate.md

#doc #md

> path: source/engine-mycelial-substrate.md  
> ext: .md  

---

# engine/mycelial_substrate

#code #module #engine #code

> source_path: engine/mycelial_substrate.py  
> package: engine  
> module: engine/mycelial_substrate  
> hub: CODE  
> created_ts:   

---

**Package:** `engine`  
**Module:** `engine/mycelial_substrate`  
**Source:** `engine/mycelial_substrate.py`

MycelialSubstrate — living metabolic layer for the phi node graph.

Connects workers/cairrn/mycelial.py (pure formulas) to the real phi system.
One substrate instance wraps one PhiGraphSnapshot and runs per-tick
metabolism across all track nodes and their similarity edges.

Architecture
------------
The PhiGraphSnapshot provides:
    tracks  : N SongNodes  →  one energy state per node
    H       : (N, 256)     →  cosine similarity used for Hebbian/growth gate
    A       : (N, N)       →  binary adjacency matrix → initial edge weights

Substrate mutable state (evolves on each tick):
    energy        : np.ndarray (N,)   — node energy ∈ [0, E_max]
    weights       : np.ndarray (N, N) — edge weights (float, evolved from A)
    starved_ticks : np.ndarray (N,)   — consecutive starvation ticks per node
    tick_count    : int                — total ticks run

Tick lifecycle (one gate-open = one tick):
    1. demand()           — D_i from CODE hub pressure + embedding signals
    2. nutrient_alloc()   — softmax budget → allocation per node
    3. metabolise()       — energy_i ← clamp(energy + η·nutrients - cost, 0, E_max)
    4. passive_flow()     — energy diffusion along every edge
    5. active_flow()      — bloom/starve transport for high/low energy nodes
    6. weight_update()    — Hebbian + decay + entropy per edge
    7. shimmer_decay()    — cold edge degradation (edges not recently active)
    8. autophagy_trigger()— flag nodes held below θ_prune for τ_ticks
    9. growth_gate()      — allow new edges when all four conditions pass

Wiring
------
Called from CAIRRNDispatcher via PhiActionKind.MYCELIAL_TICK:
    dispatcher.enqueue(PhiAction(PhiActionKind.MYCELIA

---

## Semantic links

→ [[engine-mycelial-substrate]]
→ [[workers-cairrn-mycelial]]
→ [[engine-mycelial]]
→ [[mycelial-layer]]
→ [[mycelial-layer]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-engine-mycelial-substrate-py]]
→ [[cursor-ingest/2026-08-04-072347-source-engine-mycelial-md]]
→ [[cursor-ingest/2026-08-04-072347-workers-cairrn-mycelial-py]]
→ [[cursor-ingest/2026-08-04-072347-source-workers-cairrn-mycelial-md]]
→ [[cursor-ingest/2026-08-04-072347-source-sims-index-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
