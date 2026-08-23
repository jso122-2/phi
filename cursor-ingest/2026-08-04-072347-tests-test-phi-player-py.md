# tests / test_phi_player.py

#source #python

> path: tests/test_phi_player.py  
> ext: .py  

---

# tests / test_phi_player.py


Tests for engine/phi_player.py — PhiPlayer playback + CAIRRN feedback loop.

Synthetic subsystems — no disk I/O, no audio playback.


Defines: _make_tracks, _make_snap, _make_index, _make_dispatcher, _make_shuffle_mock, _make_player, TestConstruction, TestPlayNext, TestReportPlay, TestInjectionThresholds, TestHarmonicFeedback, TestFullLoop, TestState, _next, test_defaults, test_factory, test_returns_track, test_current_track_set_during_play, test_advances_cursor_each_call, test_calls_peek_and_preload_when_hot_loader_attached, test_no_peek_and_preload_without_hot_loader, test_raises_when_snapshot_none, test_returns_play_event, test_play_fraction_clamped, test_play_fraction_clamped_low, test_current_track_cleared_after_report, test_increments_total_plays, test_skip_counted_below_frac_heard, test_not_skip_at_frac_heard, test_raises_without_play_next, test_raises_if_called_twice, test_event_stored_in_history, test_loved_injects_both_hubs, test_loved_above_threshold, test_heard_only_home, test_heard_lower_bound, test_skipped_no_injection, test_just_below_heard_no_injection, test_loved_track_injects_home_and_code, test_heard_track_injects_only_home

---

## Semantic links

→ [[engine-phi-player]]
→ [[scripts-embed-tracks]]
→ [[engine-phi-session]]
→ [[engine-hot-loader]]
→ [[scripts-pretrain-loop]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-engine-phi-player-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-cairrn-scheduler-py]]
→ [[cursor-ingest/2026-08-04-072347-source-engine-phi-player-md]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-prefeed-shuffle-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-metadata-schema-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
