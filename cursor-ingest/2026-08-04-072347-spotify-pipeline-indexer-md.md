# spotify-pipeline / indexer.md

#doc #md

> path: spotify-pipeline/indexer.md  
> ext: .md  

---

# spotify-pipeline / indexer

#spotify-pipeline #indexer #CODE #hub

**Files:** `pipeline/indexer/`

## Purpose

SQLite-backed index that tracks which tracks are expected to be downloaded and which files were actually produced. Provides progress reporting and dedup.

## TrackRecord

```python
TrackRecord(
    spotify_id, spotify_url, title, artists, album, year,
    collection_type,   # 'liked' | 'album' | 'playlist'
    collection_name,   # "Liked Songs", album title, or playlist name
    track_number, job_id, output_dir,
    status,            # 'pending' | 'downloaded' | 'missing'
    local_path, file_size
)
```

A track in both Liked Songs and a playlist gets two records (distinct download destinations).

## Modules

| File | Purpose |
|---|---|
| `models.py` | TrackRecord dataclass |
| `builder.py` | build_track_records() — snapshot + jobs → records |
| `store.py` | LibraryIndex — SQLite CRUD |
| `scanner.py` | snapshot_dir() — scan directory for audio files |
| `scaffolder.py` | Tree view scaffolding |
| `sidecar.py` | Sidecar metadata files |

## Connections

→ [[spotify-pipeline/index|spotify-pipeline]]
→ [[spotify-pipeline/worker|worker]]
→ [[spotify-pipeline/fetcher|fetcher]]

---

## Auto-linked

→ [[index]]
→ [[config]]
→ [[mcp-server]]
→ [[scheduler]]
→ [[cursor-skills]]
→ [[obsidian-exporter]]

→ [[queue]]
→ [[fetcher]]
→ [[worker]]
→ [[auth]]
→ [[HOME]]
→ [[2026-07-16-liked-songs-mullvad-multi-source-pipeline]]

→ [[2026-07-15-spotify-pipeline-mcp-cache-queue]]
→ [[2026-07-16-011935-modular-pipeline-rebuild]]
→ [[2026-07-16-011935-spotify-rip-mcp-server-global-agent-contract]]
→ [[2026-07-16-011935-clean-repo-file-tree-cleanup]]
→ [[2026-07-16-011935-mamba-environment-spotify-rip]]

→ [[2026-07-16-011935-scribble-files-are-read-only]]
→ [[2026-07-16-011935-spotify-rip-slash-commands]]
→ [[2026-07-16-011935-session-init]]
→ [[2026-07-16-011935-find]]
→ [[2026-07-16-011935-cursor-hooks-configuration]]
→ [[2026-07-16-011935-run-shell-commands]]

→ [[dev]

---

## Semantic links

→ [[indexer]]
→ [[fetcher]]
→ [[pipeline-fetcher-models]]
→ [[index]]
→ [[scheduler]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-spotify-pipeline-fetcher-md]]
→ [[cursor-ingest/2026-08-04-072347-spotify-pipeline-index-md]]
→ [[cursor-ingest/2026-08-04-072347-spotify-pipeline-cursor-skills-md]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-fetcher-models-py]]
→ [[cursor-ingest/2026-08-04-072347-spotify-pipeline-obsidian-exporter-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
