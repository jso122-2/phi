# source / scripts-mcp-bridge.md

#doc #md

> path: source/scripts-mcp-bridge.md  
> ext: .md  

---

# scripts/mcp_bridge

#code #module #scripts #code

> source_path: scripts/mcp_bridge.py  
> package: scripts  
> module: scripts/mcp_bridge  
> hub: CODE  
> created_ts:   

---

**Package:** `scripts`  
**Module:** `scripts/mcp_bridge`  
**Source:** `scripts/mcp_bridge.py`

MCP Obsidian Bridge — Live Vault Sync Daemon
Polls the Obsidian vault for changes and triggers adaptive retraining
when topology shifts are detected. Also exposes the SambaOrchestrator
as a simple JSON-RPC-compatible interface for MCP tool calls.

Run alongside your Obsidian instance:
    python mcp_bridge.py --checkpoint checkpoints/best.pt

MCP tools exposed:
    samba/find_related      — related note retrieval
    samba/suggest_links     — orphan link suggestions
    samba/get_clusters      — topic cluster view
    samba/route_query       — free-text query routing
    samba/refresh           — force re-encode + rebuild

    tracer/status           — live tracer swarm status + CAIRRN hub state
    tracer/cairrn           — full CAIRRN harmonic index state
    tracer/scores           — latest aggregated arm scores (prune/graft/sprout/…)

## API

- `class VaultWatcher` — Background thread that polls for vault changes and triggers refresh.
- `class MCPHandler`
- `def main`

## Internal imports

`models.coherence`, `engine.tracer_daemon`

---

## Semantic links

→ [[2026-07-13-configure-the-obsidian-graph-as-the-hub-buil]]
→ [[graph]]
→ [[hub-classifier]]
→ [[2026-07-17T02-58-58Z-RsyncBridge — real-time Cursor to Obsidian graph sync]]
→ [[graph]]

## Related notes

→ [[source/mcp-server-vault-hub]]
→ [[source/mcp-server-tools-graph]]
→ [[source/scripts-samba-mcp-server]]
→ [[source/scripts-train]]
→ [[source/engine-vault-writer]]

— import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[scripts-samba-mcp-server]]
→ [[mcp-server-main]]
→ [[mcp-server-tools-search]]
→ [[index]]
→ [[mcp-server-tools-graph]]
→ [[mcp-server-tools-init]]

---

## Semantic links

→ [[scripts-mcp-bridge]]
→ [[mcp-server-vault-hub]]
→ [[mcp-server-tools-graph]]
→ [[scripts-train]]
→ [[engine-cairrn-bridge]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-scripts-mcp-bridge-py]]
→ [[cursor-ingest/2026-08-04-072347-source-scripts-train-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-vault-hub-md]]
→ [[cursor-ingest/2026-08-04-072347-source-engine-rsync-bridge-md]]
→ [[cursor-ingest/2026-08-04-072347-scripts-train-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
