# engine / phi_player.py

#source #python

> path: engine/phi_player.py  
> ext: .py  

---

# engine / phi_player.py


PhiPlayer — CAIRRN-aware playback controller.

Architecture
------------
PhiPlayer closes the feedback loop between what the user *listens to* and
how CAIRRN shapes the *next* shuffle order.

    play_next()           → advance shuffle cursor
                          → peek_and_preload() upcoming tracks into hot cache
                          → step() the dispatcher (CAIRRN CODE tick + hot loader)
                          → return Track to play

    report_play(fraction) → record PlayEvent
                          → inject play fraction into HOME / CODE hubs
                          → fo

Defines: PlayEvent, PhiPlayer, make_phi_player, PhiPipeline, make_phi_pipeline, duration_s, as_dict, __init__, play_next, report_play, current_track, history, total_plays, skip_rate, state, _compute_injections, _inject_feedback, __repr__, state

---

## Semantic links

→ [[engine-phi-player]]
→ [[engine-prefeed-shuffle]]
→ [[mcp-server-tools-prefeed-shuffle]]
→ [[PLAYBACK]]
→ [[scripts-embed-tracks]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-core-playback-controller-py]]
→ [[cursor-ingest/2026-08-04-072347-source-engine-phi-player-md]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-phi-player-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-core-queue-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-core-smart-playlist-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
