# Rag formula_

*Source: Notion — Reservoir / 📐 Mathematics — Canonical Stack / Rag formula_*
*Dated in page: Dec 6, 2025, 11:33:19 PM*

## RAG Semantic Priority Score (P_sps)

This formula determines the final index rank and context clipping priority. It is used during ingestion to calculate the priority of each chunk.

```
P_sps = (X_norm / O(N)) − (T_pos / P_risk)
```

### Variables defined

**P_sps — Semantic Priority Score**
The final score used to `ORDER BY` and `LIMIT` the search results (n). A higher score indicates higher retrieval priority.

**X_norm — Semantic Awareness**
Source: Random Forest (RF) output (regression, range [0, 1]).
Role: The inherent importance or actionability of the text chunk.

**O(N) — System Complexity**
Source: System metric.
Role: Dynamic penalty representing the system's current load (e.g. CPU, indexing overhead).

**T_pos — Positional Context**
Source: Business logic / file metadata.
Role: Penalty factor based on time decay, recency, or hierarchical depth.

**P_risk — Perplexity Risk**
Source: Global system constant (tuning lever).
Role: Controls the system's willingness to index and keep peripheral, lower-value content.
