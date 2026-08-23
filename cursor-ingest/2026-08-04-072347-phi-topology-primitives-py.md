# phi / topology / primitives.py

#source #python

> path: phi/topology/primitives.py  
> ext: .py  

---

# phi / topology / primitives.py


Semantic Topology Primitives
Algebraic topology primitives for the Obsidian knowledge graph.

    0-simplex  Vertex              — a note node
    1-simplex  Edge                — typed directed connection
    2-simplex  Triangle            — closed triple (transitive cluster seed)
    k-simplex  Simplex             — general k-chain
    TopologicalInvariant           — χ, β₀, β₁ snapshot
    BoundaryOperator               — ∂₁, ∂₂ boundary maps

The primitives are pure Python dataclasses — zero torch, zero networkx dependencies.
They are instantiated by TopologicalGraph from the underlying n

Defines: Vertex, Edge, Triangle, Simplex, TopologicalInvariant, BoundaryOperator, __repr__, boundary, __repr__, boundary_edges, __repr__, dimension, faces, __repr__, from_counts, as_dict, __repr__, __init__, delta_1, delta_2, verify_homology, betti_ranks

---

## Semantic links

→ [[graph-init]]
→ [[mcp-server-tools-graph]]
→ [[topo-hub]]
→ [[graph-worker]]
→ [[engine-coherence-gate]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-topology-init-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-topology-topo-graph-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-data-unified-graph-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-data-symbol-node-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-graph-phi-graph-gnn-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
