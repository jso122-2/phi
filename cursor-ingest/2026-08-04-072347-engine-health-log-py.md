# engine / health_log.py

#source #python

> path: engine/health_log.py  
> ext: .py  

---

# engine / health_log.py


HealthLog — SQLite append-only log for vault topology snapshots.

Records one row per coherence cycle with the key topological metrics.
Used by the daemon to track χ over time and by the canvas dashboard
to render trend data. Agents can also write directly via samba_record_coherence.

Schema:
    snapshots(ts, chi, notes, edges, triangles, orphan_count, wikilink_count,
              links_written, bridges_created, comment)

Public API:
    HealthLog(db_path)
    .append(snapshot: dict) -> None
    .recent(n=50) -> List[dict]
    .latest() -> Optional[dict]


Defines: HealthLog, __init__, append, recent, latest, _init_db, _connect, _row_to_dict

---

## Semantic links

→ [[engine-health-log]]
→ [[engine-coherence-daemon]]
→ [[sessions]]
→ [[sessions]]
→ [[graph-logger]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-engine-health-log-md]]
→ [[cursor-ingest/2026-08-04-072347-engine-coherence-daemon-py]]
→ [[cursor-ingest/2026-08-04-072347-graph-logger-py]]
→ [[cursor-ingest/2026-08-04-072347-sessions-md]]
→ [[cursor-ingest/2026-08-04-072347-phi-core-launch-log-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
