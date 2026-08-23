# tests / test_query_router.py

#source #python

> path: tests/test_query_router.py  
> ext: .py  

---

# tests / test_query_router.py


Tests for the Stage II QueryRouter — phi/models/query_router.py.

Synthetic corpus only; no real library or disk I/O.


Defines: fitted_router, TestIsFitted, TestRouteBeforeFit, TestPassthrough, TestSearch, TestEdgeCases, test_false_before_fit, test_true_after_fit, test_true_after_fit_empty_corpus, test_raises_runtime_error, test_empty_query, test_single_token_query, test_low_score_query_passthrough, test_passthrough_tokens_still_populated, test_passthrough_confidence_zero_empty, test_search_action, test_cluster_id_in_range, test_confidence_in_unit_range, test_query_tokens_populated, test_returns_route_decision, test_search_on_large_corpus, test_min_score_zero_forces_search_if_any_overlap, test_fewer_docs_than_clusters_no_crash, test_single_doc_corpus, test_empty_corpus_passthrough, test_repr_unfitted, test_repr_fitted, test_n_clusters_param, test_route_decision_dataclass_fields

---

## Semantic links

→ [[psspps-pipeline]]
→ [[engine-phi-session]]
→ [[scripts-train]]
→ [[engine-init]]
→ [[workers-cairrn-formulas]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-tests-test-cairrn-scheduler-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-phi-session-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-phi-graph-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-hot-loader-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-psp-index-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
