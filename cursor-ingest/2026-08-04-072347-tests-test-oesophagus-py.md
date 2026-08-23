# tests / test_oesophagus.py

#source #python

> path: tests/test_oesophagus.py  
> ext: .py  

---

# tests / test_oesophagus.py


Tests for workers.sentinel and workers.oesophagus.

All tests are filesystem-isolated using tmp_path (pytest fixture).
No vault writes touch the real Obsidian vault during testing.


Defines: TestSentinelExtensionBlock, TestSentinelPathQuarantine, TestSentinelContentRedaction, TestClassify, TestScanDirectory, TestIngest, TestWriteVaultNode, test_pem_blocked, test_env_blocked, test_txt_allowed, test_md_allowed_by_extension, test_ssh_dir_blocked, test_secrets_dir_blocked, test_api_key_redacted, test_private_key_pem_in_content_redacted, test_clean_file_not_redacted, test_screen_with_text_argument, test_screen_batch, test_kinds, test_finds_txt, test_skips_md, test_recurse_finds_nested, test_no_recurse_skips_nested, test_max_files_cap, _source, _vault, test_basic_txt_ingestion, test_sensitive_file_blocked, test_redacted_file_still_ingested, test_empty_source_dir, test_mixed_content, test_result_summary_keys, test_elapsed_recorded, _make_item, test_writes_md_file, test_written_content_contains_title, test_written_under_ingest_subdir

---

## Semantic links

→ [[workers-oesophagus]]
→ [[workers-sentinel]]
→ [[README]]
→ [[engine-vault-writer]]
→ [[mcp-server-vault-hub]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-workers-oesophagus-py]]
→ [[cursor-ingest/2026-08-04-072347-workers-sentinel-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-vault-garden-py]]
→ [[cursor-ingest/2026-08-04-072347-source-workers-oesophagus-md]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-vault-writer-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
