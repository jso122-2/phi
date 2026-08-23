# graph / ingestion.py

#source #python

> path: graph/ingestion.py  
> ext: .py  

---

# graph / ingestion.py


Ingestion pipeline — embed, link, classify, write, manifest.

The single reusable core for pushing any document collection into the
Obsidian vault graph.  Works as a library (imported by keep_ingest.py,
ingest.py, or future importers) or stand-alone.

Architecture
------------
  IngestedDoc      — input: one document to ingest (title, text, tags, meta)
  IngestionManifest — output: written nodes, hub counts, semantic stats
  IngestionPipeline — orchestrator

Pipeline stages per document
-----------------------------
  1. Embed       — MiniLM all-MiniLM-L6-v2 vector (sentence-transformers or
 

Defines: IngestedDoc, WrittenNode, IngestionManifest, _build_encoder, _slug, _cosine_top_k, _render_node, IngestionPipeline, write_import_index, summary, to_dict, __init__, run, _make_stem, _write_manifest, _st_encode

---

## Semantic links

→ [[graph-ingestion]]
→ [[tools-keep-ingest]]
→ [[tools-ingest]]
→ [[graph-source-extractor]]
→ [[graph-node]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-graph-ingestion-md]]
→ [[cursor-ingest/2026-08-04-072347-graph-source-extractor-py]]
→ [[cursor-ingest/2026-08-04-072347-source-tools-ingest-md]]
→ [[cursor-ingest/2026-08-04-072347-tools-ingest-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-data-obsidian-graph-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
