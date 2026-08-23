# phi / engine / arc_scorer.py

#source #python

> path: phi/engine/arc_scorer.py  
> ext: .py  

---

# phi / engine / arc_scorer.py

phi.engine.arc_scorer — rolling D4_A buffer for smooth arc-transition scoring.

Maintains a circular buffer of recent D4_A values from playback history and
exposes ``score_candidate(d4_a)`` to rate how well a candidate track continues
the current arc.

Scoring model
-------------
    level  = mean(buffer)          — where the arc currently sits
    slope  = linregress(last 8)    — building vs. releasing energy?
    target = level + slope         — next expected value on the arc

    score(d4_a) = 1 / (1 + |d4_a − target| * scale)
                = 1.0  → perfect continuation (delta = 0)
      

Defines: ArcScorer, __init__, push, level, slope, score_candidate, __len__, __repr__

---

## Semantic links

→ [[2025-11-15-163223-2025-11-16t03-32-26-033-11-00]]
→ [[psspps-scorer]]
→ [[engine-phi-player]]
→ [[PLAYBACK]]
→ [[psspps]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-engine-arc-engine-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-engine-curve-daemon-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-models-song-derivative-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-core-ranker-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-graph-phi-orchestrator-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
