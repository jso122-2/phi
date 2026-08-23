# source / workers-oesophagus.md

#doc #md

> path: source/workers-oesophagus.md  
> ext: .md  

---

# workers/oesophagus

#code #module #workers #code

> source_path: workers/oesophagus.py  
> package: workers  
> module: workers/oesophagus  
> hub: CODE  
> created_ts:   

---

**Package:** `workers`  
**Module:** `workers/oesophagus`  
**Source:** `workers/oesophagus.py`

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
                 ┌──────▼──────┐
                 │  Transform  │  .txt → VaultNode skeleton
                 │  Workers    │  audio/video → metadata stub
                 └──────┬──────┘
                        │ IngestionItem list
                 ┌──────▼──────┐
                 │  Cerberus   │  bind-guards each transform worker
                 │   Guard     │  respawns failing workers mathematically
                 └──────┬──────┘
                        │ passed items
                 ┌──────▼──────┐
                 │   Vault     │  writes .md nodes into sessions/ingest/
                 │   Writer    │
                 └─────────────┘

No Pericles watchdog is used in this pipeline.
The only quality gate is the Cerberus bind (ceb_1, ceb_2).

Supported ingest formats
------------------------
Text:
  .txt — primary ingest format; full content read and vaulted

Audio (metadata stub — no rip yet, rip layer comes later):
  .mp3, .flac, .wav, .aac, .ogg, .m4a, .opus

Video (metadata stub — no rip yet):
  .mp4, .mkv, .avi, .mov, .webm, .m4v

Blocked by Sentinel (never reach the vault):
  See workers.sentinel for the full block-lis

---

## Semantic links

→ [[workers-oesophagus]]
→ [[workers-sentinel]]
→ [[graph-ingestion]]
→ [[engine-vault-garden]]
→ [[graph-worker]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-workers-oesophagus-py]]
→ [[cursor-ingest/2026-08-04-072347-source-tools-ingest-md]]
→ [[cursor-ingest/2026-08-04-072347-graph-ingestion-py]]
→ [[cursor-ingest/2026-08-04-072347-graph-md]]
→ [[cursor-ingest/2026-08-04-072347-source-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
