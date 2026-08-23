# spotify-pipeline / worker.md

#doc #md

> path: spotify-pipeline/worker.md  
> ext: .md  

---

# spotify-pipeline / worker

#spotify-pipeline #worker #CODE #hub

**Files:** `pipeline/worker/`

## Purpose

Thread pool that drains the job queue using spotdl (or yt-dlp). Each worker claims jobs, runs downloads, indexes new files, and marks done/failed.

## Modules

| File | Purpose |
|---|---|
| `spotdl.py` | spotdl subprocess wrapper with multi-pass retry |
| `ytdlp.py` | yt-dlp wrapper (alternative downloader) |
| `executor.py` | ThreadPoolExecutor — drains queue in parallel |

## spotdl Wrapper (run_spotdl)

Downloads into a temp directory first, then moves files to the real output dir under a per-directory lock (eliminates race conditions between parallel workers on the same playlist).

**Multi-pass retry:**
- Up to 3 passes per job
- Pass 1 fails → wait 20s → pass 2
- Pass 2 fails → wait 90s → pass 3
- Each pass uses `--overwrite skip` so already-downloaded tracks are skipped
- Timeout per pass: 600s (SIGKILL on timeout, keep partial files)

**Partial success:** Returns `ok=True` if at least 1 track downloaded.

## Worker Pool (run_workers)

- N parallel workers via ThreadPoolExecutor
- Each worker gets its own spotipy.Spotify instance (avoids shared-session 403s)
- Clients created sequentially before pool starts (avoids token-cache write race)

## Connections

→ [[spotify-pipeline/index|spotify-pipeline]]
→ [[spotify-pipeline/queue|queue]]
→ [[spotify-pipeline/indexer|indexer]]
→ [[spotify-pipeline/scheduler|scheduler]]

---

## Auto-linked

→ [[index]]
→ [[queue]]
→ [[mcp-server]]
→ [[indexer]]
→ [[scheduler]]
→ [[config]]

→ [[cursor-skills]]
→ [[obsidian-exporter]]
→ [[fetcher]]
→ [[auth]]
→ [[2026-07-16-liked-songs-mullvad-multi-source-pipeline]]
→ [[HOME]]

→ [[2026-07-16-011935-modular-pipeline-rebuild]]
→ [[2026-07-15-spotify-pipeline-mcp-cache-queue]]
→ [[2026-07-16-011935-spotify-rip-mcp-server-global-agent-contract]]
→ [[workers]]

→ [[2026-07-16-011935-mamba-environment-spotify-rip]]
→ [[2026-07-16-011935-scribble-files-are-read-only]]
→ [[2026-

---

## Semantic links

→ [[worker]]
→ [[queue]]
→ [[cursor-skills]]
→ [[index]]
→ [[scheduler]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-spotify-pipeline-queue-md]]
→ [[cursor-ingest/2026-08-04-072347-spotify-pipeline-scheduler-md]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-init-py]]
→ [[cursor-ingest/2026-08-04-072347-spotify-pipeline-config-md]]
→ [[cursor-ingest/2026-08-04-072347-source-scripts-run-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
