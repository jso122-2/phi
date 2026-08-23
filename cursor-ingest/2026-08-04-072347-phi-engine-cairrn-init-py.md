# phi / engine / cairrn / __init__.py

#source #python

> path: phi/engine/cairrn/__init__.py  
> ext: .py  

---

# phi / engine / cairrn / __init__.py

phi.engine.cairrn — standalone CAIRRN substrate for the phi application.

A self-contained, MCP-independent implementation of the three-layer CAIRRN
pipeline (Ana-Chi → neg_exp → coherence) with harmonic ring propagation,
watchdog health monitoring, forest-floor metaphor, and cold-start persistence.

Quick start
───────────
    from phi.engine.cairrn import ForestFloor

    floor = ForestFloor()
    floor.load_state()                       # restore last session (no-op on first launch)
    floor.warm_from_history(library)         # replay recent listening history

    floor.leaf_falls("/music/

---

## Semantic links

→ [[engine-cairrn-bridge]]
→ [[engine-cairrn-dispatch]]
→ [[engine-cairrn-scheduler]]
→ [[workers-cairrn-layers]]
→ [[mcp-server-tools-cairrn]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-engine-init-py]]
→ [[cursor-ingest/2026-08-04-072347-engine-cairrn-bridge-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-engine-cairrn-bridge-py]]
→ [[cursor-ingest/2026-08-04-072347-engine-cairrn-scheduler-py]]
→ [[cursor-ingest/2026-08-04-072347-workers-cairrn-layers-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
