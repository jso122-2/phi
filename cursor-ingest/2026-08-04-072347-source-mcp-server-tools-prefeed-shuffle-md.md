# source / mcp-server-tools-prefeed-shuffle.md

#doc #md

> path: source/mcp-server-tools-prefeed-shuffle.md  
> ext: .md  

---

# mcp_server/tools/prefeed_shuffle

#code #module #mcp-server #code

> source_path: mcp_server/tools/prefeed_shuffle.py  
> package: mcp_server  
> module: mcp_server/tools/prefeed_shuffle  
> hub: CODE  
> created_ts:   

---

**Package:** `mcp_server`  
**Module:** `mcp_server/tools/prefeed_shuffle`  
**Source:** `mcp_server/tools/prefeed_shuffle.py`

prefeed_shuffle — MCP tools for the CAIRRN-bound prefeed shuffle.

Three tools:

    shuffle_seed   — bootstrap: build session + force initial commit
    shuffle_step   — one scheduler clock tick (gate check + auto prefeed/commit)
    shuffle_next   — advance cursor and return the next track
    shuffle_state  — inspect the full shuffle + gate state

## API

- `def _get_shuffle` — Build and cache the CAIRRNPrefeedShuffle singleton.
- `def shuffle_seed` — Bootstrap the CAIRRN-bound prefeed shuffle.
- `def shuffle_step` — One CAIRRN scheduler clock tick.
- `def shuffle_next` — Advance the shuffle cursor and return the current track.
- `def shuffle_state` — Full state snapshot of the CAIRRN prefeed shuffle.
- `def _peek_tracks` — Format a ShufflePeek into a list of track dicts.

## Internal imports

`mcp_server._gate`, `mcp_server._state`, `mcp_server.tools.phi_clip`, `engine.prefeed_shuffle`

---

## Semantic links

→ [[COMMANDS]]
→ [[mcp-server]]
→ [[mcp-server]]
→ [[2026-07-16-011935-mcp-pre-call]]
→ [[COMMANDS]]

## Related notes

→ [[source/engine-prefeed-shuffle]]
→ [[source/mcp-server-tools-cairrn]]
→ [[source/mcp-server-tools-phi-dispatch]]
→ [[source/engine-phi-player]]
→ [[source/mcp-server-server]]

— import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[mcp-index]]
→ [[mcp-server-main]]
→ [[mcp-server-tools-cairrn]]
→ [[mcp-server-server]]
→ [[mcp-server-tools-init]]
→ [[engine-prefeed-shuffle]]

---

## Semantic links

→ [[mcp-server-tools-prefeed-shuffle]]
→ [[mcp-server-server]]
→ [[engine-prefeed-shuffle]]
→ [[mcp-index]]
→ [[mcp-server-main]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-mcp-server-tools-prefeed-shuffle-py]]
→ [[cursor-ingest/2026-08-04-072347-source-engine-prefeed-shuffle-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-init-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-system-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-main-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
