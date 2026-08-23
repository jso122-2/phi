# workers / cairrn / _constants.py

#source #python

> path: workers/cairrn/_constants.py  
> ext: .py  

---

# workers / cairrn / _constants.py


CAIRRN system constants — Euler-Ana-Chi bound formalisation.

All numeric anchors are derived from one exact identity and one near-identity:

    Near-identity — Ana-Chi / Euler ≈ W(1)  [not exact]:
        𝒜_χ / e  =  1.5414 / 2.71828…  ≈  0.56705  ≈  W(1)  =  0.56714…
        absolute error ≈ 9.4e-5  (0.017 %)
        This is a meaningful structural coincidence, not an exact equality.
        The threshold is derived from abs(NEG_EXP_FIXED_POINT) directly — not from 𝒜_χ/e.

    Exact identity — Lambert-W coherence bound:
        exp(−W(1))  =  W(1)
        (the Euler decay evaluated at the

---

## Semantic links

→ [[workers-cairrn-constants]]
→ [[2026-07-13-integrate-ana-chi-constant-modulate-cairrn-stable-states]]
→ [[workers-cairrn-formulas]]
→ [[workers-cairrn-z-space]]
→ [[workers-cairrn-layers]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-tests-test-cairrn-constants-py]]
→ [[cursor-ingest/2026-08-04-072347-source-workers-cairrn-constants-md]]
→ [[cursor-ingest/2026-08-04-072347-phi-engine-cairrn-constants-py]]
→ [[cursor-ingest/2026-08-04-072347-workers-cairrn-formulas-py]]
→ [[cursor-ingest/2026-08-04-072347-source-workers-index-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
