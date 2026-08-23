# tests / test_phi_session_clip.py

#source #python

> path: tests/test_phi_session_clip.py  
> ext: .py  

---

# tests / test_phi_session_clip.py


Tests for PhiTracerSession.clip() — GeminiClipper integration.

All tests use synthetic data: no disk I/O, no real library.


Defines: make_clip_session, built_session, TestClipBeforeBuild, TestClipAfterBuild, TestLazyClipper, TestReprClipperField, test_raises_runtime_error_before_build, test_clipper_is_none_before_first_clip, test_returns_clip_result, test_clip_result_query_matches_input, test_n_tracks_searched_matches_track_count, test_top_k_length_equals_requested_k, test_top_k_capped_when_k_exceeds_n, test_default_top_k_is_five, test_clipper_none_before_first_clip, test_clipper_created_after_first_clip, test_same_clipper_reused_for_same_params, test_different_alpha_creates_new_clipper, test_different_top_k_creates_new_clipper, test_clipper_carries_correct_alpha, test_clipper_carries_correct_top_k, test_repr_contains_clipper_field, test_repr_clipper_none_before_clip, test_repr_clipper_ready_after_clip

---

## Semantic links

→ [[mcp-server-tools-phi-clip]]
→ [[engine-phi-session]]
→ [[2025-12-06-114407-gemini-clipper]]
→ [[scripts-train-d4]]
→ [[engine-hot-loader]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-tests-test-gemini-clipper-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-phi-clip-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-phi-clip-tool-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-phi-session-py]]
→ [[cursor-ingest/2026-08-04-072347-mcp-server-tools-phi-clip-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
