# phi / ui / qt / rooms / forge_room.py

#source #python

> path: phi/ui/qt/rooms/forge_room.py  
> ext: .py  

---

# phi / ui / qt / rooms / forge_room.py

phi.ui.qt.rooms.forge_room — ML Forge room.

Forge is the training / fitting station of the ML route.

Pipeline
--------
    1. MetaClipper.fit(library)         — build TF-IDF → SVD → PCA pipeline
       MetaClipper.run_batch(library)   — produce clipper_emb, clipper_x/y,
                                          fold_bits, d4_b for every track
    2. D4XGBoostModel.fit(anns, y)      — train XGBoost regressor
    3. Save both to ~/.phi/ checkpoints

Layout
------
┌──────────────────────────────────────────────────────────────────────┐
│  FORGE           ‹ Dragon · Inference · Forge ›        [F

Defines: _ForgeWorker, _ascii_bar, MLForgePage, __init__, _log, run, __init__, _build, _make_header, _make_route_label, _make_status_panel, _kv_inline, _make_log_panel, _make_importance_panel, _make_coverage_panel, _sep, _on_nav_prev, _on_nav_next, _on_forge, _on_forge_done, _on_forge_error, _append_log, _refresh_coverage, _write_annotations, _check_checkpoints, _library_items, on_show, on_refresh, refresh, sync_transport, update_transport, mark_playing, set_playing

---

## Semantic links

→ [[models-metadata-cluster]]
→ [[scripts-embed-tracks]]
→ [[psspps-pipeline]]
→ [[scripts-train-d4]]
→ [[tools-enrich-c7]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-rooms-dragon-room-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-models-meta-clipper-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-meta-dataset-export-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-engine-vault-context-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-engine-zone-clusterer-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
