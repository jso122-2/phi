# source / psspps-scorer.md

#doc #md

> path: source/psspps-scorer.md  
> ext: .md  

---

# psspps/scorer

#code #module #psspps #code

> source_path: psspps/scorer.py  
> package: psspps  
> module: psspps/scorer  
> hub: CODE  
> created_ts:   

---

**Package:** `psspps`  
**Module:** `psspps/scorer`  
**Source:** `psspps/scorer.py`

TF-IDF semantic scoring + harmonic perspective scoring for PSSPPS.

Semantic score  — cosine similarity between query and document TF-IDF vectors.
Perspective score — dot product of the document's harmonic affinity vector with
                    the current harmonic index activations.

The affinity vector encodes which attractor basins a document "lives in" by
soft-assigning each numeric value found in its text to the nearest basin centre
via a Gaussian kernel.  Documents that discuss maths near the active harmonics
float to the top automatically.

## API

- `def tokenize`
- `def build_tfidf` — Build a TF-IDF matrix for a list of plain-text documents.
- `def query_vector` — Convert a query string to an L2-normalised TF-IDF vector.
- `def semantic_scores` — Cosine similarity between query vector and every document row.
- `def harmonic_affinity` — Map a document's numeric content to an 8-dim basin affinity vector.
- `def perspective_scores` — Dot product of each document's basin affinity with the harmonic index state.
- `def combined_scores` — Blend semantic and perspective scores.
- `def _structural_order` — Structural order of a probability distribution over basins.
- `def coherence_scores` — Coherence score per document: structural_order × harmonic_alignment.
- `def ana_chi_weight` — Topology correction weight derived from the Ana-Chi coherence formula.
- `def refresh_on_cache` — Update the cached O(N) complexity value from an external doc count.
- `def _get_o_n` — Return cached O(N) if set, else compute from live doc count.
- `def rag_priority_score` — RAG Semantic Priority Score.

## Internal imports

`sims.attractors`

---

## Semantic links

→ [[psspps]]
→ [[psspps]]
→ [[FORMULAS]]
→ [[2025-05-26-141815-semantic-fei

---

## Semantic links

→ [[psspps-scorer]]
→ [[psspps-init]]
→ [[psspps-pipeline]]
→ [[psspps-find]]
→ [[psspps-retriever]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-psspps-init-py]]
→ [[cursor-ingest/2026-08-04-072347-psspps-scorer-py]]
→ [[cursor-ingest/2026-08-04-072347-psspps-md]]
→ [[cursor-ingest/2026-08-04-072347-psspps-pipeline-py]]
→ [[cursor-ingest/2026-08-04-072347-source-psspps-index-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
