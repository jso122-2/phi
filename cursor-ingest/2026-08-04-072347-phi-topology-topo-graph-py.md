# phi / topology / topo_graph.py

#source #python

> path: phi/topology/topo_graph.py  
> ext: .py  

---

# phi / topology / topo_graph.py


TopologicalGraph
Algebraic topology wrapper over ObsidianGraph.

Decomposes the underlying nx.DiGraph into the primitive simplex hierarchy:
    0-simplices  → Vertex   (all note nodes)
    1-simplices  → Edge     (typed directed links)
    2-simplices  → Triangle (closed triples — smallest cycles)

Computes and caches the topological invariants:
    χ  = V − E + T      (Euler characteristic)
    β₀                  (connected components, 0th Betti number)
    β₁ = β₀ − χ        (independent cycles, 1st Betti number)

Also builds the boundary operators ∂₁ and ∂₂, and supports the semantic
simp

Defines: TopologicalGraph, __init__, build, _build_vertices, _build_edges, _build_triangles, _build_invariant, vertices, edges, triangles, edges_by_type, invariant, boundary_operator, semantic_simplex_complex, semantic_invariant, connected_components, largest_component_fraction, snapshot

---

## Semantic links

→ [[topo-hub]]
→ [[graph-init]]
→ [[graph-worker]]
→ [[graph-node]]
→ [[mcp-server-tools-graph]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-topology-primitives-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-topology-init-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-topo-graph-py]]
→ [[cursor-ingest/2026-08-04-072347-graph-topo-graph-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-graph-phi-graph-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
