# workers / cerberus.py

#source #python

> path: workers/cerberus.py  
> ext: .py  

---

# workers / cerberus.py


Cerberus bind — mathematical worker-respawn guard.

Three-headed gate: first bind detects deviation, second bind escalates
factorially with each retry, third head kills and respawns.

Mathematics
-----------
First bind (linear deviation):

    ceb_1 = | x - z/A - C - 1 |

    x  : observed worker metric (a float in any range)
    z  : normalisation constant  (default 0.0)
    A  : amplitude / scale factor (default 1.0, must be non-zero)
    C  : offset constant          (default 0.0)

    When z=0, A=1, C=0 this collapses to |x - 1|, i.e. the L1 distance
    from 1.0 — the "perfect worker" ta

Defines: ceb_1, ceb_2, BindResult, evaluate, CerberusGuard, CerberusExhausted, __str__, __post_init__, __call__, bind_log, retry_count

---

## Semantic links

→ [[workers-cerberus]]
→ [[workers-cairrn-worker]]
→ [[workers-cairrn-constants]]
→ [[workers-cairrn-layers]]
→ [[engine-gate]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-workers-cerberus-md]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-cerberus-py]]
→ [[cursor-ingest/2026-08-04-072347-workers-cairrn-worker-py]]
→ [[cursor-ingest/2026-08-04-072347-engine-cairrn-scheduler-py]]
→ [[cursor-ingest/2026-08-04-072347-engine-gate-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
