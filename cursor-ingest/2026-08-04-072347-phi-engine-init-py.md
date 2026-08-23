# phi / engine / __init__.py

#source #python

> path: phi/engine/__init__.py  
> ext: .py  

---

# phi / engine / __init__.py

phi.engine — CAIRRN-backed computation substrate for PHI.

    Pages  are trees.
    Songs  (and their nesting — track → album → genre → mood) are leaves.
    CAIRRN is the forest floor.

All PHI operations flow through the CAIRRN three-layer pipeline before
computing.  The harmonic ring is a live waveform of PHI's state.

Quick start::

    from phi.engine import ForestFloor
    floor = ForestFloor()
    floor.leaf_falls("/music/track.mp3", completion_rate=0.88)
    floor.root_pulse("genre")
    print(floor.breathe())

---

## Semantic links

→ [[engine-cairrn-scheduler]]
→ [[engine-phi-player]]
→ [[engine-phi-session]]
→ [[engine-cairrn-dispatch]]
→ [[sims-harmonic]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-engine-cairrn-init-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-engine-cairrn-types-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-metadata-node-builder-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-engine-cairrn-floor-py]]
→ [[cursor-ingest/2026-08-04-072347-engine-cairrn-scheduler-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
