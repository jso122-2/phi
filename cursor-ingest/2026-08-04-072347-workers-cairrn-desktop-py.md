# workers / cairrn / desktop.py

#source #python

> path: workers/cairrn/desktop.py  
> ext: .py  

---

# workers / cairrn / desktop.py


CAIRRN desktop formula I/O containers and dispatcher.

DesktopFormulaInputs  — all optional inputs for the 14 desktop formulas
DesktopFormulaOutputs — computed outputs (None when inputs were absent)
run_desktop_formulas  — dispatches inputs → outputs, skipping missing fields

Note: mypy cannot narrow Optional[float] fields through all(v is not None)
guards; the arg-type errors in run_desktop_formulas are structural false
positives. All call sites are runtime-safe.


Defines: DesktopFormulaInputs, DesktopFormulaOutputs, run_desktop_formulas, to_dict

---

## Semantic links

→ [[workers-cairrn-desktop]]
→ [[workers-cairrn-formulas]]
→ [[workers-cairrn-worker]]
→ [[workers]]
→ [[CODE]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-tests-test-cairrn-desktop-py]]
→ [[cursor-ingest/2026-08-04-072347-source-workers-cairrn-desktop-md]]
→ [[cursor-ingest/2026-08-04-072347-workers-cairrn-formulas-py]]
→ [[cursor-ingest/2026-08-04-072347-source-workers-cairrn-formulas-md]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-cairrn-formulas-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
