# tests / test_hot_loader.py

#source #python

> path: tests/test_hot_loader.py  
> ext: .py  

---

# tests / test_hot_loader.py


Tests for engine/hot_loader.py — CAIRRNHotLoader speculative prefetch engine.

No disk I/O. All load_fns return synthetic values.


Defines: _immediate_loader, _sync_load, _slow_load, TestRegister, TestSignal, TestStep, TestGet, TestInvalidate, TestThreadSafety, TestState, TestHotLoadMetrics, TestMetricsAccumulation, test_register_adds_entry, test_register_overwrite_preserves_loaded_result, test_register_and_signal_marks_pending, test_unregister, test_max_entries_evicts_oldest, test_max_entries_zero_disables_eviction, test_signal_marks_pending_and_fires, test_signal_unknown_returns_false, test_signal_loaded_entry_is_noop, test_step_fires_when_signal_returns_true, test_step_does_not_fire_when_signal_false, test_step_does_not_double_fire_loading_entry, test_step_result_fields, test_step_ready_list_reflects_loaded_entries, test_as_dict, test_get_returns_none_before_load, test_get_returns_value_after_load, test_get_nonexistent_returns_none, test_is_ready, test_invalidate_clears_result, test_invalidate_allows_reload, test_invalidate_all, test_concurrent_register_and_get, test_load_fn_exception_is_non_fatal, test_state_keys, test_summary_keys, test_repr_contains_total, test_defaults_zero

---

## Semantic links

→ [[engine-hot-loader]]
→ [[scripts-pretrain-loop]]
→ [[engine-tracer-daemon]]
→ [[engine-index]]
→ [[workers-cairrn-layers]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-engine-hot-loader-md]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-prefeed-shuffle-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-cairrn-dispatch-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-cairrn-scheduler-py]]
→ [[cursor-ingest/2026-08-04-072347-engine-hot-loader-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
