# tests / test_traverser.py

#source #python

> path: tests/test_traverser.py  
> ext: .py  

---

# tests / test_traverser.py


Tests for psspps.traverser (minecart graph traversal).

All tests are fastembed-free: they supply pre-built numpy arrays
and synthetic VaultDoc dicts, so they run offline with zero model
weights required.


Defines: _make_docs, _unit, _orthonormal, _stub_embed, _make_embed_fn, TestFindDocByTitle, TestTraversalResultToDict, TestTraverse, test_exact_match, test_case_insensitive, test_missing, test_empty_result, test_hop_fields, test_returns_traversal_result, test_visits_at_most_max_hops, test_seed_title_boards_first, test_no_revisit, test_budget_limits_traversal, test_stopped_reason_set, test_path_matches_hops, test_similarity_in_range, test_sim_floor_respected, test_empty_docs_handled

---

## Semantic links

→ [[psspps-traverser]]
→ [[psspps-init]]
→ [[psspps-pipeline]]
→ [[psspps-retriever]]
→ [[graph-linker]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-psspps-traverser-md]]
→ [[cursor-ingest/2026-08-04-072347-psspps-traverser-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-psp-index-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-psspps-pipeline-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-query-router-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
