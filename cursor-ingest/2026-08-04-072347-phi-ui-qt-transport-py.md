# phi / ui / qt / transport.py

#source #python

> path: phi/ui/qt/transport.py  
> ext: .py  

---

# phi / ui / qt / transport.py

phi.ui.qt.transport — PySide6 transport bar.

Identical public API to phi.ui.transport.TransportPanel so every call site
in PhiMainWindow, PlaybackController, and PollEngine works unchanged.

Public API (mirrors TransportPanel)
------------------------------------
    set_seek(pos, duration)
    set_end(duration)
    reset_seek()
    set_playing(playing)
    set_shuffle(on)
    set_repeat(mode)
    set_mode_label(shuffle, repeat)
    set_volume(v)
    load_waveform(path)   # no-op — kept for compatibility
    is_seeking            # bool property


Defines: _VarCompat, TransportWidget, __init__, get, set, __init__, _build, _gated, is_seeking, load_waveform, set_seek, set_end, reset_seek, set_playing, set_shuffle, set_shuffle_mode, set_repeat, set_mode_label, set_volume, _on_seek_press, _on_seek_release, _on_seek_moved, _on_vol_changed

---

## Semantic links

→ [[2026-07-28-230105-remaining-refactor-pass-port-all-remaining]]
→ [[engine-phi-player]]
→ [[engine-phi-session]]
→ [[2026-07-16T19-50-20Z-phi floating UI + ASCII waveform — Layer 5 implementation]]
→ [[PLAYBACK]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-rooms-mini-transport-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-app-transport-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-app-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-playlist-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-main-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
