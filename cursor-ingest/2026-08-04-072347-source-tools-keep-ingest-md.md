# source / tools-keep-ingest.md

#doc #md

> path: source/tools-keep-ingest.md  
> ext: .md  

---

# tools/keep_ingest

#code #module #tools #code

> source_path: tools/keep_ingest.py  
> package: tools  
> module: tools/keep_ingest  
> hub: CODE  
> created_ts:   

---

**Package:** `tools`  
**Module:** `tools/keep_ingest`  
**Source:** `tools/keep_ingest.py`

Google Keep Takeout → Obsidian vault importer.

Thin adapter over graph.ingestion.IngestionPipeline.  Handles the Google
Keep JSON schema (title, textContent, labels, timestamps, isTrashed) and
feeds clean IngestedDoc objects into the pipeline.

After writing, runs /graph-sync-manifest automatically by calling the
pipeline's manifest directly against the harmonic index — or prints the
manual command if the MCP server is not reachable.

Usage (from Spotify-rip/ with mamba base env Python):
    python tools/keep_ingest.py [--keep-dir PATH] [--dry-run]
                                [--threshold F] [--top-k N]
                                [--skip-cross-link] [--no-wipe]

Defaults
--------
--keep-dir      ~/Downloads/Takeout/Keep
--threshold     0.30   (cosine similarity cutoff)
--top-k         5      (max vault links per note)

## API

- `def _slug`
- `def _ts_to_dt`
- `def _should_skip`
- `def _keep_note_to_doc`
- `def run`
- `def main`

## Internal imports

`graph.ingestion`, `graph.node`

---

## Semantic links

→ [[keep]]
→ [[2026-07-13-configure-the-obsidian-graph-as-the-hub-buil]]
→ [[2025-09-09-102444-2025-09-09t20-25-19-520-10-00]]
→ [[graph]]
→ [[graph]]

## Related notes

→ [[source/graph-ingestion]]
→ [[source/tools-ingest]]
→ [[source/graph-source-extractor]]
→ [[source/mcp-server-tools-graph]]
→ [[source/graph-init]]

— import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[tools-index]]
→ [[mcp-server-tools-graph]]
→ [[tools-ingest]]
→ [[graph-init]]
→ [[graph-logger]]
→ [[graph-source-extractor]]

---

## Semantic links

→ [[tools-keep-ingest]]
→ [[graph-ingestion]]
→ [[tools-ingest]]
→ [[tools-cursor-ingest]]
→ [[mcp-server-tools-graph]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-tools-ingest-md]]
→ [[cursor-ingest/2026-08-04-072347-source-graph-ingestion-md]]
→ [[cursor-ingest/2026-08-04-072347-tools-keep-ingest-py]]
→ [[cursor-ingest/2026-08-04-072347-graph-ingestion-py]]
→ [[cursor-ingest/2026-08-04-072347-source-tools-index-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
