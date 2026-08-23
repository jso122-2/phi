# phi / topology / __init__.py

#source #python

> path: phi/topology/__init__.py  
> ext: .py  

---

# phi / topology / __init__.py


topology — Semantic Topology Primitives and Topological Graph

Public surface:

    Primitives (pure Python, zero-dependency):
        from topology import Vertex, Edge, Triangle, Simplex
        from topology import TopologicalInvariant
        from topology import BoundaryOperator

    Topological graph (wraps ObsidianGraph):
        from topology import TopologicalGraph

Typical usage:
    obs_graph = ObsidianGraph(vault_path=...)
    obs_graph.build()

    topo = TopologicalGraph(obs_graph)
    topo.build()

    inv = topo.invariant        # TopologicalInvariant: χ, β₀, β₁, V, E, T
    op

---

## Semantic links

→ [[graph-init]]
→ [[mcp-server-tools-graph]]
→ [[graph-worker]]
→ [[graph-ingestion]]
→ [[graph-node]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-topology-primitives-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-topology-topo-graph-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-graph-init-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-data-obsidian-graph-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-topo-graph-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
