# source / mcp-server-vault-hub.md

#doc #md

> path: source/mcp-server-vault-hub.md  
> ext: .md  

---

# mcp_server/vault_hub

#code #module #mcp-server #code

> source_path: mcp_server/vault_hub.py  
> package: mcp_server  
> module: mcp_server/vault_hub  
> hub: CODE  
> created_ts:   

---

**Package:** `mcp_server`  
**Module:** `mcp_server/vault_hub`  
**Source:** `mcp_server/vault_hub.py`

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
Same pattern as HarmonicIndex and DOMRequestQueue: a single threading.RLock
guards all writes.  Writes are fast (small .md file), so lock contention is
negligible.

Registration
------------
VaultHub is instantiated once at spawn alongside the DOM queue:

    _vault_hub = VaultHub(vault_dir=Path("Spotify-rip"))

Then called inside tool bodies after state-mutating operations:

    _vault_hub.push_harmonic(state_dict)
    _vault_hub.push_sim("double_well_sim", result_dict)
    _vault_hub.push_queue(queue_state_dict)

## API

- `class VaultHub` — Writes MCP server state back into the Obsidian vault as live-state.md.
- `def _activation_bar` — Tiny text bar showing relative activation level.
- `def open_vault_hub` — Instantiate and return a VaultHub pointed at the Obsidian vault.

---

## Semantic links

→ [[2026-07-13-040611-configure-pushes-to-the-obsidian-graph-and-bu]]
→ [[2026-07-13-configure-the-obsidian-graph-as-the-hub-buil]]
→ [[2026-07-16-011935-vault-hub-remote-bmod-maximum-prescription]]
→ [[2026-07-16-011935-vault-coherence-engine]]
→ [[sessions]]

## Related notes

→ [[source/mcp-server-tools-search]]
→ [[source/scripts-mcp-bridge]]
→ [[

---

## Semantic links

→ [[mcp-server-vault-hub]]
→ [[mcp-server-tools-graph]]
→ [[mcp-server-server]]
→ [[scripts-mcp-bridge]]
→ [[mcp-server-tools-search]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-main-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-system-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-modular-md]]
→ [[cursor-ingest/2026-08-04-072347-mcp-server-vault-hub-py]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-init-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
