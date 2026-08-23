# tests / test_phi_graph.py

#source #python

> path: tests/test_phi_graph.py  
> ext: .py  

---

# tests / test_phi_graph.py


Tests for phi — library, CLAPProjection, MetadataEncoder, PhiGraph.

These tests use synthetic Track objects — no disk I/O, no actual .mp3 files.
The live library path is only exercised in the integration tests at the bottom
(marked with `@pytest.mark.integration`), which require the real library to exist.


Defines: make_track, make_library, make_phi_graph, TestTrack, TestPhiLibrary, TestCLAPProjection, TestMetadataEncoder, TestEmbedTracks, TestTagAdjacency, TestPhiGraphSnapshot, TestPhiGraph, TestPhiGraphRealLibrary, test_display_name_both, test_display_name_fallback_to_stem, test_all_tags_deduplicated, test_all_tags_combines_sources, test_hash_and_equality, test_inequality_different_path, test_equality_type_check, test_len, test_getitem, test_by_artist, test_by_tag, test_tag_vocabulary_ordering, test_tag_vocabulary_top_k_cap, test_repr, test_output_shape, test_l2_normalised, test_single_row, test_zero_input_does_not_nan, test_n_params, test_different_seeds_different_weights, test_same_seed_same_weights, _enc, test_output_shape, test_key_one_hot_C, test_key_one_hot_sharp, test_key_unknown_leaves_zeros, test_key_confidence_clamped, test_duration_nonzero

---

## Semantic links

→ [[scripts-embed-tracks]]
→ [[pipeline-sources-soundcloud]]
→ [[engine-phi-session]]
→ [[scripts-rescrape-short]]
→ [[graph-node]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-tests-test-phi-session-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-phi-player-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-gemini-clipper-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-psp-index-py]]
→ [[cursor-ingest/2026-08-04-072347-scripts-embed-tracks-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
