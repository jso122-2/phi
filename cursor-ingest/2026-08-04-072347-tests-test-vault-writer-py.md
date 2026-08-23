# tests / test_vault_writer.py

#source #python

> path: tests/test_vault_writer.py  
> ext: .py  

---

# tests / test_vault_writer.py


Tests for engine.vault_writer.SambaWriter.

Coverage:
  - Coherence gate: < W(1) ≈ 0.5671 → dry-run (no files written)
  - Coherence gate: ≥ W(1) ≈ 0.5671 → live writes
  - SPROUT arm triggers new .md node
  - Arms below threshold are skipped
  - SambaResult.summary() has required keys
  - sessions/samba/ directory created automatically
  - Multiple arms → multiple writes on one tick
  - Written file content includes arm name and score
  - Dry-run content rendered even when not written
  - SambaWrite.path is None when dry-run
  - make_samba_writer factory works
  - TracerDaemon with vault_roo

Defines: all_arms, make_writer, TestCoherenceGate, TestArmThreshold, TestFileContent, TestSambaResult, TestSambaDirCreated, TestFactory, TestTracerDaemonVaultIntegration, test_below_threshold_is_dry_run, test_above_threshold_writes_files, test_exactly_at_threshold_writes, test_dry_run_path_is_none, test_live_write_path_exists, test_zero_score_skipped, test_above_threshold_included, test_all_below_threshold_no_writes, test_sprout_node_contains_arm_name, test_file_includes_score, test_dry_run_content_rendered, test_file_under_samba_subdir, test_file_suffix_is_md, test_summary_has_required_keys, test_multiple_arms_multiple_writes, test_tick_increments, test_samba_dir_auto_created, test_make_samba_writer_returns_writer, test_daemon_with_vault_root_writes_samba_nodes, ring_A

---

## Semantic links

→ [[engine-vault-writer]]
→ [[scripts-mcp-bridge]]
→ [[engine-coherence-daemon]]
→ [[engine-gate]]
→ [[engine-arm-injector]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-engine-vault-writer-md]]
→ [[cursor-ingest/2026-08-04-072347-engine-vault-writer-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-oesophagus-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-vault-garden-py]]
→ [[cursor-ingest/2026-08-04-072347-engine-coherence-daemon-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
