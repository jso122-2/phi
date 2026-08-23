# phi / ui / qt / rooms / dragon_room.py

#source #python

> path: phi/ui/qt/rooms/dragon_room.py  
> ext: .py  

---

# phi / ui / qt / rooms / dragon_room.py

phi.ui.qt.rooms.dragon_room — Dragon Curve ML room  (entry point of the ML route).

The dragon curve is the aesthetic and score-normalisation basis for the entire
ML pipeline.  This room is the first step: it projects each track onto the
curve using BPM × Key as the coordinate pair, producing (clipper_x, clipper_y)
that flows downstream through Inference → Forge.

Projection
----------
    x = BPM normalised over [60, 200]      — tempo axis
    y = Camelot wheel slot / 23            — harmonic axis (24 positions)

Auto-anchor: when a track is loaded and no prior anchor exists, the room
compute

Defines: MLDragonPage, __init__, _build, _make_header, _make_route_label, _on_queried, _on_hovered, _on_anchor, _on_curve_walk, _on_arc_shape_changed, _on_arc_mode_toggled, _on_depth_dec, _on_depth_inc, _on_nav_prev, _on_nav_next, on_show, on_refresh, refresh, sync_transport, update_transport, mark_playing, _compute_and_save_anchor, _current_track_bpm, _load_scatter, _on_scatter_hovered, set_playing

---

## Semantic links

→ [[scripts-train-d4]]
→ [[workers-cairrn-z-space]]
→ [[models-bert-clipper]]
→ [[engine-phi-session]]
→ [[engine-mycelial-substrate]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-rooms-dragon-coord-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-models-dragon-curve-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-engine-curve-daemon-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-engine-curve-walker-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-engine-zone-clusterer-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
