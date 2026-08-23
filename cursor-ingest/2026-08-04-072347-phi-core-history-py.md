# phi / core / history.py

#source #python

> path: phi/core/history.py  
> ext: .py  

---

# phi / core / history.py

phi.core.history — doubly-linked playback history.

Replaces the brittle ``queue.pos - 1`` back-navigation with a proper
linked-list node chain so that pressing "prev" always returns to the
*actually last played track*, not just the adjacent queue slot.

Why not use a plain list?
    A doubly-linked node chain lets the cursor move back *without*
    destroying the forward branch — if the user presses prev then plays a
    new track, the old forward chain is cleanly truncated at the cursor.
    A deque-based approach would need an extra forward-stack; the linked
    nodes keep both in one struc

Defines: HistoryNode, PlaybackHistory, __init__, __repr__, __init__, push, back, forward, current, depth_back, depth_forward, recent, size, _trim

---

## Semantic links

→ [[engine-phi-player]]
→ [[PLAYBACK]]
→ [[engine-prefeed-shuffle]]
→ [[mcp-server]]
→ [[git-log]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-core-queue-py]]
→ [[cursor-ingest/2026-08-04-072347-engine-phi-player-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-core-playback-controller-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-playlist-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-utils-replay-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
