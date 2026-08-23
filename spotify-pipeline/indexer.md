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

→ [[dev]]
→ [[2026-07-16-011935-talk-conversational-context-mode]]
→ [[2026-07-16-011935-dev-workhorse-development-mode]]
→ [[2026-07-16-011935-wire-connect-all-work-together]]
→ [[2026-07-16-011935-review]]
→ [[2026-07-16-011935-modular-raw-dev-minimal-python-package]]
