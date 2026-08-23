# source / engine-init.md

#doc #md

> path: source/engine-init.md  
> ext: .md  

---

# engine/__init__

#code #module #engine #code

> source_path: engine/__init__.py  
> package: engine  
> module: engine/__init__  
> hub: CODE  
> created_ts:   

---

**Package:** `engine`  
**Module:** `engine/__init__`  
**Source:** `engine/__init__.py`

OctopusTracer engine package.

    from engine.gate import gate_coherence, gate_pass, COHERENCE_THRESHOLD
    from engine.bridge_factory import CAIRRNBridge, make_bridge, ARM_SHARD_MAP
    from engine.tracer_daemon import TracerDaemon, TracerSummary, Tracer
    from engine.tracer_daemon import (
        SPAWN_COLD_START, SPAWN_SHARD_DROP, SPAWN_DEGREE_ANOMALY,
        SPAWN_EMBEDDING_DRIFT, SPAWN_TICK_GATE,
    )
    from engine.vault_writer import SambaWriter, SambaResult, SambaWrite, make_samba_writer
    from engine.phi_session import PhiTracerSession, make_phi_session
    from engine.cairrn_scheduler import CAIRRNScheduler, SchedulerResult, make_cairrn_scheduler
    from engine.cairrn_dispatch import CAIRRNDispatcher, PhiAction, PhiActionKind, make_dispatcher
    from engine.hot_loader import CAIRRNHotLoader, HotLoadResult, HotLoadMetrics
    from engine.mycelial_substrate import MycelialSubstrate, MycelialTickResult
    from engine.cursor_tracer import CursorTracer, CursorSample, HoverRegion
    from engine.prefeed_shuffle import CAIRRNPrefeedShuffle, make_prefeed_shuffle
    from engine.phi_player import (
        PhiPlayer, PhiPipeline, PlayEvent,
        make_phi_player, make_phi_pipeline,
        FRAC_LOVED, FRAC_HEARD,
    )

Pipeline shortcut (wires all components from a built session in one call):

    session = make_phi_session()
    session.build()
    pipeline = make_phi_pipeline(
        session,
        hover_regions=[
            HoverRegion("play",  x=690, y=820, w=52,  h=52),
            HoverRegion("next",  x=742, y=820, w=60,  h=60),
            HoverRegion("prev",  x=630, y=820, w=60,  h=60),
        ],
    )
    pipeline.tracer.start()        # cursor daemon live
    track = pipeline.play

---

## Semantic links

→ [[engine-init]]
→ [[engine-gate]]
→ [[engine-main]]
→ [[engine-tracer-daemon]]
→ [[models-init]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-engine-init-py]]
→ [[cursor-ingest/2026-08-04-072347-source-engine-gate-md]]
→ [[cursor-ingest/2026-08-04-072347-source-models-init-md]]
→ [[cursor-ingest/2026-08-04-072347-source-engine-cairrn-bridge-md]]
→ [[cursor-ingest/2026-08-04-072347-source-engine-tracer-daemon-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
