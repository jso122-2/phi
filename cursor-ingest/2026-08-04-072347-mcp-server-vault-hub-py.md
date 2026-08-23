# mcp_server / vault_hub.py

#source #python

> path: mcp_server/vault_hub.py  
> ext: .py  

---

# mcp_server / vault_hub.py


VaultHub — backwards enforcement from MCP server into the Obsidian vault.

Data flow
---------
Forward (existing):   vault .md files → PSSPPS retriever → harmonic scorer → MCP tool results
Backwards (this file): MCP tool results → VaultHub.push_*() → vault live-state.md

The vault is the hub.  Every mutating MCP operation writes a snapshot back to
`Spotify-rip/live-state.md`.  Obsidian picks it up immediately (file watcher).
The graph then reflects live server state — the vault stays the canonical record.

Thread safety
-------------
Same pattern as HarmonicIndex and DOMRequestQueue: a single

Defines: VaultHub, _activation_bar, open_vault_hub, __init__, push_harmonic, push_sim, push_queue, push_forecast, push_all, _write, _render, _render_harmonic, _render_forecast, _render_sim, _render_queue

---

## Semantic links

→ [[mcp-server-vault-hub]]
→ [[scripts-mcp-bridge]]
→ [[mcp-server-tools-graph]]
→ [[ARTIST]]
→ [[mcp-server]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-vault-hub-md]]
→ [[cursor-ingest/2026-08-04-072347-phi-engine-vault-context-py]]
→ [[cursor-ingest/2026-08-04-072347-scripts-mcp-bridge-py]]
→ [[cursor-ingest/2026-08-04-072347-mcp-server-server-py]]
→ [[cursor-ingest/2026-08-04-072347-psspps-retriever-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
