# tests / test_cairrn_dispatch.py

#source #python

> path: tests/test_cairrn_dispatch.py  
> ext: .py  

---

# tests / test_cairrn_dispatch.py


Tests for engine/cairrn_dispatch.py — CAIRRN-bound action dispatcher.

Synthetic subsystems only — no disk I/O, no workers.cairrn calls.


Defines: _make_index, _make_dispatcher, _action, TestConstruction, TestPhiAction, TestEnqueue, TestGate, TestDispatchActions, TestPrefeed, TestForceDispatch, TestDispatchResult, TestState, TestDoubleRouteWatchdog, test_defaults, test_tau_clamped_positive, test_factory, test_all_kinds, test_unique_ids, test_as_dict, test_priority_default_zero, test_enqueue_returns_depth, test_urgent_sorted_to_front, test_deferred_sorted_to_back, test_fifo_within_same_priority, test_gate_closed_at_zero_steps, test_gate_open_after_many_steps, test_step_gated_after_enough_steps, test_step_skipped_when_incoherent, test_skip_increments_steps, test_gate_open_resets_steps, test_ticks_run_increments_on_gate, test_shard_inject_dispatched, test_hub_inject_dispatched, test_propagate_dispatched, test_empty_queue_still_gates, test_queue_drains_one_per_step, test_temporal_rec_without_temporal_index, test_temporal_rec_with_index, test_prefeed_runs_for_shuffle_next_when_gate_closed, test_prefeed_not_repeated_for_same_action

---

## Semantic links

→ [[engine-cairrn-dispatch]]
→ [[workers-cairrn-worker]]
→ [[workers-cairrn-desktop]]
→ [[workers-cairrn-init]]
→ [[engine-cairrn-scheduler]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-tests-test-cairrn-scheduler-py]]
→ [[cursor-ingest/2026-08-04-072347-source-engine-cairrn-dispatch-md]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-hot-loader-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-prefeed-shuffle-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-cairrn-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
