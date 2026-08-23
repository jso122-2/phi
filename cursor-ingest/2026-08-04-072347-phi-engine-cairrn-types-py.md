# phi / engine / cairrn / types.py

#source #python

> path: phi/engine/cairrn/types.py  
> ext: .py  

---

# phi / engine / cairrn / types.py

phi.engine.cairrn.types — Leaf, Tree, and RiderState value types for the ForestFloor.

Pure data structures with no I/O or network dependencies.  Separated from
floor.py so other modules can import the types without pulling in the full
CAIRRN substrate or its persistence layer.

    Leaf        — one track event (a song that fell from the canopy)
    Tree        — one UI page    (a standing tree rooted in a CAIRRN hub)
    RiderState  — the user's active position and velocity in the forest


Defines: Leaf, Tree, RiderState, skip_pressure, nesting_depth, __str__, from_page, catch, leaf_count, mean_completion, total_skip_pressure, __str__, record, decay, is_active, restless, __str__

---

## Semantic links

→ [[engine-vault-garden]]
→ [[cairrn]]
→ [[source]]
→ [[engine-cairrn-dispatch]]
→ [[engine-mycelial]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-engine-cairrn-floor-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-engine-init-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-app-track-ui-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-engine-forest-types-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-core-ranker-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
