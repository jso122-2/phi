# phi / watch / enrich_daemon.py

#source #python

> path: phi/watch/enrich_daemon.py  
> ext: .py  

---

# phi / watch / enrich_daemon.py

phi.watch.enrich_daemon — background metadata enrichment worker.

Processes library tracks one at a time, rate-limited, pausing during
playback so it never competes with the audio engine for I/O or CPU.

Usage (in PhiApp.__init__)
--------------------------
    self.enrich = EnrichDaemon(
        library=self.library,
        review_queue=self.review_queue,
        is_playing=lambda: self.player.is_busy(),
        on_progress=self._on_enrich_progress,   # called on main thread via after()
        schedule=self.after,
    )
    self.enrich.start()

    # Later, once OctopusOrganizer has run:
  

Defines: EnrichProgress, EnrichDaemon, pct, status_line, __init__, set_plan, bind_floor, start, stop, progress, _run, _unenriched_paths, _acoustid_retry_due, _process, _apply_result, _update_track_store, _notify, _on_commands_shift, _apply

---

## Semantic links

→ [[scripts-embed-tracks]]
→ [[engine-phi-player]]
→ [[engine-phi-session]]
→ [[engine-cairrn-scheduler]]
→ [[engine-tracer-daemon]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-watch-watcher-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-watch-librosa-worker-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-meta-extract-worker-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-core-race-watcher-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-watch-init-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
