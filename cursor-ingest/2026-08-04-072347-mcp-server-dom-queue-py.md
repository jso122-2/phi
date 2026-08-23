# mcp_server / dom_queue.py

#source #python

> path: mcp_server/dom_queue.py  
> ext: .py  

---

# mcp_server / dom_queue.py


DOM Request Queue — 6-house serialising gate for the MCP server.

Architecture
------------
At spawn, six Houses are opened — one per workflow mode.  Every tool call
races from spawn to its declared house.  The queue verifies the BMAD trust
token, admits the call through the correct door, and serialises execution
within that lane.

Once inside a house, the call proceeds through and purposeful — no ambiguity
in ordering, no silent state contention.  Calls to *different* houses are
fully parallel; calls to the *same* house are queued.

BMAD Trust
----------
Each house holds a trust token minted

Defines: House, _HouseGate, RaceWatchdog, DOMRequestQueue, _bmad_token, spawn_houses, __post_init__, admits, enter, status, __init__, house, tool_name, elapsed_ms, __enter__, __exit__, __init__, start, stop, state, _watch_loop, _poll, _record_stall, _record_contention, __init__, register_house, open, gate, state, house_for

---

## Semantic links

→ [[mcp-server-dom-queue]]
→ [[mcp-server-gate]]
→ [[mcp-server-tools-phi-dispatch]]
→ [[mcp-server-server]]
→ [[mcp-server]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-tests-test-dom-queue-py]]
→ [[cursor-ingest/2026-08-04-072347-mcp-server-gate-py]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-dom-queue-md]]
→ [[cursor-ingest/2026-08-04-072347-mcp-server-tools-phi-dispatch-py]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-index-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
