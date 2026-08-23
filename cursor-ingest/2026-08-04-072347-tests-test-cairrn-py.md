# tests / test_cairrn.py

#source #python

> path: tests/test_cairrn.py  
> ext: .py  

---

# tests / test_cairrn.py


test_cairrn.py — direct (no MCP subprocess) CAIRRN layer tests.

Covers:
  Layer 1  — Ana-Chi basin modulation
  Layer 2  — neg_exp sharding
  Layer 3  — coherence enforcement + re-route
  Layer 4  — Active -Z scoring (ZScore, z_coherence, z_shard)
  Batch    — CAIRRNBatch, shard_summary, z_active_runs
  Index    — temporal index update on inject


Defines: run_hub, TestLayer1Modulation, TestLayer2Sharding, TestLayer3Coherence, TestLayer4ZScoring, TestCAIRRNBatch, TestRerouteTarget, test_modulation_home, test_modulation_all_hubs_positive, test_to_dict_has_modulation_fields, test_natural_shard_in_range, test_shard_ordering, test_neg_exp_fixed_point, test_neg_exp_one_step_present, test_coherence_in_range, test_ana_chi_coherence_present, test_ana_chi_coherence_in_range, test_home_ana_chi_coherence_is_one, test_commands_ana_chi_coherence_low, test_agent_context_routing_coherent_but_structurally_low, test_re_routed_field_present, test_coherent_consistent_with_threshold, _z_dfi, test_z_score_none_without_inputs, test_z_score_active_with_inputs, test_z_score_fields, test_z_coherence_consistent_with_threshold, test_to_dict_exposes_z_fields, test_to_dict_no_z_fields_without_inputs, test_compute_z_score_standalone, test_z_scoring_all_hubs, test_batch_runs_all_hubs, test_batch_result_has_cairrn_key, test_shard_summary_keys, test_shard_summary_has_required_fields, test_batch_z_active_runs, test_requested_hub_in_to_dict, test_reroute_uses_home_when_incoherent, _force_low

---

## Semantic links

→ [[workers-cairrn-layers]]
→ [[engine-cairrn-bridge]]
→ [[mcp-server-tools-cairrn]]
→ [[engine-cairrn-scheduler]]
→ [[workers-cairrn-init]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-workers-cairrn-layers-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-temporal-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-cairrn-dispatch-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-phi-stress-py]]
→ [[cursor-ingest/2026-08-04-072347-engine-cairrn-bridge-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
