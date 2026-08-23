# phi / core / launch_log.py

#source #python

> path: phi/core/launch_log.py  
> ext: .py  

---

# phi / core / launch_log.py

phi.core.launch_log — append-only per-launch cache snapshot.

Writes one JSON line to ``~/.phi/launches.jsonl`` every time phi starts.
Each entry captures the state of every persistent cache so you can audit
what was loaded, enriched, and rate-limited across sessions.

Schema (one JSON object per line)
──────────────────────────────────
{
  "ts":            "2026-07-19T09:05:30.123456",   # ISO-8601 launch time
  "library_size":  1234,                            # tracks in session playlist
  "meta_tracks":   1190,                            # rows in meta.db tracks table
  "annotated":     87

Defines: _meta_stats, _session_snapshot, _spotify_snapshot, record

---

## Semantic links

→ [[engine-phi-session]]
→ [[engine-health-log]]
→ [[tools-keep-ingest]]
→ [[engine-hot-loader]]
→ [[2025-05-15-063837-2025-05-15t16-39-34-231-10-00]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-session-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-meta-cache-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-engine-playback-logger-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-core-library-py]]
→ [[cursor-ingest/2026-08-04-072347-engine-health-log-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
