# tests / test_temporal.py

#source #python

> path: tests/test_temporal.py  
> ext: .py  

---

# tests / test_temporal.py


Tests for sims/temporal.py — CAIRRN-aware, Ana-Chi hosted temporal sharding index.

Coverage
--------
  CAIRRN_HUBS                      — all five hubs present and ordered correctly
  HubTemporalTrace.build()         — correct basin/decay from CAIRRN hub
  HubTemporalTrace.record()        — t=0 window accumulates activation
  HubTemporalTrace.advance()       — decay + slide + re-index
  HubTemporalTrace.activation_at() — correct lag retrieval, OOB → 0.0
  HubTemporalTrace.total_activation()
  TemporalShardIndex construction  — n_windows < 2 raises ValueError
  TemporalShardIndex.record()    

Defines: TestCairrnHubs, TestTemporalShard, TestHubTemporalTrace, TestTemporalShardIndexConstruction, TestTemporalShardIndexRecord, TestTemporalShardIndexAdvance, TestTemporalShardIndexReset, TestDominant, TestHubTotals, TestTemporalVector, TestAnaChiCoherence, TestAnaChiState, TestState, TestAnaChiHosting, TestTemporalDecayMonotonicity, test_five_hubs, test_all_canonical_hubs_present, test_hub_basin_alignment, test_default_activation_zero, test_decay_multiplies_activation, test_decay_full_rate_one, test_decay_zero, test_build_home, test_build_math, test_build_commands, test_initial_windows_count, test_initial_all_zero, test_record_adds_to_t0, test_record_accumulates, test_activation_at_oob_returns_zero, test_advance_decays_existing, test_advance_prepends_empty_window, test_advance_does_not_grow_windows, test_advance_reindexes_t, test_total_activation_sums_all_windows, test_state_keys, test_default_n_windows, test_custom_n_windows, test_n_windows_too_small_raises, test_five_traces_built

---

## Semantic links

→ [[temporal-index]]
→ [[temporal-index]]
→ [[mcp-server-tools-temporal]]
→ [[sims-temporal]]
→ [[2026-07-13-102400-temporal-sharding-index-cairrn-aware-ana-chi-hosted]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-tests-test-cairrn-py]]
→ [[cursor-ingest/2026-08-04-072347-sims-temporal-py]]
→ [[cursor-ingest/2026-08-04-072347-source-sims-temporal-md]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-hub-classifier-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-bridge-factory-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
