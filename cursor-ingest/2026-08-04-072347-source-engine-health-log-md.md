# source / engine-health-log.md

#doc #md

> path: source/engine-health-log.md  
> ext: .md  

---

# engine/health_log

#code #module #engine #code

> source_path: engine/health_log.py  
> package: engine  
> module: engine/health_log  
> hub: CODE  
> created_ts:   

---

**Package:** `engine`  
**Module:** `engine/health_log`  
**Source:** `engine/health_log.py`

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

## API

- `class HealthLog` — Append-only SQLite log for coherence cycle snapshots.

---

## Semantic links

→ [[sessions]]
→ [[sessions]]
→ [[2026-07-16-011935-vault-coherence-engine]]
→ [[2026-07-13-configure-the-obsidian-graph-as-the-hub-buil]]
→ [[2025-05-27-173121-2025-05-28t03-31-22-711-10-00]]

## Related notes

→ [[source/engine-coherence-daemon]]
→ [[source/engine-forecasting-engine]]
→ [[source/graph-logger]]
→ [[source/engine-cursor-tracer]]
→ [[source/engine-phi-session]]

— import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[engine-index]]
→ [[engine-main]]
→ [[engine-gate]]
→ [[engine-coherence-daemon]]
→ [[index]]
→ [[engine-init]]

---

## Semantic links

→ [[engine-health-log]]
→ [[engine-coherence-daemon]]
→ [[engine-vault-garden]]
→ [[engine-phi-session]]
→ [[tools-cursor-ingest]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-engine-health-log-py]]
→ [[cursor-ingest/2026-08-04-072347-engine-coherence-daemon-py]]
→ [[cursor-ingest/2026-08-04-072347-source-engine-forecasting-engine-md]]
→ [[cursor-ingest/2026-08-04-072347-source-engine-coherence-daemon-md]]
→ [[cursor-ingest/2026-08-04-072347-sessions-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
