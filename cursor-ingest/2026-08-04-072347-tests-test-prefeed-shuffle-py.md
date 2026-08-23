# tests / test_prefeed_shuffle.py

#source #python

> path: tests/test_prefeed_shuffle.py  
> ext: .py  

---

# tests / test_prefeed_shuffle.py


Tests for engine/prefeed_shuffle.py — CAIRRN-bound prefeed shuffle.

Synthetic session only — no disk I/O.


Defines: _make_snap, _make_harmonic, _make_session, TestProjectionMatrix, TestHarmonicScores, TestShuffleOrder, TestPrefeedShuffle, TestCAIRRNPrefeedShuffle, TestFactory, test_shape, test_rows_normalised, test_deterministic, test_shape, test_empty_H, test_no_exploration_is_deterministic, test_high_shard_activation_influences_order, test_length, test_is_permutation, test_indices_in_range, test_next_raises_before_commit, test_prefeed_populates_pending, test_commit_swaps_buffers, test_commit_empty_pending_returns_false, test_next_returns_valid_index, test_next_advances_cursor, test_next_wraps_around, test_prefeed_overwrites_pending, test_commit_resets_cursor, test_empty_snapshot_prefeed, test_peek_returns_correct_count, test_peek_empty_active, test_peek_does_not_advance_cursor, test_peek_pending_ready_flag, test_repr_contains_key_info, test_seed_populates_active, test_seed_raises_without_build, test_step_returns_step_result, test_first_step_coherence_zero_gate_closed, test_step_skipped_when_incoherent, test_skip_prefeed_updates_pending

---

## Semantic links

→ [[mcp-server-tools-prefeed-shuffle]]
→ [[engine-prefeed-shuffle]]
→ [[scripts-pretrain-loop]]
→ [[engine-phi-player]]
→ [[engine-phi-session]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-tests-test-cairrn-scheduler-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-hot-loader-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-cairrn-dispatch-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-phi-player-py]]
→ [[cursor-ingest/2026-08-04-072347-source-engine-prefeed-shuffle-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
