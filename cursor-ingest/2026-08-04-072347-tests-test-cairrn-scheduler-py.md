# tests / test_cairrn_scheduler.py

#source #python

> path: tests/test_cairrn_scheduler.py  
> ext: .py  

---

# tests / test_cairrn_scheduler.py


Tests for CAIRRNScheduler — engine/cairrn_scheduler.py.

Synthetic PhiTracerSession (no disk I/O).


Defines: _make_summary, _make_snap, _make_session_mock, TestConstruction, TestGate, TestDispatch, TestForceTick, TestSchedulerResult, TestState, TestFactory, test_defaults, test_custom_params, test_tau_clamped_to_positive, test_first_step_coherence_is_zero_gate_closed, test_gate_blocked_when_incoherent, test_skipped_increments_steps, test_gated_tick_resets_steps, test_gated_increments_ticks_run, test_plain_tick_by_default, test_force_refresh_triggers_refresh_and_tick, test_auto_refresh_at_interval, test_no_refresh_ran_on_plain_tick, test_force_tick_bypasses_gate, test_force_tick_with_refresh, test_force_tick_resets_steps, test_result_fields_present, test_as_dict_gated, test_as_dict_skipped_no_summary, test_state_dict_keys, test_gate_closed_after_reset, test_repr_contains_coherence, test_make_cairrn_scheduler_returns_instance

---

## Semantic links

→ [[engine-cairrn-scheduler]]
→ [[engine-phi-session]]
→ [[engine-cairrn-dispatch]]
→ [[engine-cursor-tracer]]
→ [[engine-cairrn-tracer-daemon]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-tests-test-cairrn-dispatch-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-prefeed-shuffle-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-phi-player-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-phi-session-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-hot-loader-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
