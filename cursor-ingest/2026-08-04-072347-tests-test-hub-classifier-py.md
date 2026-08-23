# tests / test_hub_classifier.py

#source #python

> path: tests/test_hub_classifier.py  
> ext: .py  

---

# tests / test_hub_classifier.py


Tests for graph/hub_classifier.py

Covers:
  - Strong single-hub signals route correctly
  - Link-signal bonus tips ambiguous cases
  - Empty / whitespace content falls back to HOME
  - hub_scores() returns expected relative ordering
  - Tiebreaker: CODE beats MATH on identical raw scores


Defines: _classify, TestKeywordSignal, TestLinkSignal, TestHubScores, TestTiebreaker, test_math_attractor_content, test_math_harmonic_shard_content, test_code_psspps_content, test_code_ingestion_content, test_commands_slash_content, test_agent_context_workflow_mode, test_empty_content_falls_back_to_home, test_whitespace_only_falls_back_to_home, test_math_links_tip_ambiguous_content, test_code_links_tip_ambiguous_content, test_links_reinforce_keyword_signal, test_empty_links_list_treated_same_as_none, test_math_content_has_highest_math_score, test_code_content_has_highest_code_score, test_all_hubs_present_in_scores, test_scores_are_non_negative, test_code_beats_math_on_zero_scores, test_classify_is_deterministic

---

## Semantic links

→ [[graph-hub-classifier]]
→ [[hub-classifier]]
→ [[topo-hub]]
→ [[logger]]
→ [[scratch]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-graph-hub-classifier-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-topo-graph-py]]
→ [[cursor-ingest/2026-08-04-072347-source-graph-hub-classifier-md]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-bridge-factory-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-temporal-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
