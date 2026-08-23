# source / psspps-router.md

#doc #md

> path: source/psspps-router.md  
> ext: .md  

---

# psspps/router

#code #module #psspps #code

> source_path: psspps/router.py  
> package: psspps  
> module: psspps/router  
> hub: CODE  
> created_ts:   

---

**Package:** `psspps`  
**Module:** `psspps/router`  
**Source:** `psspps/router.py`

RAG routing for PSSPPS — two decision points.

Pre-routing   — given the raw query, should we retrieve at all?
Post-routing  — given the retrieval scores, did RAG actually help?

Both return a (decision: bool, confidence: float) pair so callers can
propagate uncertainty through the pipeline.

## API

- `def should_retrieve` — Pre-routing: decide whether to run retrieval for this query.
- `def rag_was_useful` — Post-routing: given the retrieval scores, estimate whether RAG helped.

---

## Semantic links

→ [[2026-07-16-011935-knowledge-graph-pre-routing]]
→ [[psspps]]
→ [[psspps]]
→ [[CODE]]
→ [[CODE]]

## Related notes

→ [[source/psspps-pipeline]]
→ [[source/psspps-find]]
→ [[source/psspps-init]]
→ [[source/mcp-server-tools-search]]
→ [[source/psspps-retriever]]

— import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[psspps-pipeline]]
→ [[psspps-init]]
→ [[psspps-index]]
→ [[psspps-retriever]]
→ [[mcp-server-tools-search]]
→ [[psspps-embedder]]

---

## Semantic links

→ [[psspps-router]]
→ [[psspps-pipeline]]
→ [[psspps-init]]
→ [[psspps-find]]
→ [[psspps-traverser]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-psspps-router-py]]
→ [[cursor-ingest/2026-08-04-072347-source-psspps-init-md]]
→ [[cursor-ingest/2026-08-04-072347-source-psspps-index-md]]
→ [[cursor-ingest/2026-08-04-072347-source-psspps-pipeline-md]]
→ [[cursor-ingest/2026-08-04-072347-source-psspps-traverser-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
