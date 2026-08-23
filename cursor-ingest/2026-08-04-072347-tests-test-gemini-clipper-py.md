# tests / test_gemini_clipper.py

#source #python

> path: tests/test_gemini_clipper.py  
> ext: .py  

---

# tests / test_gemini_clipper.py


Tests for GeminiClipper — phi/models/gemini_clipper.py.

Uses synthetic Track + PhiGraphSnapshot (no disk I/O, no real library).


Defines: make_track, make_snap, make_clipper, TestTrackText, TestQueryHVec, TestGeminiClipper, test_includes_name_and_artist, test_includes_tags, test_empty_track_no_crash, test_output_shape, test_l2_normalised, test_empty_query_no_crash, _run, test_returns_clip_result, test_top_k_length, test_top_k_capped_to_n, test_ranks_are_sequential, test_p_sps_descending, test_scores_in_unit_range, test_context_contains_query, test_context_contains_track_names, test_n_tracks_searched, test_alpha_stored, test_pure_semantic_alpha_zero, test_pure_hspace_alpha_one, test_empty_snap_returns_no_tracks, test_single_track_snap, test_repr, test_context_block_format

---

## Semantic links

→ [[mcp-server-tools-phi-clip]]
→ [[engine-phi-session]]
→ [[scripts-train-d4]]
→ [[scripts-embed-tracks]]
→ [[2025-12-06-114407-gemini-clipper]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-tests-test-phi-session-clip-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-phi-clip-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-phi-clip-tool-py]]
→ [[cursor-ingest/2026-08-04-072347-mcp-server-tools-phi-clip-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-models-gemini-clipper-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
