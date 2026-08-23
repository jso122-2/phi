# source / workers-cairrn-desktop.md

#doc #md

> path: source/workers-cairrn-desktop.md  
> ext: .md  

---

# workers/cairrn/desktop

#code #module #workers #code

> source_path: workers/cairrn/desktop.py  
> package: workers  
> module: workers/cairrn/desktop  
> hub: CODE  
> created_ts:   

---

**Package:** `workers`  
**Module:** `workers/cairrn/desktop`  
**Source:** `workers/cairrn/desktop.py`

CAIRRN desktop formula I/O containers and dispatcher.

DesktopFormulaInputs  — all optional inputs for the 14 desktop formulas
DesktopFormulaOutputs — computed outputs (None when inputs were absent)
run_desktop_formulas  — dispatches inputs → outputs, skipping missing fields

Note: mypy cannot narrow Optional[float] fields through all(v is not None)
guards; the arg-type errors in run_desktop_formulas are structural false
positives. All call sites are runtime-safe.

## API

- `class DesktopFormulaInputs` — Optional inputs for desktop formula computation.
- `class DesktopFormulaOutputs` — Computed desktop formula outputs (None when inputs were absent).
- `def run_desktop_formulas` — Compute all desktop formulas for which inputs are present.

## Internal imports

`workers.cairrn.formulas`

---

## Semantic links

→ [[CODE]]
→ [[CODE]]
→ [[workers]]
→ [[2026-07-16-011935-cairrn-cairrn-worker-system]]
→ [[workers]]

## Related notes

→ [[source/workers-cairrn-formulas]]
→ [[source/workers-cairrn-worker]]
→ [[source/workers-cairrn-init]]
→ [[source/workers-cairrn-mycelial]]
→ [[source/workers-cairrn-constants]]

— import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[workers-index]]
→ [[workers-cairrn-z-space]]
→ [[workers-cairrn-worker]]
→ [[workers-cairrn-layers]]
→ [[workers-cairrn-formulas]]
→ [[workers-base]]

---

## Semantic links

→ [[workers-cairrn-desktop]]
→ [[workers-cairrn-worker]]
→ [[workers-cairrn-formulas]]
→ [[workers-cairrn-init]]
→ [[workers-base]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-workers-cairrn-z-space-md]]
→ [[cursor-ingest/2026-08-04-072347-workers-cairrn-desktop-py]]
→ [[cursor-ingest/2026-08-04-072347-source-workers-cairrn-formulas-md]]
→ [[cursor-ingest/2026-08-04-072347-source-workers-cairrn-worker-md]]
→ [[cursor-ingest/2026-08-04-072347-source-workers-cairrn-constants-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
