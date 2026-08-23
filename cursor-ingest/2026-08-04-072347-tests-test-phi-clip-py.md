# tests / test_phi_clip.py

#source #python

> path: tests/test_phi_clip.py  
> ext: .py  

---

# tests / test_phi_clip.py


tests/test_phi_clip_tool.py

Direct-import tests for the gemini_clip MCP tool.

Strategy: monkeypatch mcp_server.tools.phi_clip._get_session so that tests
never touch the real library on disk.  The gate is bypassed by calling the
inner function directly (the @requires_init decorator returns early when the
gate is closed, so we open it before the tests that need it).


Defines: _make_track, _make_synthetic_session, TestGeminiClipLibraryUnavailable, TestGeminiClipWithSession, TestIsWarmed, test_library_available_false, test_empty_tracks, test_query_echoed, test_n_tracks_searched_zero, test_blend_in_result, _patch_session, test_library_available_true, test_query_echoed, test_blend_stored, test_tracks_length_respects_top_k, test_tracks_length_default_top_k, test_track_keys_present, test_track_name_and_artist_are_strings, test_track_tags_is_list, test_p_sps_in_range, test_ranks_are_zero_based_sequential, test_context_string_non_empty, test_n_tracks_searched_matches_library, test_blend_zero_allowed, test_blend_one_allowed, test_false_when_session_none, test_true_when_session_set

---

## Semantic links

→ [[mcp-server-tools-phi-clip]]
→ [[mcp-server-tools-phi-dispatch]]
→ [[engine-phi-session]]
→ [[mcp-server-tools-init]]
→ [[mcp-server-tools-modular]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-tests-test-phi-clip-tool-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-phi-session-clip-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-gemini-clipper-py]]
→ [[cursor-ingest/2026-08-04-072347-mcp-server-tools-phi-clip-py]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-phi-clip-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
