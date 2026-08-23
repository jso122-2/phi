# scripts / inference.py

#source #python

> path: scripts/inference.py  
> ext: .py  

---

# scripts / inference.py


SambaGNN Inference Interface
Provides a clean API for Obsidian graph orchestration tasks:
  - find_related(note_title, top_k)  → ranked list of related notes
  - suggest_links(note_title)        → notes that should be linked but aren't
  - get_clusters()                   → topic clusters across the vault
  - route_query(query_text, top_k)   → find most relevant notes for a query

When config.yaml includes a [crawler] section, the orchestrator builds from
the full filesystem UnifiedGraph (all repos + notes on ~/), gates symbols via
AutonomousGate, and falls back to the ObsidianGraph vault onl

Defines: SambaOrchestrator, __init__, _build_unified_graph, _rebuild_unified_incremental, _build_representations, refresh, node_embeddings, find_related, suggest_links, get_clusters, topology_summary, graph_snapshot, route_query, node_index_map, _title_to_id, _id_to_note

---

## Semantic links

→ [[scripts-inference]]
→ [[graph-linker]]
→ [[2026-07-13-configure-the-obsidian-graph-as-the-hub-buil]]
→ [[graph-node]]
→ [[graph-init]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-scripts-inference-md]]
→ [[cursor-ingest/2026-08-04-072347-graph-md]]
→ [[cursor-ingest/2026-08-04-072347-phi-data-obsidian-graph-py]]
→ [[cursor-ingest/2026-08-04-072347-graph-ingestion-py]]
→ [[cursor-ingest/2026-08-04-072347-source-graph-linker-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
