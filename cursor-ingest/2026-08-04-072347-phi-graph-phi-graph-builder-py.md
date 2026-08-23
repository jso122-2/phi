# phi / graph / phi_graph_builder.py

#source #python

> path: phi/graph/phi_graph_builder.py  
> ext: .py  

---

# phi / graph / phi_graph_builder.py

phi.graph.phi_graph_builder — topology-aware music graph construction.

Extends `PhiGraph` (which builds H from CLAP embeddings) with:

  1. Typed music edges wired into an ObsidianGraph-compatible nx.DiGraph:
       semantic   — CLAP cosine similarity > threshold
       wikilink   — Camelot harmonic key compatibility (±1 on wheel, relative)
       temporal   — BPM proximity |BPM_i − BPM_j| < bpm_window
       tag_overlap — shared mood / genre tags from Phi annotations

  2. TopologicalGraph built over those edges → χ, β₀, β₁, ∂₁, ∂₂

  3. D4InjectionLayer — `nn.Linear(1, d_model)` that additi

Defines: _parse_camelot, camelot_compatible, PhiGraphBuilder, D4InjectionLayer, D4InjectionLayer, __init__, build_topology, _collect_tags, __init__, forward, parameter_count, __init__

---

## Semantic links

→ [[graph-node]]
→ [[graph-logger]]
→ [[2026-07-17T01-33-09Z-CLAPProjection and PhiGraph — DAWN bridge layer]]
→ [[graph-init]]
→ [[README]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-graph-phi-graph-gnn-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-init-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-metadata-schema-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-data-unified-graph-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-graph-phi-graph-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
