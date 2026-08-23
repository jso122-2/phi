# source / psspps-init.md

#doc #md

> path: source/psspps-init.md  
> ext: .md  

---

# psspps/__init__

#code #module #psspps #code

> source_path: psspps/__init__.py  
> package: psspps  
> module: psspps/__init__  
> hub: CODE  
> created_ts:   

---

**Package:** `psspps`  
**Module:** `psspps/__init__`  
**Source:** `psspps/__init__.py`

PSSPPS — Perspective-Oriented Semantic Scored Personalized Parsing Scored.

A RAG pipeline that:
  1. Infers whether retrieval is worth running  (pre-routing)
  2. Retrieves from the Obsidian knowledge vault
  3. Scores results by semantic similarity + harmonic index perspective
  4. Parses top results into structured output
  5. Infers whether RAG actually helped          (post-routing confidence)

The harmonic index activations act as the "perspective" — which attractor
basins you have been exploring biases retrieval toward related vault documents.

## Internal imports

`psspps.pipeline`, `psspps.traverser`

---

## Semantic links

→ [[psspps]]
→ [[psspps]]
→ [[FORMULAS]]
→ [[CODE]]
→ [[CODE]]

## Related notes

→ [[source/psspps-pipeline]]
→ [[source/psspps-scorer]]
→ [[source/psspps-find]]
→ [[source/psspps-retriever]]
→ [[source/psspps-traverser]]

— import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[psspps-pipeline]]
→ [[psspps-index]]
→ [[psspps-router]]
→ [[psspps-retriever]]
→ [[mcp-server-tools-search]]
→ [[psspps-scorer]]

---

## Semantic links

→ [[psspps-pipeline]]
→ [[psspps-init]]
→ [[psspps-retriever]]
→ [[mcp-server-tools-init]]
→ [[psspps-embedder]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-psspps-index-md]]
→ [[cursor-ingest/2026-08-04-072347-source-psspps-router-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-init-md]]
→ [[cursor-ingest/2026-08-04-072347-source-psspps-retriever-md]]
→ [[cursor-ingest/2026-08-04-072347-source-psspps-pipeline-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
