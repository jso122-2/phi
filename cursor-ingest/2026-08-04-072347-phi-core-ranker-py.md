# phi / core / ranker.py

#source #python

> path: phi/core/ranker.py  
> ext: .py  

---

# phi / core / ranker.py

phi.core.ranker — context-aware track ranking and ELO pairwise scoring.

CAIRRN integration
──────────────────
When ForestFloor is wired via ``bind_floor()``, two hotspots are eliminated:

1. RankContext.from_library() — O(n log n) play_stats sort on every call.
   The module caches the result until the CODE hub step count advances
   (i.e. until a new track is played), then rebuilds exactly once.

2. candidates() rank cache — scoring n tracks × 512-d cosine per transition.
   The module caches the ranked list keyed by (current_path, library_size).
   Invalidated when CODE becomes incoherent (

Defines: TrackRanker, candidates, score, elo_update, implicit_elo_update, compute_scup, _mean_elo, top_by_score

---

## Semantic links

→ [[engine-phi-player]]
→ [[engine-cairrn-dispatch]]
→ [[engine-cairrn-scheduler]]
→ [[source]]
→ [[workers-cairrn-z-space]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-core-rank-context-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-app-track-ui-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-engine-cairrn-types-py]]
→ [[cursor-ingest/2026-08-04-072347-engine-phi-player-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-engine-init-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
