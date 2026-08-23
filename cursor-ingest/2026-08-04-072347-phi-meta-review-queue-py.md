# phi / meta / review_queue.py

#source #python

> path: phi/meta/review_queue.py  
> ext: .py  

---

# phi / meta / review_queue.py

phi.meta.review_queue — thread-safe queue for low-confidence enrichment matches.

Items that scored below the auto-accept threshold are placed here for the
user to review.  The EnrichPanel polls pending_count() and renders items
for Accept / Reject / Edit actions.


Defines: ReviewStatus, ReviewItem, ReviewQueue, display_label, __init__, push, pending_items, all_items, pending_count, resolve, remove, clear_resolved

---

## Semantic links

→ [[engine-cairrn-scheduler]]
→ [[engine-cairrn-dispatch]]
→ [[engine-prefeed-shuffle]]
→ [[engine-coherence-gate]]
→ [[mcp-server-tools-prefeed-shuffle]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-ui-app-queue-ops-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-watch-enrich-daemon-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-meta-enricher-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-core-rank-scoring-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-meta-consensus-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
