# Session: 2026-07-15 — Spotify Pipeline MCP + Cache Queue

#session 

**Prompt:** MCP server showing errored. Fix connection and get pipeline working.

**Thinking:** The samba-obsidian MCP server was showing "errored" in Cursor's MCP settings panel. Root cause was a stale stdio connection — not a code bug. The server itself starts cleanly (tested full JSON-RPC handshake). Cursor needed a reconnect via the MCP settings refresh button. Also identified that the Spotify pipeline had 616 cache-chunk jobs queued with no liked songs jobs at all — library_snapshot.json had never been created.

**Outcome:**
- Confirmed MCP server healthy (clean init handshake, tools listing, zero stderr)
- Identified duplicate samba-obsidian entry in both ~/.cursor/mcp.json and .cursor/mcp.json
- Diagnosed queue state: 69 downloading (stale) + 547 pending — all cache chunks, no liked songs
- Confirmed library_snapshot.json missing — fetch has never run
- Planned fetch → scaffold → work sequence for liked songs

## Graph links discovered

→ [[mcp-server]]  
→ [[environment]]  
→ [[graph]]  
→ [[2026-07-15]]

---

## Auto-linked

→ [[cursor-skills]]
→ [[config]]
→ [[2026-07-13-042743-configure-the-obsidian-graph-as-the-hub-buil]]
→ [[obsidian-exporter]]
→ [[sessions]]

→ [[logger]]
→ [[scheduler]]

→ [[indexer]]
→ [[git-log]]
→ [[fetcher]]

→ [[mcp-server-server]]
→ [[queue]]
