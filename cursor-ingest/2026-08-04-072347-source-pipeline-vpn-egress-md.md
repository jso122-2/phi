# source / pipeline-vpn-egress.md

#doc #md

> path: source/pipeline-vpn-egress.md  
> ext: .md  

---

# pipeline/vpn/egress

#code #module #pipeline #code

> source_path: pipeline/vpn/egress.py  
> package: pipeline  
> module: pipeline/vpn/egress  
> hub: CODE  
> created_ts:   

---

**Package:** `pipeline`  
**Module:** `pipeline/vpn/egress`  
**Source:** `pipeline/vpn/egress.py`

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
    result = verify_egress(proxy="socks5://127.0.0.1:1080", timeout=10.0)
    if not result.consensus_ok:
        raise RuntimeError(f"Egress leak: {result}")

## API

- `class EgressResult` — Result of a multi-endpoint egress verification.
- `def _fetch_ip` — Fetch the public IP from one endpoint.
- `def verify_egress` — Query all endpoints in parallel and return a consensus egress result.

---

## Semantic links

→ [[2026-07-16-liked-songs-mullvad-multi-source-pipeline]]
→ [[2025-09-09-102444-2025-09-09t20-25-19-520-10-00]]
→ [[queue]]
→ [[2026-07-16-011935-cairrn-cairrn-worker-system]]
→ [[2025-06-08-062508-2025-06-08t16-25-08-874-10-00]]

## Related notes

→ [[source/pipeline-vpn-mullvad]]
→ [[source/pipeline-vpn-init]]
→ [[source/pipeline-vpn-relay-pool]]
→ [[source/pipeline-vpn-manager]]
→ [[source/pipeline-auth]]

— import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[pipeline-vpn-init]]
→ [[pipeline-vpn-manager]]
→ [[pipeline-index]]
→ [[pipeline-vpn-relay-pool]]
→ [[pipeline-vpn-mullvad]]
→ [[pipeline-worker-init]]

---

## Semantic links

→ [[pipeline-vpn-egress]]
→ [[pipeline-vpn-init]]
→ [[pipeline-vpn-manager]]
→ [[scripts-run]]
→ [[pipeline-utils-config]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-pipeline-vpn-init-md]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-vpn-manager-md]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-vpn-mullvad-md]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-vpn-relay-pool-md]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-utils-config-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
