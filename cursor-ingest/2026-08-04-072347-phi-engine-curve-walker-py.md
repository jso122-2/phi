# phi / engine / curve_walker.py

#source #python

> path: phi/engine/curve_walker.py  
> ext: .py  

---

# phi / engine / curve_walker.py

phi.engine.curve_walker — CurveWalker: sort the queue by dragon-curve position.

Every track gets a segment index (0 … n_segments-1) that represents where it
sits along the dragon-curve path.  Sorting the queue by this index produces a
"curve walk": a continuous traversal from one end of the curve to the other,
moving through the library in order of musical character (BPM × Key projection
space).

Segment assignment priority
---------------------------
1. ``clipper_x / clipper_y`` from the annotations table (set by the anchor
   workflow or BPM×Key auto-compute).
2. BPM × Key projection from t

Defines: CurveWalker, __init__, _seg_indices, build_order, seg_map, segment_for

---

## Semantic links

→ [[engine-phi-player]]
→ [[scripts-train-d4]]
→ [[engine-phi-session]]
→ [[engine-cairrn-dispatch]]
→ [[engine-cairrn-scheduler]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-engine-curve-daemon-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-rooms-dragon-room-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-models-dragon-curve-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-meta-track-index-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-core-queue-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
