# tests / test_worker.py

#source #python

> path: tests/test_worker.py  
> ext: .py  

---

# tests / test_worker.py


Tests for graph/worker.py

Covers:
  - _resolve_link strips path prefix (regression for dead-link false-positive bug)
  - run_clean: path-prefixed links count as live, not dead
  - run_clean: only truly absent stems are reported as dead links
  - run_clean: orphan detection uses resolved stems
  - run_status: zero dead links for path-prefixed vault
  - run_nest: structural hubs are excluded from suggestions
  - run_nest: at least one semantic hub suggested when shared links exist


Defines: _Node, _vault, TestResolveLink, TestRunCleanDeadLinks, TestRunCleanOrphans, TestRunStatus, TestRunNest, _idx, test_bare_stem_unchanged, test_single_prefix_stripped, test_deep_prefix_stripped, test_empty_string, test_unknown_link_returns_none, test_bare_stem_link_is_live, test_path_prefixed_link_is_live, test_absent_target_is_dead, test_deep_path_prefix_is_live, test_mixed_live_and_dead, test_linked_node_not_orphan, test_path_prefixed_link_counts_as_incoming, test_hub_never_orphan, test_session_never_orphan, test_zero_dead_links_for_path_prefixed_vault, test_counts_nodes_correctly, test_hub_count, test_session_count, test_most_linked_ordered, test_orphan_count_with_path_prefix, test_structural_hubs_excluded_from_suggestions, test_semantic_hub_suggested_when_links_shared, test_no_suggestions_when_no_semantic_hubs, test_hub_itself_not_in_suggestions

---

## Semantic links

→ [[graph-worker]]
→ [[tools-fix-dead-links]]
→ [[graph-init]]
→ [[2026-07-13-configure-the-obsidian-graph-as-the-hub-buil]]
→ [[graph-linker]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-graph-worker-py]]
→ [[cursor-ingest/2026-08-04-072347-source-graph-worker-md]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-topo-graph-py]]
→ [[cursor-ingest/2026-08-04-072347-graph-md]]
→ [[cursor-ingest/2026-08-04-072347-graph-init-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
