# tests / test_psp_index.py

#source #python

> path: tests/test_psp_index.py  
> ext: .py  

---

# tests / test_psp_index.py


Tests for PspIndex — phi/models/psp_index.py.

Uses tmp_path for the SQLite db and synthetic Track objects.
Real files are created in tmp_path only where mtime invalidation is tested.


Defines: make_track, make_index, TestBuildCount, TestMtimeInvalidation, TestTfIdfMatrix, TestTrackPaths, TestVocabulary, TestClose, TestPersistence, test_first_build_returns_n, test_empty_tracks_returns_zero, test_single_track, test_rebuild_skips_unchanged, test_rebuild_updates_changed_file, test_rebuild_updates_all_new_tracks, test_rebuild_after_adding_track, test_shape_matches_track_count, test_vocab_size_matches_columns, test_empty_index_returns_zero_shape, test_matrix_dtype_is_float64, test_values_in_unit_range, test_length_matches_track_count, test_paths_are_strings, test_empty_index_returns_empty_list, test_track_paths_and_matrix_row_order_consistent, test_returns_non_empty_after_build, test_returns_list_of_strings, test_empty_index_returns_empty_list, test_known_terms_present, test_close_does_not_crash, test_close_twice_does_not_crash, test_close_on_empty_index, test_data_survives_reopen

---

## Semantic links

→ [[psspps-pipeline]]
→ [[indexer]]
→ [[pipeline-fetcher-models]]
→ [[pipeline-fetcher-init]]
→ [[psspps-init]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-models-psp-index-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-phi-graph-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-traverser-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-query-router-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-oesophagus-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
