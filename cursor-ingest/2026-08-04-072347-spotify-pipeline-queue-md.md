# spotify-pipeline / queue.md

#doc #md

> path: spotify-pipeline/queue.md  
> ext: .md  

---

# spotify-pipeline / queue

#spotify-pipeline #queue #CODE #hub

**Files:** `pipeline/queue/`

## Purpose

Persistent SQLite-backed job queue with atomic multi-worker claim and exponential backoff between retries.

## Job Lifecycle

```
pending → downloading → done
                      → failed  (retried up to 3 times)
```

## Key Design

**Atomic claim (race-safe):**
```sql
UPDATE jobs SET status='downloading' WHERE id=? AND status='pending'
-- rowcount=0 means another worker got it first → retry
```

**WAL mode** — all workers read concurrently; only the brief UPDATE serialises.

**Thread-local connections** — one SQLite connection per OS thread.

**Exponential backoff:**
- Attempt 1→2: wait 0s (immediate retry)
- Attempt 2→3: wait 2 min
- Attempt 3→4: wait 10 min

**Crash recovery:** Jobs stuck in `downloading` on startup are reset to `pending`.

## JobQueue Methods

- `enqueue(job) -> bool` — insert; False if already exists (idempotent)
- `claim_next() -> Job | None` — atomic claim; retries 20x on contention
- `mark_done(job_id)`, `mark_failed(job_id, error, attempt)`
- `requeue_failed() -> int` — reset all failed to pending
- `stats() -> dict` — counts per status

## Connections

→ [[spotify-pipeline/index|spotify-pipeline]]
→ [[spotify-pipeline/scheduler|scheduler]]
→ [[spotify-pipeline/worker|worker]]
→ [[spotify-pipeline/mcp-server|mcp-server]]

---

## Auto-linked

→ [[index]]
→ [[config]]
→ [[mcp-server]]
→ [[cursor-skills]]
→ [[scheduler]]
→ [[worker]]

→ [[indexer]]
→ [[obsidian-exporter]]
→ [[auth]]
→ [[fetcher]]
→ [[2026-07-16-liked-songs-mullvad-multi-source-pipeline]]
→ [[2026-07-15-spotify-pipeline-mcp-cache-queue]]

→ [[2026-07-16-011935-modular-pipeline-rebuild]]
→ [[2026-07-16-011935-spotify-rip-mcp-server-global-agent-contract]]
→ [[HOME]]

→ [[2026-07-16-011935-mamba-environment-spotify-rip]]
→ [[2026-07-16-011935-spotify-rip-slash-commands]]
→ [[2026-07-16-011935-session-init]]
→ [[2026-07-16-011935-scribble-files-are-read-only]]
→ [[2026-07-

---

## Semantic links

→ [[queue]]
→ [[worker]]
→ [[scheduler]]
→ [[mcp-server]]
→ [[indexer]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-spotify-pipeline-worker-md]]
→ [[cursor-ingest/2026-08-04-072347-spotify-pipeline-scheduler-md]]
→ [[cursor-ingest/2026-08-04-072347-spotify-pipeline-indexer-md]]
→ [[cursor-ingest/2026-08-04-072347-spotify-pipeline-cursor-skills-md]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-init-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
