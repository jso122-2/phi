# phi / engine / arc_engine.py

#source #python

> path: phi/engine/arc_engine.py  
> ext: .py  

---

# phi / engine / arc_engine.py

phi.engine.arc_engine — Session Arc Engine.

Maintains a target D4_A trajectory (the "arc") for the current session and
picks the next track from the library to keep playback on that trajectory.

Arc shapes
----------
FLAT    — constant energy (D4_A stays near the middle of the range)
RISING  — energy climbs linearly over the session horizon
FALLING — energy falls linearly
PEAK    — rises to a peak at the halfway point then decays (parabola)
VALLEY  — inverse of PEAK — dip then recovery
WAVE    — one full sinusoidal oscillation over the horizon

D4_A values are normalised to [0, 1] (per-segmen

Defines: ArcShape, ArcEngine, __init__, target, d4a_norm_for_seg, _ring_coherence, pick_next, on_track_played, reset

---

## Semantic links

→ [[scripts-train-d4]]
→ [[engine-phi-session]]
→ [[2026-02-18-012004-poster]]
→ [[scripts-pretrain-loop]]
→ [[engine-phi-player]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-engine-arc-scorer-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-engine-curve-daemon-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-engine-curve-walker-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-utils-perpetual-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-core-playback-controller-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
