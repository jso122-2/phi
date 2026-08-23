# tests / test_dom_queue.py

#source #python

> path: tests/test_dom_queue.py  
> ext: .py  

---

# tests / test_dom_queue.py


Tests for mcp_server/dom_queue.py

Covers:
  - House: ownership check, BMAD token determinism
  - DOMRequestQueue: register, open, gate (happy path + wrong house error)
  - spawn_houses(): all expected houses present + cairrn/forecast entries added
  - RaceWatchdog: starts as daemon, state() returns correct structure
  - Concurrency: sequential calls to same house are serialised (no deadlock)


Defines: _make_house, TestHouse, TestDOMRequestQueue, TestSpawnHouses, test_admits_registered_tool, test_does_not_admit_foreign_tool, test_call_count_starts_zero, test_active_starts_false, test_status_shape, _open_queue, test_gate_executes_correctly, test_gate_increments_call_count, test_gate_unknown_tool_raises, test_gate_not_open_raises, test_multiple_houses_independent, test_reentrant_gate_same_house, test_sequential_calls_same_house_no_deadlock, test_concurrent_calls_serialised, setup_method, test_returns_open_queue, test_all_expected_houses_present, test_cairrn_tools_in_modular, test_forecast_state_in_modular, test_each_tool_in_exactly_one_house, test_watchdog_is_daemon, test_watchdog_state_structure, worker

---

## Semantic links

→ [[mcp-server-dom-queue]]
→ [[2026-07-13-095004-cairrnify-the-mcp-server-fix-dom-queue-open]]
→ [[mcp-server-server]]
→ [[mcp-server-state]]
→ [[scripts-mcp-bridge]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-mcp-server-dom-queue-py]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-dom-queue-md]]
→ [[cursor-ingest/2026-08-04-072347-mcp-server-tools-system-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-cairrn-scheduler-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-vpn-manager-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
