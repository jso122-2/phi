# source / scripts-samba-mcp-server.md

#doc #md

> path: source/scripts-samba-mcp-server.md  
> ext: .md  

---

# scripts/samba_mcp_server

#code #module #scripts #code

> source_path: scripts/samba_mcp_server.py  
> package: scripts  
> module: scripts/samba_mcp_server  
> hub: CODE  
> created_ts:   

---

**Package:** `scripts`  
**Module:** `scripts/samba_mcp_server`  
**Source:** `scripts/samba_mcp_server.py`

Samba GNN — MCP Server
Proper JSON-RPC 2.0 MCP server using FastMCP.
Registers with Cursor via .cursor/mcp.json and exposes the Obsidian graph
orchestration tools as native MCP tools.

Usage (Cursor handles this automatically via .cursor/mcp.json):
    python mcp_server.py

    # With a specific checkpoint:
    python mcp_server.py --checkpoint checkpoints/best.pt

    # To test tools manually:
    python mcp_server.py --dev

The server loads the model lazily on first tool call and caches it.
If no checkpoint exists yet, tools return a helpful "not trained" message
rather than crashing.

Tools exposed:
    samba_find_related      Find notes semantically related to a given note
    samba_suggest_links     Suggest wiki-links that are missing but should exist
    samba_route_query       Route a free-text query to the most relevant notes
    samba_get_clusters      Return topic clusters across the vault
    samba_graph_stats       Vault graph statistics (nodes, edges, χ, Euler spectrum)
    samba_euler_spectrum    Show learned oscillation frequencies from EulerSSM
    samba_refresh           Force re-encode and rebuild the graph representation

Agent write-zone tools (Option-3 write isolation):
    samba_write_note        Create a new note in agent-log/ (or named zone)
    samba_annotate          Append an agent comment to an existing note

Live daemon CAIRRN bridge (IPC via /tmp state file):
    cairrn_hub_state        Read live hub state from the running daemon
    cairrn_inject           Inject an activation into a daemon hub next cycle

## API

- `def _find_best_checkpoint` — Auto-discover the best or most recent checkpoint.
- `def _get_orchestrator` — Return the c

---

## Semantic links

→ [[scripts-samba-mcp-server]]
→ [[mcp-server-server]]
→ [[mcp-server-main]]
→ [[mcp-server-tools-modular]]
→ [[scripts-mcp-bridge]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-main-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-system-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-modular-md]]
→ [[cursor-ingest/2026-08-04-072347-scripts-samba-mcp-server-py]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-state-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
