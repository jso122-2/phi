# tests / test_mycelial_substrate.py

#source #python

> path: tests/test_mycelial_substrate.py  
> ext: .py  

---

# tests / test_mycelial_substrate.py


tests/test_mycelial_substrate.py — integration tests for MycelialSubstrate.

Tests the full wiring:
  MycelialSubstrate ← workers/cairrn/mycelial.py (pure formulas)
  MycelialSubstrate ← PhiGraphSnapshot (tracks, H, A)
  MycelialSubstrate → CAIRRNDispatcher (MYCELIAL_TICK action)

Uses a minimal fake snapshot and a stub harmonic index — no real library scan.


Defines: FakeTrack, FakeSnapshot, FakeShard, FakeHarmonicIndex, _make_snapshot, _make_substrate, TestConstruction, TestTick, TestDefaultBudget, TestEdgeWeights, TestAccessors, TestRebind, TestDispatcherIntegration, TestGrowthGate, TestDisconnectedGraph, TestSerialization, N, __init__, __init__, inject_from_hub, inject, propagate, test_init_energy_zeros, test_init_weights_from_adjacency, test_init_tick_count_zero, test_repr, test_state_dict, test_returns_tick_result, test_tick_count_increments, test_result_tick_index_matches, test_energy_increases_after_tick_with_budget, test_energy_clamped_to_e_max, test_energy_nonnegative, test_tick_result_n_nodes, test_tick_result_budget_used_nonneg, test_tick_zero_budget_no_energy, test_default_budget_no_crash, test_higher_code_act_more_energy, test_weights_stay_nonneg, test_cold_edges_decay

---

## Semantic links

→ [[engine-mycelial-substrate]]
→ [[workers-cairrn-mycelial]]
→ [[engine-mycelial]]
→ [[sims-temporal]]
→ [[mcp-server-tools-harmonic]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-tests-test-cairrn-mycelial-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-harmonic-py]]
→ [[cursor-ingest/2026-08-04-072347-engine-mycelial-substrate-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-phi-session-py]]
→ [[cursor-ingest/2026-08-04-072347-source-engine-mycelial-substrate-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
