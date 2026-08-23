# scripts / mcp_bridge.py

#source #python

> path: scripts/mcp_bridge.py  
> ext: .py  

---

# scripts / mcp_bridge.py


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
    samba/refresh        

Defines: VaultWatcher, MCPHandler, main, __init__, run, stop, log_message, do_POST, _dispatch, _respond, _tracer_cycle_thread

---

## Semantic links

→ [[scripts-mcp-bridge]]
→ [[mcp-server-tools-graph]]
→ [[2026-07-13-configure-the-obsidian-graph-as-the-hub-buil]]
→ [[scripts-samba-mcp-server]]
→ [[mcp-server-vault-hub]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-scripts-mcp-bridge-md]]
→ [[cursor-ingest/2026-08-04-072347-scripts-samba-mcp-server-py]]
→ [[cursor-ingest/2026-08-04-072347-scripts-train-py]]
→ [[cursor-ingest/2026-08-04-072347-mcp-server-vault-hub-py]]
→ [[cursor-ingest/2026-08-04-072347-source-scripts-train-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
