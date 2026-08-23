# tests / test_leaf_falls_no_double_route.py

#source #python

> path: tests/test_leaf_falls_no_double_route.py  
> ext: .py  

---

# tests / test_leaf_falls_no_double_route.py

Regression: leaf_falls must not DOUBLE_ROUTE TRACK_TRANSITION with arrival.

Departure (leaf_falls) records the leaf + skip-pressure ML_INFERENCE only.
Arrival (_apply_track_to_ui) owns the single TRACK_TRANSITION route.


Defines: TestLeafFallsNoDoubleRoute, test_leaf_falls_routes_ml_inference_not_track_transition, test_departure_then_arrival_no_double_route

---

## Semantic links

→ [[psspps-router]]
→ [[workers-cairrn-formulas]]
→ [[engine-coherence-gate]]
→ [[models-regression]]
→ [[scripts-train-d4]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-psspps-router-md]]
→ [[cursor-ingest/2026-08-04-072347-source-models-regression-md]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-query-router-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-octopus-head-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-bridge-factory-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
