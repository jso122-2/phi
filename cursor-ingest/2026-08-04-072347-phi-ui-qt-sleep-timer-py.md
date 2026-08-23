# phi / ui / qt / sleep_timer.py

#source #python

> path: phi/ui/qt/sleep_timer.py  
> ext: .py  

---

# phi / ui / qt / sleep_timer.py

phi.ui.qt.sleep_timer — sleep timer engine + Qt dialog.

Replaces phi.ui.sleep_timer (Tkinter).

Public API
----------
    SleepTimer(schedule, on_expire, on_tick)  — framework-agnostic countdown
    SleepTimerDialog(parent, ctrl)            — QDialog


Defines: SleepTimer, SleepTimerDialog, __init__, set, cancel, remaining, active, _tick, __init__, _build, _set, _set_custom, _cancel

---

## Semantic links

→ [[2026-07-28-230105-remaining-refactor-pass-port-all-remaining]]
→ [[engine-cairrn-scheduler]]
→ [[engine-cairrn-dispatch]]
→ [[engine-coherence-daemon]]
→ [[engine-phi-session]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-app-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-init-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-app-overlays-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-settings-dialog-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-main-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
