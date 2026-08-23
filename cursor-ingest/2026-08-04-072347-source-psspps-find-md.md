# source / psspps-find.md

#doc #md

> path: source/psspps-find.md  
> ext: .md  

---

# psspps/find

#code #module #psspps #code

> source_path: psspps/find.py  
> package: psspps  
> module: psspps/find  
> hub: CODE  
> created_ts:   

---

**Package:** `psspps`  
**Module:** `psspps/find`  
**Source:** `psspps/find.py`

/find — Pericles-scored exact-retrieval pipeline.

Funnel:  all vault docs → top-5 by combined score
                        → Pericles re-scoring
                        → top-3 shown to operator
                        → top-1 as the final answer

The Pericles formula
--------------------
    per = |tc_A - Adp_At| * k / x

where:
    tc_A     — total positional term count: Σ_t Σ_pos 1/(pos+1) for each
                query-token hit in the document body; earlier hits count more.
    Adp_At   — adaptive harmonic temporal score: perspective_score multiplied by
                exp(−λ · harmonic_step) so fresher index states weigh more.
    k        — combined TF-IDF + harmonic relevance score (the k-score).
    x        — confidence denominator: max(|k · N_j|, D)  [∨ = max]
    N_j      — normalised Jules score (entropy, normalised to 0.00 target):
                Shannon entropy of the doc's TF-IDF row, shifted batch-wide
                so the most-focused document scores exactly 0.00.
    D        — drift / iwave score: sin(π · β / 2) where β = k / max_k.
                A positive half-sine iwave — β = 0 → D = 0, β = 1 → D = 1.

Pericles (495–429 BC) — Athenian autocratic statesman.
If Pericles had a scoring formula, it would be this one: precise, positional,
and temporally weighted, with a confidence floor that prevents noise from
inflating weak candidates.

## API

- `class PericlesScore` — All intermediate values for the Pericles formula, fully auditable.
- `class FindCandidate`
- `class FindResult`
- `def _positional_term_count` — For every occurrence of a query token in the document body,
- `def _adaptive_temporal` — Adaptive score of the Active node, temporally weighted.
- `def _jules_entropy_raw` — Raw normalised entropy

---

## Semantic links

→ [[psspps-find]]
→ [[mcp-server-tools-search]]
→ [[psspps-pipeline]]
→ [[psspps-retriever]]
→ [[psspps-traverser]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-psspps-find-py]]
→ [[cursor-ingest/2026-08-04-072347-source-psspps-retriever-md]]
→ [[cursor-ingest/2026-08-04-072347-psspps-retriever-py]]
→ [[cursor-ingest/2026-08-04-072347-psspps-pipeline-py]]
→ [[cursor-ingest/2026-08-04-072347-mcp-server-tools-search-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
