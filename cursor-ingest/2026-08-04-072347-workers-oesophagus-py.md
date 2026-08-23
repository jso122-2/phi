# workers / oesophagus.py

#source #python

> path: workers/oesophagus.py  
> ext: .py  

---

# workers / oesophagus.py


Oesophagus — ingestion pipeline for the Obsidian vault graph.

Architecture: the tube that feeds the vault (stomach).

                 ┌─────────────┐
   source        │   Scanner   │  discovers .txt, audio, video files
   directory ──► │             │
                 └──────┬──────┘
                        │ file paths
                 ┌──────▼──────┐
                 │  Sentinel   │  blocks / redacts sensitive content
                 │   Gate      │  hard-blocks before any content is parsed
                 └──────┬──────┘
                        │ cleared files
                 ┌──────▼

Defines: FileKind, classify, scan_directory, IngestionItem, _slug, _transform_txt, _transform_audio, _transform_video, _transform, _vault_node_content, write_vault_node, OesophagusResult, ingest, ingest_stream, ok, summary, _make_transform_fn, _fn

---

## Semantic links

→ [[workers-oesophagus]]
→ [[workers-sentinel]]
→ [[graph-ingestion]]
→ [[tools-ingest]]
→ [[engine-vault-garden]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-workers-oesophagus-md]]
→ [[cursor-ingest/2026-08-04-072347-workers-sentinel-py]]
→ [[cursor-ingest/2026-08-04-072347-graph-ingestion-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-oesophagus-py]]
→ [[cursor-ingest/2026-08-04-072347-source-tools-ingest-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
