# phi / ui / qt / rooms / queue_room.py

#source #python

> path: phi/ui/qt/rooms/queue_room.py  
> ext: .py  

---

# phi / ui / qt / rooms / queue_room.py

phi.ui.qt.rooms.queue_room — live playback queue + CAIRRN dispatch panel.

The magnum opus room.  Three vertical zones:

  ┌─────────────────────────────────────────────────────────────┐
  │  NOW PLAYING  —  album art · title · artist · progress      │  [A]
  ├──────────────────┬──────────────────────────────────────────┤
  │  CAIRRN DISPATCH │  UP NEXT  ──────────── GNN nudge ♻      │  [B]
  │  coherence bar   │  ▶ [locked]  Title · Artist  dur         │
  │  queue depth     │    [locked]  …                           │
  │  action log      │    …  (drag-reorderable)                 │
  │  [St

Defines: _art_bytes_to_pixmap, _DragHandleDelegate, _QueueListWidget, _NowPlayingStrip, _CAIRRNPanel, _UpNextHeader, QueueRoom, paint, sizeHint, __init__, dropEvent, _on_double_click, __init__, _build, sync, set_art_pixmap, __init__, _build, sync_dispatcher, append_log, _on_step, _on_flush, __init__, _build, set_count, _on_export, _on_clear, __init__, _build, on_show, on_refresh, hideEvent, sync_transport, mark_playing, refresh_queue, _highlight_current, _refresh_cairrn, on_gnn_nudge

---

## Semantic links

→ [[engine-phi-player]]
→ [[PLAYBACK]]
→ [[engine-prefeed-shuffle]]
→ [[2026-07-28-230105-remaining-refactor-pass-port-all-remaining]]
→ [[engine-cairrn-dispatch]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-rooms-mixer-room-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-rooms-genre-room-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-rooms-playlist-room-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-app-queue-ops-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-rooms-library-room-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
