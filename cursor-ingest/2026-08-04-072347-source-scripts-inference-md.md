# source / scripts-inference.md

#doc #md

> path: source/scripts-inference.md  
> ext: .md  

---

# scripts/inference

#code #module #scripts #code

> source_path: scripts/inference.py  
> package: scripts  
> module: scripts/inference  
> hub: CODE  
> created_ts:   

---

**Package:** `scripts`  
**Module:** `scripts/inference`  
**Source:** `scripts/inference.py`

SambaGNN Inference Interface
Provides a clean API for Obsidian graph orchestration tasks:
  - find_related(note_title, top_k)  → ranked list of related notes
  - suggest_links(note_title)        → notes that should be linked but aren't
  - get_clusters()                   → topic clusters across the vault
  - route_query(query_text, top_k)   → find most relevant notes for a query

When config.yaml includes a [crawler] section, the orchestrator builds from
the full filesystem UnifiedGraph (all repos + notes on ~/), gates symbols via
AutonomousGate, and falls back to the ObsidianGraph vault only when no crawler
config is present.  All public API methods work identically in both modes.

## API

- `class SambaOrchestrator` — High-level inference wrapper for the Obsidian knowledge graph.

## Internal imports

`models`, `engine.gate`

---

## Semantic links

→ [[2026-07-13-configure-the-obsidian-graph-as-the-hub-buil]]
→ [[graph]]
→ [[graph]]
→ [[2026-07-16-011935-knowledge-graph-pre-routing]]
→ [[README]]

## Related notes

→ [[source/graph-linker]]
→ [[source/graph-init]]
→ [[source/mcp-server-tools-graph]]
→ [[source/graph-ingestion]]
→ [[source/graph-logger]]

— import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[graph-logger]]
→ [[graph-init]]
→ [[graph-node]]
→ [[mcp-server-tools-graph]]
→ [[graph-index]]
→ [[graph-worker]]

---

## Semantic links

→ [[scripts-inference]]
→ [[graph-linker]]
→ [[graph-node]]
→ [[graph-ingestion]]
→ [[graph-worker]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-scripts-inference-py]]
→ [[cursor-ingest/2026-08-04-072347-source-graph-linker-md]]
→ [[cursor-ingest/2026-08-04-072347-source-graph-ingestion-md]]
→ [[cursor-ingest/2026-08-04-072347-phi-data-unified-graph-py]]
→ [[cursor-ingest/2026-08-04-072347-source-graph-worker-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
