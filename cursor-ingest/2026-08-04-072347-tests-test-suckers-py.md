# tests / test_suckers.py

#source #python

> path: tests/test_suckers.py  
> ext: .py  

---

# tests / test_suckers.py


Tests for models.suckers.LoRASucker and SuckerPool (15 tests).

Coverage:
  - B=0 init means output is zero at spawn
  - One gradient step makes output non-zero
  - Warm-start from BERT projection weight (both row and transposed layouts)
  - Pool spawns above threshold, silent below
  - Device-agnostic: suckers operate on plain numpy arrays


Defines: make_sucker, random_R, TestBZeroInit, TestGradientStep, TestWarmStart, TestSuckerPool, test_B_is_zero_at_spawn, test_output_is_zero_at_spawn, test_is_active_false_before_update, test_one_step_makes_output_nonzero, test_is_active_after_update, test_loss_returned_from_update, test_repeated_steps_reduce_loss, test_row_layout_accepted, test_transposed_layout_accepted, test_incompatible_shape_raises, test_warmstart_B_still_zero, test_spawn_above_threshold, test_silent_below_threshold, test_max_suckers_cap_respected, test_forward_all_zero_before_updates, test_device_agnostic_float32, test_spawn_log_records_event

---

## Semantic links

→ [[models-suckers]]
→ [[pipeline-vpn-relay-pool]]
→ [[scripts-pretrain-loop]]
→ [[mcp-server-tools-sims]]
→ [[models-init]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-models-suckers-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-gnn-lora-sucker-py]]
→ [[cursor-ingest/2026-08-04-072347-source-models-suckers-md]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-vpn-manager-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-prefeed-shuffle-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
