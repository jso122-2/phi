# tests / test_psspps_pipeline.py

#source #python

> path: tests/test_psspps_pipeline.py  
> ext: .py  

---

# tests / test_psspps_pipeline.py


Tests for psspps/pipeline.py — run_psspps full pipeline, and for
psspps/scorer.py — coherence scoring functions.

Uses a zero activation vector (neutral harmonic state) so pipeline results
depend only on coherence structural-order, which is deterministic given the vault.


Defines: TestRunPSPSPSReturnType, TestPreRouting, TestScoreRanges, TestTopK, TestPerspectiveAlpha, TestScoredDocFields, TestStructuralOrder, TestCoherenceScores, TestRunFind, TestAnaChiWeight, TestOnCache, test_returns_psspps_result, test_query_preserved, test_top_docs_list, test_top_docs_are_scored_docs, test_n_docs_searched_positive, test_perspective_alpha_stored, test_slash_command_skips_retrieval, test_empty_query_returns_result, test_meaningful_query_triggers_retrieval, setup_method, test_retrieval_confidence_in_range, test_rag_confidence_in_range, test_doc_scores_in_range, test_docs_sorted_descending, test_default_top_k_three, test_custom_top_k, test_top_k_zero_returns_empty, test_alpha_zero_pure_semantic, test_alpha_one_pure_perspective, test_nonzero_activations_affect_perspective, test_scored_doc_has_path, test_scored_doc_snippet_is_string, test_scored_doc_has_coherence_score, test_one_hot_is_max_order, test_uniform_is_zero_order, test_order_in_unit_range, test_more_concentrated_is_higher_order, _uniform_affinity, _one_hot

---

## Semantic links

→ [[psspps-pipeline]]
→ [[psspps-router]]
→ [[psspps-find]]
→ [[psspps-init]]
→ [[engine-coherence-daemon]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-psspps-pipeline-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-gate-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-traverser-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-oesophagus-py]]
→ [[cursor-ingest/2026-08-04-072347-workers-cairrn-layers-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
