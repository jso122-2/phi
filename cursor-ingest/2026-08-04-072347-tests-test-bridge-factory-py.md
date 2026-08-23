# tests / test_bridge_factory.py

#source #python

> path: tests/test_bridge_factory.py  
> ext: .py  

---

# tests / test_bridge_factory.py


Tests for engine.bridge_factory.CAIRRNBridge (12 tests).

Regression guards:
  Bug 1 — spawn signals capture pre-reset coherence
  _incoherence_events cleared on next ingest cycle
  Both key formats (topology vs. graph_snapshot) → identical hub activations
  ingest_arm_scores() mutates index without stepping hub clocks or generating events
  Harmonic index bounded after repeated arm routing


Defines: fresh_bridge, all_arm_scores, TestSpawnSignalCoherence, TestIncoherenceEventClear, TestTopologyKeyFormats, TestIngestArmScores, TestIndexBounded, test_record_spawn_coherence_stores_value, test_incoherent_spawn_creates_event, test_coherent_spawn_no_event, test_event_captures_arm_and_coherence, test_clear_returns_events_and_empties_list, test_clear_idempotent, _nodes, test_topology_and_graph_snapshot_identical, test_empty_topology_returns_empty_dict, test_index_changes_after_ingest, test_no_incoherence_events_generated, test_arm_shard_map_coverage, test_activations_finite_after_100_ingest_cycles, test_make_bridge_factory, test_arm_shard_map_has_8_entries

---

## Semantic links

→ [[engine-bridge-factory]]
→ [[engine-arm-injector]]
→ [[engine-cairrn-bridge]]
→ [[engine-init]]
→ [[engine-rsync-bridge]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-engine-arm-injector-md]]
→ [[cursor-ingest/2026-08-04-072347-engine-arm-injector-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-pipeline-bridge-py]]
→ [[cursor-ingest/2026-08-04-072347-source-engine-bridge-factory-md]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-hub-classifier-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
