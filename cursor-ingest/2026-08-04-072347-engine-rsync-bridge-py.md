# engine / rsync_bridge.py

#source #python

> path: engine/rsync_bridge.py  
> ext: .py  

---

# engine / rsync_bridge.py


RsyncBridge — real-time filesystem → Obsidian graph synchronisation daemon.

Watches one or more source directories (project root, phi/, etc.) with
kqueue/inotify events (via watchdog) and triggers an incremental graph
refresh within milliseconds of a file save — replacing the 5-minute crawl
poll cycle.

Pipeline per change event
─────────────────────────
    file saved in watched dir
        ↓  (debounce 400 ms — batches rapid multi-file saves)
    RsyncBridge._flush()
        ↓
    SambaOrchestrator.refresh()   ← in-process, no HTTP
        ↓
    (optional) VaultWriter stub   ← writes a min

Defines: ChangeBuffer, GraphSyncHandler, _write_vault_stub, RsyncBridge, _parse_args, main, __init__, push, _fire, __init__, _relevant, on_modified, on_created, on_moved, __init__, _get_orch, _find_checkpoint, _flush, _write_cairrn_commands, start, stop, run_forever

---

## Semantic links

→ [[engine-rsync-bridge]]
→ [[2026-07-17T02-58-58Z-RsyncBridge — real-time Cursor to Obsidian graph sync]]
→ [[scripts-mcp-bridge]]
→ [[graph-init]]
→ [[graph-worker]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-engine-rsync-bridge-md]]
→ [[cursor-ingest/2026-08-04-072347-scripts-mcp-bridge-py]]
→ [[cursor-ingest/2026-08-04-072347-graph-init-py]]
→ [[cursor-ingest/2026-08-04-072347-source-graph-init-md]]
→ [[cursor-ingest/2026-08-04-072347-graph-worker-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
