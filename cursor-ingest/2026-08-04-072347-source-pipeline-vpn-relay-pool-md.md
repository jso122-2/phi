# source / pipeline-vpn-relay-pool.md

#doc #md

> path: source/pipeline-vpn-relay-pool.md  
> ext: .md  

---

# pipeline/vpn/relay_pool

#code #module #pipeline #code

> source_path: pipeline/vpn/relay_pool.py  
> package: pipeline  
> module: pipeline/vpn/relay_pool  
> hub: CODE  
> created_ts:   

---

**Package:** `pipeline`  
**Module:** `pipeline/vpn/relay_pool`  
**Source:** `pipeline/vpn/relay_pool.py`

pipeline.vpn.relay_pool — EU relay pool for defensive VPN rotation.

Maintains a weighted pool of Mullvad relay hostnames across SE/NL/DE.
Random selection excludes the last N used relays (configurable) to
prevent back-to-back repeats.

The default pool is hard-coded from the Mullvad WireGuard relay list (2024).
Call `pool.refresh()` to repopulate live from `mullvad relay list` output.

## API

- `class RelayPool` — Rotating pool of EU Mullvad relay hostnames.

---

## Semantic links

→ [[2025-09-09-102444-2025-09-09t20-25-19-520-10-00]]
→ [[2025-05-11-042356-conda-commands]]
→ [[2025-11-15-163002-2025-11-16t03-30-02-589-11-00]]
→ [[2025-05-19-073525-butler-logs]]
→ [[2026-07-17T01-33-09Z-CLAPProjection and PhiGraph — DAWN bridge layer]]

## Related notes

→ [[source/pipeline-vpn-init]]
→ [[source/pipeline-vpn-manager]]
→ [[source/pipeline-vpn-mullvad]]
→ [[source/pipeline-vpn-egress]]
→ [[source/pipeline-auth]]

— import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[pipeline-vpn-init]]
→ [[pipeline-vpn-manager]]
→ [[pipeline-index]]
→ [[pipeline-vpn-mullvad]]
→ [[pipeline-vpn-egress]]
→ [[pipeline-auth]]

---

## Semantic links

→ [[pipeline-vpn-init]]
→ [[pipeline-vpn-manager]]
→ [[pipeline-vpn-relay-pool]]
→ [[scripts-run]]
→ [[pipeline-vpn-mullvad]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-pipeline-vpn-init-md]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-vpn-init-py]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-vpn-manager-md]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-vpn-egress-md]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-vpn-mullvad-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
