# phi / models / query_router.py

#source #python

> path: phi/models/query_router.py  
> ext: .py  

---

# phi / models / query_router.py


Stage II Query Router for the Gemini Clipper architecture.

Lightweight TF-IDF centroid classifier that intercepts a query and decides
whether to route to semantic search (SEARCH) or bypass entirely (PASSTHROUGH).

Outputs:
    cluster_id  — which semantic partition to search (0-based)
    action      — RouteAction.SEARCH or RouteAction.PASSTHROUGH


Defines: RouteAction, RouteDecision, QueryRouter, __init__, fit, route, is_fitted, __repr__

---

## Semantic links

→ [[2025-12-06-114407-gemini-clipper]]
→ [[engine-phi-session]]
→ [[psspps-pipeline]]
→ [[psspps-router]]
→ [[scripts-inference]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-models-gemini-clipper-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-models-init-py]]
→ [[cursor-ingest/2026-08-04-072347-psspps-pipeline-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-query-router-py]]
→ [[cursor-ingest/2026-08-04-072347-psspps-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
