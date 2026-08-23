# tools / keep_ingest.py

#source #python

> path: tools/keep_ingest.py  
> ext: .py  

---

# tools / keep_ingest.py


Google Keep Takeout → Obsidian vault importer.

Thin adapter over graph.ingestion.IngestionPipeline.  Handles the Google
Keep JSON schema (title, textContent, labels, timestamps, isTrashed) and
feeds clean IngestedDoc objects into the pipeline.

After writing, runs /graph-sync-manifest automatically by calling the
pipeline's manifest directly against the harmonic index — or prints the
manual command if the MCP server is not reachable.

Usage (from Spotify-rip/ with mamba base env Python):
    python tools/keep_ingest.py [--keep-dir PATH] [--dry-run]
                                [--threshol

Defines: _slug, _ts_to_dt, _should_skip, _keep_note_to_doc, run, main

---

## Semantic links

→ [[tools-keep-ingest]]
→ [[graph-ingestion]]
→ [[index]]
→ [[pipeline-fetcher-models]]
→ [[mcp-server]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-tools-keep-ingest-md]]
→ [[cursor-ingest/2026-08-04-072347-graph-ingestion-py]]
→ [[cursor-ingest/2026-08-04-072347-source-graph-ingestion-md]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-fetcher-models-py]]
→ [[cursor-ingest/2026-08-04-072347-source-graph-logger-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
