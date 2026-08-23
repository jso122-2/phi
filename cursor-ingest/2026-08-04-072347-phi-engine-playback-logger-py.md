# phi / engine / playback_logger.py

#source #python

> path: phi/engine/playback_logger.py  
> ext: .py  

---

# phi / engine / playback_logger.py

phi.engine.playback_logger — JSONL playback event log.

Writes one JSON object per line to ``~/.phi/logs/playback_YYYY-MM-DD.jsonl``
with daily rotation. Writes are buffered (flushed every 10 events OR 30 s)
and fully thread-safe.

ZoneClusterer (Phase 2) reads these files to build the zone → zone transition
matrix from real listening history.

Event schema
------------
  play  {"ts": float, "event": "play",  "path": str, "d4_a": float|null, "zone_id": int|null}
  skip  {"ts": float, "event": "skip",  "path": str, "pos": float}


Defines: PlaybackLogger, __init__, _ensure_dir, _get_fh, _append, _flush_locked, record, record_skip, flush, close

---

## Semantic links

→ [[engine-phi-player]]
→ [[engine-phi-session]]
→ [[mcp-server-tools-temporal]]
→ [[2025-05-27-173121-2025-05-28t03-31-22-711-10-00]]
→ [[scripts-embed-tracks]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-core-poll-state-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-core-launch-log-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-core-playback-controller-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-watch-librosa-worker-py]]
→ [[cursor-ingest/2026-08-04-072347-engine-phi-player-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
