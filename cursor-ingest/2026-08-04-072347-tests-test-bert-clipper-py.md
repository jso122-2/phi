# tests / test_bert_clipper.py

#source #python

> path: tests/test_bert_clipper.py  
> ext: .py  

---

# tests / test_bert_clipper.py


Tests for models.bert_clipper.BERTClipper.

Coverage:
  - encode() output shapes and types
  - tau is strictly positive
  - lora_proj shape matches (d, lora_rank)
  - lora_proj is a slice of last layer's W_O
  - encode() is deterministic for the same input
  - different inputs produce different H
  - update() returns a float loss
  - update() changes W_emb and W_out
  - update() gradient clipping: large gradient norm is clamped
  - n_params > 0
  - import from models package
  - d_in != d (non-square embedding)
  - TracerDaemon.bert + lora_proj properties live after first run_once()


Defines: make_clipper, random_X, TestEncodeShapes, TestEncodeDeterminism, TestUpdate, TestNParams, TestNonSquareEmbed, TestPackageImport, TestTracerDaemonBERTIntegration, test_H_shape, test_tau_is_positive_float, test_lora_proj_shape, test_lora_proj_is_copy_of_last_W_O, test_single_node, test_large_N, test_same_input_same_output, test_different_inputs_different_H, test_update_returns_float, test_update_changes_W_emb, test_update_changes_W_out, test_attention_weights_unchanged_after_update, test_gradient_clipping_limits_weight_change, test_explicit_target, test_multiple_steps_loss_finite, test_n_params_positive, test_n_params_scales_with_d, test_d_in_less_than_d, test_import_from_models, _ring_A, test_daemon_has_bert_property, test_lora_proj_none_before_first_tick, test_lora_proj_set_after_run_once, test_lora_proj_matches_last_W_O_slice, test_bert_weights_change_after_run_once

---

## Semantic links

→ [[models-bert-clipper]]
→ [[models-suckers]]
→ [[models-init]]
→ [[models-regression]]
→ [[mcp-server-tools-phi-clip]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-models-bert-clipper-md]]
→ [[cursor-ingest/2026-08-04-072347-models-bert-clipper-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-models-bert-encoder-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-gemini-clipper-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-suckers-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
