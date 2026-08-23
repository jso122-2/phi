# source / graph-ingestion.md

#doc #md

> path: source/graph-ingestion.md  
> ext: .md  

---

# graph/ingestion

#code #module #graph #code

> source_path: graph/ingestion.py  
> package: graph  
> module: graph/ingestion  
> hub: CODE  
> created_ts:   

---

**Package:** `graph`  
**Module:** `graph/ingestion`  
**Source:** `graph/ingestion.py`

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
                   fastembed, same model)
  2. Link        — cosine similarity → top-K existing vault nodes above threshold
  3. Classify    — hub_classifier() → HOME | MATH | CODE | COMMANDS | agent-context
  4. Write       — write <output_dir>/<timestamp>-<slug>.md to disk

Pipeline stages for the batch
------------------------------
  5. Cross-link  — within-batch cosine similarity → related-doc wikilinks
  6. Manifest    — write <output_dir>/ingest-manifest.json with hub counts and
                   node list; the MCP tool graph_sync_manifest reads this to
                   pulse the harmonic index

The manifest is the bridge between file I/O (this module, any Python env)
and index injection (MCP server, spotify-rip env).  The two sides are
deliberately decoupled so ingestion never requires a live MCP session.

Embedding backend priority
--------------------------
  1. sentence-transformers (full PyTorch; installed in mamba base env)
  2. fastembed (ONNX; installed in spotify-rip env)
  Both produce identical all-MiniLM-L6-v2 384-dim normalised vectors.

Usage
-----
    from graph.ingestion import IngestedDoc, IngestionPip

---

## Semantic links

→ [[graph-ingestion]]
→ [[graph-source-extractor]]
→ [[tools-keep-ingest]]
→ [[tools-ingest]]
→ [[graph-node]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-graph-ingestion-py]]
→ [[cursor-ingest/2026-08-04-072347-graph-source-extractor-py]]
→ [[cursor-ingest/2026-08-04-072347-source-graph-source-extractor-md]]
→ [[cursor-ingest/2026-08-04-072347-source-tools-keep-ingest-md]]
→ [[cursor-ingest/2026-08-04-072347-source-tools-ingest-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
