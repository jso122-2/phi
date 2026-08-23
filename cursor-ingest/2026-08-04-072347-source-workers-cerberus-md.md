# source / workers-cerberus.md

#doc #md

> path: source/workers-cerberus.md  
> ext: .md  

---

# workers/cerberus

#code #module #workers #code

> source_path: workers/cerberus.py  
> package: workers  
> module: workers/cerberus  
> hub: CODE  
> created_ts:   

---

**Package:** `workers`  
**Module:** `workers/cerberus`  
**Source:** `workers/cerberus.py`

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
    from 1.0 — the "perfect worker" target.

Second bind (factorial escalation):

    ceb_2 = M! * ceb_1

    M  : retry index for this worker (0-indexed; M=0 means first attempt)

    The factorial makes repeated failures super-linearly expensive:
        M=0 → factor 1     (no escalation on first attempt)
        M=1 → factor 1     (1! = 1)
        M=2 → factor 2
        M=3 → factor 6
        M=4 → factor 24
        M=5 → factor 120   → a mid-range violation explodes past any threshold

Respawn logic:
    ceb_1 > tau_1  → soft violation  — log, increment retry counter, retry worker
    ceb_2 > tau_2  → hard violation  — kill worker, spawn fresh instance
    both within    → worker passes the Cerberus gate

## API

- `def ceb_1` — First Cerberus bind — linear deviation metric.
- `def ceb_2` — Second Cerberus bind — factorial escalation.
- `class BindResult` — Full audit record for one Cerberus evaluation.
- `def evaluate` — Evaluate both Cerberus binds for a worker metric `x` at retry `M`.
- `class CerberusGuard` — Wraps a factory function that produces a callable worker.
- `class CerberusExhausted` — Raised when a worker exceeds the maximum Cerberus r

---

## Semantic links

→ [[workers-cerberus]]
→ [[workers-cairrn-layers]]
→ [[engine-gate]]
→ [[workers-cairrn-worker]]
→ [[workers-cairrn-constants]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-workers-cerberus-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-cerberus-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-app-workers-py]]
→ [[cursor-ingest/2026-08-04-072347-source-engine-gate-md]]
→ [[cursor-ingest/2026-08-04-072347-source-workers-base-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
