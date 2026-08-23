# source / engine-rsync-bridge.md

#doc #md

> path: source/engine-rsync-bridge.md  
> ext: .md  

---

# engine/rsync_bridge

#code #module #engine #code

> source_path: engine/rsync_bridge.py  
> package: engine  
> module: engine/rsync_bridge  
> hub: CODE  
> created_ts:   

---

**Package:** `engine`  
**Module:** `engine/rsync_bridge`  
**Source:** `engine/rsync_bridge.py`

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
    (optional) VaultWriter stub   ← writes a minimal .md into vault so the
                                     changed file immediately has a graph node
        ↓
    log summary

CLI:
    python -m engine.rsync_bridge [options]

    --config PATH           config.yaml path (default: config/config.yaml)
    --checkpoint PATH       model checkpoint (auto-detected if omitted)
    --watch PATH [PATH …]   additional dirs to watch (project root + vault
                            are always included)
    --debounce-ms N         batch window in ms (default: 400)
    --no-stub               don't write vault stubs for changed source files
    --dry-run               log actions but don't write vault or call refresh
    --log-level LEVEL       DEBUG / INFO / WARNING (default: INFO)

## API

- `class ChangeBuffer` — Accumulates filesystem events during a debounce window, then fires once.
- `class GraphSyncHandler` — Forward meaningful file changes into ChangeBuffer.
- `def _write_vault_stub` — Create or update a minimal Obsidian note that mirrors the changed source
- `class RsyncBridge` — Persistent bridge: watches filesystem, refreshes graph on changes.
- `de

---

## Semantic links

→ [[engine-rsync-bridge]]
→ [[2026-07-17T02-58-58Z-RsyncBridge — real-time Cursor to Obsidian graph sync]]
→ [[scripts-mcp-bridge]]
→ [[graph-worker]]
→ [[mcp-server-tools-graph]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-engine-rsync-bridge-py]]
→ [[cursor-ingest/2026-08-04-072347-source-scripts-mcp-bridge-md]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-bridge-init-md]]
→ [[cursor-ingest/2026-08-04-072347-source-graph-worker-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-graph-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
