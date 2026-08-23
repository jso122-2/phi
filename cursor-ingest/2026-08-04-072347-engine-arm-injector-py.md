# engine / arm_injector.py

#source #python

> path: engine/arm_injector.py  
> ext: .py  

---

# engine / arm_injector.py


BridgeFactory — detects isolated cluster pairs and generates bridge note specs.

Two clusters are "isolated" if there are fewer explicit inter-cluster wikilinks
than `min_bridges`. For each such pair, the factory proposes a bridge note that
can be written to the vault by VaultWriter.create_bridge_note().

Public API:
    BridgeFactory(orchestrator, min_bridges=1)
    .scan() -> List[BridgeSpec]

Each BridgeSpec contains:
    cluster_a_id     First cluster index
    cluster_b_id     Second cluster index
    title            Proposed title for the bridge note
    cluster_a_note   Title of the t

Defines: BridgeSpec, BridgeFactory, to_dict, __init__, scan, _wikilink_edge_set, _inter_cluster_links, _short

---

## Semantic links

→ [[engine-arm-injector]]
→ [[engine-bridge-factory]]
→ [[engine-orphan-detector]]
→ [[engine-vault-writer]]
→ [[scripts-mcp-bridge]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-engine-arm-injector-md]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-bridge-factory-py]]
→ [[cursor-ingest/2026-08-04-072347-engine-orphan-detector-py]]
→ [[cursor-ingest/2026-08-04-072347-source-engine-bridge-factory-md]]
→ [[cursor-ingest/2026-08-04-072347-engine-coherence-daemon-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
