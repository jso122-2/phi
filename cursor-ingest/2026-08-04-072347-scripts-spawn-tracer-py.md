# scripts / spawn_tracer.py

#source #python

> path: scripts/spawn_tracer.py  
> ext: .py  

---

# scripts / spawn_tracer.py


spawn_tracer.py — OctopusTracer spawn daemon (single-instance, change-aware).

Loads SambaOrchestrator from checkpoint, creates a CAIRRN-bound TracerDaemon,
and runs the gardening loop autonomously — printing live spawn events,
arm scores, CAIRRN hub state, and sucker growth to the console.

Single-instance guarantee
─────────────────────────
An exclusive file-lock on /tmp/samba_octopus.lock is acquired at startup.
Any subsequent launch will detect the lock and exit immediately with a clear
message.  The lock is released automatically on exit or crash — no stale PID
files to clean up manually

Defines: _setup_logging, _bar, _print_cycle_header, _print_cairrn, _print_summary, PericlesWatchdog, _apply_tracer_writes, _broadcast_cairrn_state, _drain_cairrn_cmds, _acquire_lock, _vault_mtime, run, _parse, __init__, begin, end, status_line, _resolve_vault_hb_path, _write_heartbeat, _should_run

---

## Semantic links

→ [[scripts-spawn-tracer]]
→ [[engine-cairrn-tracer-daemon]]
→ [[engine-tracer-daemon]]
→ [[engine-init]]
→ [[engine-gate]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-scripts-spawn-tracer-md]]
→ [[cursor-ingest/2026-08-04-072347-source-engine-tracer-daemon-md]]
→ [[cursor-ingest/2026-08-04-072347-engine-tracer-daemon-py]]
→ [[cursor-ingest/2026-08-04-072347-engine-cairrn-tracer-daemon-py]]
→ [[cursor-ingest/2026-08-04-072347-engine-init-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
