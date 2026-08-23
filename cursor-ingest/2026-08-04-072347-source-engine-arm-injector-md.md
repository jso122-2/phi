# source / engine-arm-injector.md

#doc #md

> path: source/engine-arm-injector.md  
> ext: .md  

---

# engine/arm_injector

#code #module #engine #code

> source_path: engine/arm_injector.py  
> package: engine  
> module: engine/arm_injector  
> hub: CODE  
> created_ts:   

---

**Package:** `engine`  
**Module:** `engine/arm_injector`  
**Source:** `engine/arm_injector.py`

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
    cluster_a_note   Title of the top note in cluster A (becomes a wikilink)
    cluster_b_note   Title of the top note in cluster B (becomes a wikilink)
    body             Short connecting sentence, constructed without an LLM
    inter_link_count Number of existing explicit links between the two clusters

## API

- `class BridgeSpec`
- `class BridgeFactory` — Scans for isolated cluster pairs and produces bridge note specs.

---

## Semantic links

→ [[hub-classifier]]
→ [[2026-07-13-configure-the-obsidian-graph-as-the-hub-buil]]
→ [[2026-07-16-011935-vault-coherence-engine]]
→ [[graph]]
→ [[graph]]

## Related notes

→ [[source/engine-vault-writer]]
→ [[source/engine-bridge-factory]]
→ [[source/engine-orphan-detector]]
→ [[source/engine-coherence-daemon]]
→ [[source/pipeline-bridge-init]]

— import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[engine-orphan-detector]]
→ [[engine-index]]
→ [[engine-main]]
→ [[index]]
→ [[engine-coherence-daemon]]
→ [[engine-health-log]]

---

## Semantic links

→ [[engine-arm-injector]]
→ [[engine-bridge-factory]]
→ [[engine-init]]
→ [[pipeline-bridge-init]]
→ [[engine-index]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-engine-arm-injector-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-bridge-factory-py]]
→ [[cursor-ingest/2026-08-04-072347-source-engine-bridge-factory-md]]
→ [[cursor-ingest/2026-08-04-072347-source-engine-index-md]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-bridge-init-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
