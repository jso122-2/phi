# tests / test_tracer_daemon.py

#source #python

> path: tests/test_tracer_daemon.py  
> ext: .py  

---

# tests / test_tracer_daemon.py


Tests for engine.tracer_daemon.TracerDaemon (14 tests).

Coverage:
  - Cold start always spawns ≥1 tracer with SPAWN_COLD_START condition
  - TracerSummary has all 8 arm fields + aggregated_tag + aggregated_merge
  - Ana-Chi weight decreases with tick (rattling decay property)
  - Harmonic index changes after run_once() (arm → CAIRRN routing live)
  - max_tracers cap respected
  - Tick gate fires at configured interval


Defines: small_A, make_daemon, TestColdStart, TestTracerSummaryFields, TestAnaChiDecay, TestHarmonicIndexLive, TestMaxTracersCap, TestTickGate, test_first_run_spawns_at_least_one_tracer, test_first_tracer_has_cold_start_condition, test_cold_start_only_on_first_tick, test_summary_has_all_8_arm_fields, test_summary_has_aggregated_tag, test_summary_has_aggregated_merge, test_aggregated_tag_equals_arm_tag, test_aggregated_merge_equals_arm_merge, test_summary_as_dict_has_all_keys, test_weight_decreases_with_ticks, test_weight_strictly_positive, test_index_changes_after_run_once, test_cap_respected_over_many_ticks, test_tick_gate_fires_at_interval

---

## Semantic links

→ [[engine-tracer-daemon]]
→ [[scripts-spawn-tracer]]
→ [[engine-cairrn-tracer-daemon]]
→ [[engine-init]]
→ [[engine-cursor-tracer]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-engine-tracer-daemon-py]]
→ [[cursor-ingest/2026-08-04-072347-source-engine-tracer-daemon-md]]
→ [[cursor-ingest/2026-08-04-072347-source-engine-cairrn-tracer-daemon-md]]
→ [[cursor-ingest/2026-08-04-072347-scripts-spawn-tracer-py]]
→ [[cursor-ingest/2026-08-04-072347-engine-cairrn-tracer-daemon-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
