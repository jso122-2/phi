# phi / ui / _app / _navigation.py

#source #python

> path: phi/ui/_app/_navigation.py  
> ext: .py  

---

# phi / ui / _app / _navigation.py

phi.ui._app._navigation — page navigation and ML table switching.

CAIRRN scheduling
-----------------
Frame switch and on_show() are always synchronous — zero added latency.
root_pulse() runs after on_show() so the harmonic ring activation reflects
the fully-loaded page state.  The result gates follow-on expensive refresh
work (on_refresh) but never gates the initial frame show.

Latency contract:
    pack/pack_forget  → synchronous, immediate                 (Tk layout)
    on_show()         → synchronous, immediate                 (frame init)
    root_pulse()      → synchronous, after on_s

Defines: _NavigationMixin, go_to_page, toggle_page, toggle_rooms, toggle_ml_table, _enter_ml_table, _leave_ml_table, ml_next_page, ml_prev_page, navigate_deeper, _cairrn_route_key, toggle_z_spine, _enter_z_spine, _leave_z_spine, z_next_page, z_prev_page

---

## Semantic links

→ [[engine-cairrn-scheduler]]
→ [[engine-cairrn-dispatch]]
→ [[engine-phi-player]]
→ [[cairrn]]
→ [[sims-temporal]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-engine-cairrn-scheduler-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-app-track-ui-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-engine-init-py]]
→ [[cursor-ingest/2026-08-04-072347-engine-cairrn-dispatch-py]]
→ [[cursor-ingest/2026-08-04-072347-engine-phi-player-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
