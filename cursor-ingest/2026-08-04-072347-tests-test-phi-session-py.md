# tests / test_phi_session.py

#source #python

> path: tests/test_phi_session.py  
> ext: .py  

---

# tests / test_phi_session.py


Tests for PhiTracerSession — the OctopusTracer/phi wiring.

All tests use synthetic PhiGraph (no disk I/O) and a real TracerDaemon.
Integration tests at the bottom require the actual library.


Defines: make_snap, make_session, TestPhiTracerSessionConstruction, TestPhiTracerSessionTick, TestRefreshAndTick, TestHarmonicIndexIntegration, TestMakePhiSession, TestPhiSessionRealLibrary, test_snapshot_none_before_build, test_n_tracks_zero_before_build, test_tick_raises_before_build, test_build_populates_snapshot, test_n_tracks_after_build, test_repr_after_build, test_tick_returns_tracer_summary, test_tick_increments_daemon_tick, test_cold_start_spawns_tracer, test_tracer_count_bounded_by_max, test_summary_fields_populated, test_summary_arm_scores_finite, test_multiple_ticks_stable, test_refresh_calls_build, test_refresh_and_tick_returns_summary, test_refresh_updates_snapshot, test_harmonic_index_changes_after_tick, test_bridge_tick_advances, test_harmonic_activations_bounded, test_returns_phi_tracer_session, test_snapshot_none_before_build, test_d_matches_clap_proj_output, test_custom_edge_threshold, test_custom_max_tracers, test_build_and_tick, test_three_ticks_stable

---

## Semantic links

→ [[engine-phi-session]]
→ [[engine-tracer-daemon]]
→ [[engine-init]]
→ [[2026-07-17T02-45-15Z-OctopusTracer v1 — Full Integration Summary]]
→ [[engine-cairrn-tracer-daemon]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-tests-test-phi-session-clip-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-cairrn-scheduler-py]]
→ [[cursor-ingest/2026-08-04-072347-engine-phi-session-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-phi-graph-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-graph-phi-tracer-bridge-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
