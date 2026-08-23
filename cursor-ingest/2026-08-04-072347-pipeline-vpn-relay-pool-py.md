# pipeline / vpn / relay_pool.py

#source #python

> path: pipeline/vpn/relay_pool.py  
> ext: .py  

---

# pipeline / vpn / relay_pool.py


pipeline.vpn.relay_pool — EU relay pool for defensive VPN rotation.

Maintains a weighted pool of Mullvad relay hostnames across SE/NL/DE.
Random selection excludes the last N used relays (configurable) to
prevent back-to-back repeats.

The default pool is hard-coded from the Mullvad WireGuard relay list (2024).
Call `pool.refresh()` to repopulate live from `mullvad relay list` output.


Defines: RelayPool, __post_init__, pick, country_code, city_code, refresh, size, last_used, history

---

## Semantic links

→ [[pipeline-vpn-relay-pool]]
→ [[pipeline-vpn-init]]
→ [[pipeline-vpn-mullvad]]
→ [[pipeline-vpn-manager]]
→ [[pipeline-vpn-egress]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-pipeline-vpn-init-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-vpn-manager-py]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-vpn-mullvad-md]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-vpn-relay-pool-md]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-vpn-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
