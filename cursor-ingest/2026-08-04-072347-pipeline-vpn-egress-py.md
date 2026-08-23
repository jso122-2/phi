# pipeline / vpn / egress.py

#source #python

> path: pipeline/vpn/egress.py  
> ext: .py  

---

# pipeline / vpn / egress.py


pipeline.vpn.egress — multi-endpoint consensus egress IP verification.

Queries three independent endpoints in parallel, requires 2/3 majority
agreement on the returned public IP.  The Mullvad endpoint additionally
confirms the IP is a known Mullvad exit node via the `mullvad_exit_ip` flag.

Endpoints
---------
1. https://am.i.mullvad.net/json   — ASN, relay name, mullvad_exit_ip bool
2. https://icanhazip.com           — bare IP string, no JS, fastest
3. https://api.ipify.org?format=json — neutral JSON {"ip": "..."}

Usage
-----
    result = verify_egress(proxy="socks5://127.0.0.1:1080", time

Defines: EgressResult, _fetch_ip, verify_egress, __str__, to_dict

---

## Semantic links

→ [[pipeline-vpn-egress]]
→ [[pipeline-vpn-mullvad]]
→ [[pipeline-vpn-init]]
→ [[pipeline-vpn-relay-pool]]
→ [[pipeline-auth]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-pipeline-vpn-init-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-vpn-py]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-vpn-mullvad-py]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-vpn-mullvad-md]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-vpn-relay-pool-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
