# tests / test_vault_garden.py

#source #python

> path: tests/test_vault_garden.py  
> ext: .py  

---

# tests / test_vault_garden.py


Tests for engine/vault_garden.py

Covers:
  - build_adjacency: wikilinks produce correct symmetric matrix
  - build_adjacency: path-prefixed links are resolved
  - build_adjacency: self-loops are absent
  - project_embeddings: output shape and no-op when d_in == d_out
  - _node_text: title + truncated body
  - VaultGarden.run_cycle: runs end-to-end with stub vault (no fastembed)
  - VaultGarden.run_cycle: returns zero summary on empty vault
  - VaultGarden: tick advances after each cycle


Defines: _Node, TestBuildAdjacency, TestProjectEmbeddings, TestNodeText, TestVaultGardenRunCycle, stem, test_bare_link_produces_edge, test_path_prefixed_link_resolved, test_no_self_loop, test_missing_target_no_edge, test_shape, test_symmetric, test_output_shape, test_noop_when_same_dim, test_deterministic, test_different_seeds_differ, test_combines_title_and_body, test_truncates_long_text, _make_nodes, _fake_embed, test_returns_tracer_summary, test_tick_advances, test_empty_vault_returns_zero_summary, test_samba_dir_created

---

## Semantic links

→ [[engine-vault-garden]]
→ [[engine-vault-writer]]
→ [[graph-node]]
→ [[psspps-traverser]]
→ [[graph-worker]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-tests-test-oesophagus-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-worker-py]]
→ [[cursor-ingest/2026-08-04-072347-engine-vault-garden-py]]
→ [[cursor-ingest/2026-08-04-072347-graph-node-py]]
→ [[cursor-ingest/2026-08-04-072347-graph-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
