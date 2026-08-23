# tests / test_cursor_tracer.py

#source #python

> path: tests/test_cursor_tracer.py  
> ext: .py  

---

# tests / test_cursor_tracer.py


tests/test_cursor_tracer.py — unit tests for engine.cursor_tracer.

Coverage:
  - HoverRegion.contains() — boundary, inside, outside
  - CursorSample hovered_regions field — default empty list, as_dict omits key
    when empty, includes key when non-empty
  - CursorTracer.register_hover() — registers region, initialises counter to 0
  - CursorTracer._check_hover() — dwell accumulation, fires at threshold,
    does NOT fire before threshold, does NOT fire again on the next sample,
    resets counter after leaving region, can re-fire after re-entry
  - CursorTracer.attach_dispatcher() — swapped

Defines: TestHoverRegionContains, TestCursorSampleHoveredRegions, _FakeDispatcher, TestCursorTracerHover, TestCursorTracerSnapshot, _region, test_inside_centre, test_top_left_corner, test_bottom_right_corner, test_outside_left, test_outside_right, test_outside_top, test_outside_bottom, test_dwell_samples_default, _sample, test_default_empty, test_as_dict_omits_key_when_empty, test_as_dict_includes_key_when_non_empty, test_as_dict_multiple_regions, __init__, signal_hover, _tracer, test_register_initialises_counter_zero, test_no_signal_before_threshold, test_signal_fires_exactly_at_threshold, test_signal_does_not_re_fire_while_still_inside, test_counter_resets_on_leave, test_can_refire_after_reentry, test_multiple_regions_independent, test_no_dispatcher_no_exception, test_broken_dispatcher_does_not_crash, test_attach_dispatcher_replaces_previous, test_snapshot_hover_regions_empty, test_snapshot_hover_regions_populated, test_snapshot_counter_advances, BrokenDispatcher, signal_hover

---

## Semantic links

→ [[engine-cursor-tracer]]
→ [[tools-cursor-ingest]]
→ [[scripts-spawn-tracer]]
→ [[engine-tracer-daemon]]
→ [[2025-09-24-134225-2025-09-24t23-42-27-440-10-00]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-engine-cursor-tracer-md]]
→ [[cursor-ingest/2026-08-04-072347-engine-cursor-tracer-py]]
→ [[cursor-ingest/2026-08-04-072347-source-tools-cursor-ingest-md]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-tracer-daemon-py]]
→ [[cursor-ingest/2026-08-04-072347-tools-cursor-ingest-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
