# source / mcp-server-dom-queue.md

#doc #md

> path: source/mcp-server-dom-queue.md  
> ext: .md  

---

# mcp_server/dom_queue

#code #module #mcp-server #code

> source_path: mcp_server/dom_queue.py  
> package: mcp_server  
> module: mcp_server/dom_queue  
> hub: CODE  
> created_ts:   

---

**Package:** `mcp_server`  
**Module:** `mcp_server/dom_queue`  
**Source:** `mcp_server/dom_queue.py`

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
Each house holds a trust token minted at spawn from a deterministic hash of
the house name.  The mapping of tool → house is declared at spawn and is
immutable for the process lifetime.  Tools cannot self-select a different
house; the queue enforces structural trust, not credential-based trust.

    Build   — declare the house mapping at spawn
    Map     — route every tool to exactly one house
    Admit   — verify membership before acquiring the lane lock
    Do      — execute within the serialised lane, then release

Race / Concurrency
------------------
The solved race-condition system already used in HarmonicIndex (threading.RLock)
is promoted here to the queue layer — one RLock per house.  The queue-level
RLock (_queue_lock) protects the house registry during spawn registration only.
After open() is called, the registry is frozen and each house lock operates
independently.

This is slower for the CPU by one lock acquire/release per call (≈ 50–200 ns
per gate crossing), which is completely imperceptible at human interaction
timescales (> 100 ms).

Race Condition Watchdog
-----------------------
RaceWatchdog runs as a daem

---

## Semantic links

→ [[mcp-server-server]]
→ [[mcp-server-dom-queue]]
→ [[mcp-index]]
→ [[mcp-server-main]]
→ [[mcp-server-hooks]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-mcp-index-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-main-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-system-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-init-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-state-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
