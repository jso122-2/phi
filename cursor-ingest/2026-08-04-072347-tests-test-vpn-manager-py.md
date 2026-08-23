# tests / test_vpn_manager.py

#source #python

> path: tests/test_vpn_manager.py  
> ext: .py  

---

# tests / test_vpn_manager.py


Tests for the defensive VPN layer:
    pipeline.vpn.relay_pool  — RelayPool selection and refresh
    pipeline.vpn.egress      — EgressResult, verify_egress consensus
    pipeline.vpn.manager     — VPNManager lifecycle and state machine

All tests are fully offline — Mullvad CLI and network calls are mocked.


Defines: TestRelayPool, _make_egress_ok, _make_egress_leaked, TestEgressResult, TestVerifyEgress, _mock_mullvad_connect, TestVPNManager, test_pick_returns_pool_member, test_pick_excludes_recent_history, test_fallback_to_full_pool_when_all_in_history, test_country_code, test_city_code, test_last_used_tracks_picks, test_history_property, test_refresh_updates_relays, test_refresh_falls_back_on_failure, test_str_ok, test_str_failed, test_to_dict_keys, _patch_fetch, test_consensus_ok_when_all_agree, test_consensus_ok_on_two_of_three, test_no_consensus_when_all_disagree, test_consensus_ok_when_one_endpoint_errors, test_fail_when_all_endpoints_error, _make_manager, test_connect_sets_connected_status, test_connect_picks_from_pool_when_no_relay_given, test_connect_raises_on_socks5_timeout, test_connect_raises_on_egress_leak, test_verify_updates_egress_state, test_verify_raises_on_leak, test_verify_noop_when_disconnected, test_rotate_changes_relay, test_disconnect_sets_disconnected, test_alert_ring_records_events, test_alert_ring_bounded_at_20, test_state_dict_is_serialisable, test_state_dict_status_is_string, _side_effect

---

## Semantic links

→ [[pipeline-vpn-init]]
→ [[pipeline-vpn-manager]]
→ [[pipeline-vpn-relay-pool]]
→ [[pipeline-vpn-egress]]
→ [[mcp-server-tools-vpn]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-tests-test-vpn-py]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-vpn-init-py]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-vpn-manager-py]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-vpn-relay-pool-py]]
→ [[cursor-ingest/2026-08-04-072347-mcp-server-tools-vpn-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
