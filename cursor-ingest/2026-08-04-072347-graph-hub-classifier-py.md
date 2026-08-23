# graph / hub_classifier.py

#source #python

> path: graph/hub_classifier.py  
> ext: .py  

---

# graph / hub_classifier.py


Hub classifier — maps session content to a station hub for harmonic injection.

Two independent signals are combined:

  1. Keyword signal — weighted keyword hits across the concatenated session
     text (prompt + thinking + outcome).  Each hub has its own vocabulary.
     Raw hit count is normalised by vocabulary size so large sets don't
     dominate by surface area alone.

  2. Link signal — if a discovered_link stem is a known member of a hub's
     node set, that hub receives a flat bonus per matching link.  This lets
     the PSSPPS-discovered graph topology vote on hub assignment.

Th

Defines: classify_hub, hub_scores, hub_ana_chi_weight, classify_hub_full

---

## Semantic links

→ [[graph-hub-classifier]]
→ [[PLAYBACK]]
→ [[HOME]]
→ [[HOME]]
→ [[hub-classifier]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-graph-hub-classifier-md]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-hub-classifier-py]]
→ [[cursor-ingest/2026-08-04-072347-graph-topo-graph-py]]
→ [[cursor-ingest/2026-08-04-072347-source-graph-linker-md]]
→ [[cursor-ingest/2026-08-04-072347-graph-init-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
