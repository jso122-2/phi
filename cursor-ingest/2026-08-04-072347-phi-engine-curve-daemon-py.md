# phi / engine / curve_daemon.py

#source #python

> path: phi/engine/curve_daemon.py  
> ext: .py  

---

# phi / engine / curve_daemon.py

phi.engine.curve_daemon — CurveDaemon: single orchestrating object for
dragon-curve background ML additions.

Coordinates three background processes that run alongside phi's playback engine:

    A  FoldInjector   — wire track fold-bits into the shared harmonic index
                        so the CAIRRN ring reflects the curve geometry of
                        whatever is playing.

    B  ArcScorer      — maintain a rolling D4_A buffer to score candidate
                        tracks for smooth arc continuation.

    C  PlaybackLogger — write JSONL events (play / skip) that ZoneClusterer
 

Defines: CurveDaemon, __init__, on_track_change, on_skip, on_library_refresh, suggest_next_for, score_candidate, zone_of, _on_clustered, index_state, cairrn_state, flush_logs, shutdown

---

## Semantic links

→ [[engine-phi-player]]
→ [[scripts-train-d4]]
→ [[engine-cairrn-scheduler]]
→ [[mcp-server-tools-phi-dispatch]]
→ [[engine-tracer-daemon]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-engine-curve-walker-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-rooms-dragon-room-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-app-track-ui-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-graph-phi-orchestrator-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-models-dragon-curve-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
