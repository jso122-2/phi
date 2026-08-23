# engine / mycelial_substrate.py

#source #python

> path: engine/mycelial_substrate.py  
> ext: .py  

---

# engine / mycelial_substrate.py


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
    ener

Defines: MycelialTickResult, MycelialSubstrate, as_dict, __init__, tick, node_energy, top_k_energy, edge_weight, state, edge_volatility, compute_shi, rebind, _compute_demands, _run_flows, _update_weights, _check_autophagy, _check_growth_gate, _code_activation, __repr__

---

## Semantic links

→ [[engine-mycelial-substrate]]
→ [[workers-cairrn-mycelial]]
→ [[engine-mycelial]]
→ [[mycelial-layer]]
→ [[engine-phi-session]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-engine-mycelial-substrate-md]]
→ [[cursor-ingest/2026-08-04-072347-workers-cairrn-mycelial-py]]
→ [[cursor-ingest/2026-08-04-072347-source-engine-mycelial-md]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-mycelial-substrate-py]]
→ [[cursor-ingest/2026-08-04-072347-engine-mycelial-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
