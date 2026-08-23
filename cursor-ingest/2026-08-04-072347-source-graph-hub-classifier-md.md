# source / graph-hub-classifier.md

#doc #md

> path: source/graph-hub-classifier.md  
> ext: .md  

---

# graph/hub_classifier

#code #module #graph #code

> source_path: graph/hub_classifier.py  
> package: graph  
> module: graph/hub_classifier  
> hub: CODE  
> created_ts:   

---

**Package:** `graph`  
**Module:** `graph/hub_classifier`  
**Source:** `graph/hub_classifier.py`

Hub classifier — maps session content to a station hub for harmonic injection.

Two independent signals are combined:

  1. Keyword signal — weighted keyword hits across the concatenated session
     text (prompt + thinking + outcome).  Each hub has its own vocabulary.
     Raw hit count is normalised by vocabulary size so large sets don't
     dominate by surface area alone.

  2. Link signal — if a discovered_link stem is a known member of a hub's
     node set, that hub receives a flat bonus per matching link.  This lets
     the PSSPPS-discovered graph topology vote on hub assignment.

The hub with the highest combined score wins.  CODE is the tiebreaker.

Station-hub → shard mapping (fixed at spawn, mirrors server.py):
    HOME          → shard 0          (basin 1.96)
    MATH          → shards 1, 2      (basins 3.92, 5.88)
    CODE          → shards 3, 4      (basins 7.84, 9.80)
    COMMANDS      → shard 5          (basin 11.76)
    agent-context → shards 6, 7      (basins 13.72, 15.68)

Station-hub → Ana-Chi basin mapping (𝒜_χ integration):
    HOME          → true_center  χ = 1.5414   (natural equilibrium)
    MATH          → white_peak   χ = 1.9600   (singularity = ALPHA)
    CODE          → mirror       χ = 0.9900   (stable, slow transitions)
    COMMANDS      → escape       χ = 2.6700   (rapid action)
    agent-context → boundary     χ = 0.0300   (interface layer)

## API

- `def classify_hub` — Return the station hub that best matches this session's content.
- `def hub_scores` — Return the raw score for every hub — useful for debugging and tests.
- `def hub_ana_chi_weight` — Return the Ana-Chi coherence weight for a hub.
- `def classify_hub_full` — Full classification result inc

---

## Semantic links

→ [[graph-hub-classifier]]
→ [[mcp-server-tools-harmonic]]
→ [[HOME]]
→ [[HOME]]
→ [[logger]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-graph-hub-classifier-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-hub-classifier-py]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-harmonic-md]]
→ [[cursor-ingest/2026-08-04-072347-source-graph-index-md]]
→ [[cursor-ingest/2026-08-04-072347-mcp-server-tools-harmonic-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
