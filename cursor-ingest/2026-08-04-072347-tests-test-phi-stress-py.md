# tests / test_phi_stress.py

#source #python

> path: tests/test_phi_stress.py  
> ext: .py  

---

# tests / test_phi_stress.py


Stress tests for the CAIRRN phi dispatcher — edge cases and weak points.

Covers:
  BUG-1  shard_index silently wraps via modulo (out-of-range → aliased shard)
  BUG-2  phi_flush reports success even on execution errors (no error propagation)
  BUG-3  DoubleRouteWatchdog never attached in make_dispatcher() — silent double-routes
  OBS-1  Coherence gate is a permanent open latch (once open, stays open forever)
  OBS-2  _prefeed_clip / _prefeed_shuffle_next release RLock mid-step
  EDGE   Canonical error paths: MYCELIAL_TICK no substrate, LOAD_TRACK no path,
         HOVER_PREFETCH empty payloa

Defines: _make_index, _dispatcher, d, TestShardIndexWrap, TestFlushErrorTransparency, TestWatchdogAbsent, TestGateLatch, TestPrefeedLockRelease, TestQueueFlood, TestPriorityExtremes, TestPrefeedInvalidation, TestConcurrency, test_out_of_range_index_wraps_silently, test_result_lies_about_actual_shard, test_negative_index_also_wraps, test_large_index_stress, test_mycelial_error_in_flush_result, test_load_track_no_path_error_in_result, test_hover_prefetch_empty_payload_error_in_result, test_flush_loop_sees_error_results_as_gated_true, test_cairrn_run_invalid_hub_error_in_result, test_temporal_rec_no_index_error, test_shuffle_next_no_shuffle_error, test_shuffle_seed_no_shuffle_error, test_dispatcher_has_no_watchdog_by_default, test_make_dispatcher_no_watchdog, test_double_route_not_counted_without_watchdog, test_double_route_detected_once_watchdog_attached, test_gate_stays_open_after_repeated_steps, test_coherence_decays_only_in_closed_state, test_once_closed_reopens_only_after_reset, test_gate_resets_on_dispatch, test_concurrent_enqueue_during_prefeed_clip, test_enqueue_200_actions_sorts_correctly, test_flush_200_actions_no_exception, test_priority_interleave_fifo_within_band, test_empty_flush_returns_zero, test_step_empty_queue_gate_open, test_extreme_negative_priority_goes_to_front, test_extreme_positive_priority_goes_to_back

---

## Semantic links

→ [[engine-cairrn-dispatch]]
→ [[engine-cairrn-scheduler]]
→ [[mcp-server-tools-phi-dispatch]]
→ [[engine-hot-loader]]
→ [[workers-cairrn-layers]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-engine-cairrn-dispatch-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-cairrn-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-cairrn-dispatch-py]]
→ [[cursor-ingest/2026-08-04-072347-mcp-server-tools-phi-dispatch-py]]
→ [[cursor-ingest/2026-08-04-072347-engine-cairrn-scheduler-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
