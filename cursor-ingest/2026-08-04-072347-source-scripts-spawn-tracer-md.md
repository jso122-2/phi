# source / scripts-spawn-tracer.md

#doc #md

> path: source/scripts-spawn-tracer.md  
> ext: .md  

---

# scripts/spawn_tracer

#code #module #scripts #code

> source_path: scripts/spawn_tracer.py  
> package: scripts  
> module: scripts/spawn_tracer  
> hub: CODE  
> created_ts:   

---

**Package:** `scripts`  
**Module:** `scripts/spawn_tracer`  
**Source:** `scripts/spawn_tracer.py`

spawn_tracer.py — OctopusTracer spawn daemon (single-instance, change-aware).

Loads SambaOrchestrator from checkpoint, creates a CAIRRN-bound TracerDaemon,
and runs the gardening loop autonomously — printing live spawn events,
arm scores, CAIRRN hub state, and sucker growth to the console.

Single-instance guarantee
─────────────────────────
An exclusive file-lock on /tmp/samba_octopus.lock is acquired at startup.
Any subsequent launch will detect the lock and exit immediately with a clear
message.  The lock is released automatically on exit or crash — no stale PID
files to clean up manually.

Refresh triggers
─────────────────
Instead of a dumb fixed-interval sleep, the daemon uses a two-level timer:

  fast poll  (--poll-interval, default 5s)
      Wakes every N seconds and checks whether any vault file has been
      modified (mtime scan on the watched paths).  Only triggers a full
      re-encode + tracer cycle when:
        (a) at least one file changed, OR
        (b) time since last cycle ≥ --max-interval (default 300s)

  This gives near-real-time response to vault edits while avoiding
  expensive re-encoding when nothing has changed.

Usage:
    micromamba run -n spot python spawn_tracer.py
    micromamba run -n spot python spawn_tracer.py --checkpoint checkpoints/best.pt
    micromamba run -n spot python spawn_tracer.py --poll-interval 5 --max-interval 300
    micromamba run -n spot python spawn_tracer.py --dry-run
    micromamba run -n spot python spawn_tracer.py --once

Options:
    --checkpoint PATH    Model checkpoint (default: auto-detect best.pt)
    --config PATH        Config file (default: config/config.yaml)
    --poll-interval N    Seconds between vault-change po

---

## Semantic links

→ [[scripts-spawn-tracer]]
→ [[engine-tracer-daemon]]
→ [[engine-cairrn-tracer-daemon]]
→ [[engine-init]]
→ [[engine-cursor-tracer]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-engine-tracer-daemon-md]]
→ [[cursor-ingest/2026-08-04-072347-scripts-spawn-tracer-py]]
→ [[cursor-ingest/2026-08-04-072347-engine-tracer-daemon-py]]
→ [[cursor-ingest/2026-08-04-072347-engine-init-py]]
→ [[cursor-ingest/2026-08-04-072347-engine-cairrn-tracer-daemon-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
