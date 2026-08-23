# mcp_server / tools / prefeed_shuffle.py

#source #python

> path: mcp_server/tools/prefeed_shuffle.py  
> ext: .py  

---

# mcp_server / tools / prefeed_shuffle.py


prefeed_shuffle — MCP tools for the CAIRRN-bound prefeed shuffle.

Three tools:

    shuffle_seed   — bootstrap: build session + force initial commit
    shuffle_step   — one scheduler clock tick (gate check + auto prefeed/commit)
    shuffle_next   — advance cursor and return the next track
    shuffle_state  — inspect the full shuffle + gate state


Defines: _get_shuffle, shuffle_seed, shuffle_step, shuffle_next, shuffle_state, _peek_tracks

---

## Semantic links

→ [[mcp-server-tools-prefeed-shuffle]]
→ [[engine-prefeed-shuffle]]
→ [[mcp-server-tools-cairrn]]
→ [[engine-phi-player]]
→ [[mcp-server-tools-phi-dispatch]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-prefeed-shuffle-md]]
→ [[cursor-ingest/2026-08-04-072347-source-engine-prefeed-shuffle-md]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-prefeed-shuffle-py]]
→ [[cursor-ingest/2026-08-04-072347-mcp-server-tools-cairrn-py]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-cairrn-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
