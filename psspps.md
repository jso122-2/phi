# psspps — Perspective-Oriented Semantic Scored Personalized Parsing Scored

#code #math #hub

A RAG-inference pipeline that uses the [[harmonic-index]] as a live **perspective lens**
to bias knowledge retrieval toward the attractor basins you are currently exploring.

---

## What it does

```
query
  │
  ▼
Pre-router         infer: is retrieval even worth running?
  │                (slash-commands → skip; information queries → retrieve)
  ▼
Retriever          load every .md file from the Obsidian vault
  │
  ▼
Semantic scorer    TF-IDF cosine similarity between query and each doc
Perspective scorer harmonic index activations × doc basin affinity
Combined score     (1−α)·semantic + α·perspective
  │
  ▼
Post-router        infer: did RAG actually surface useful content?
                   lift = max_score − mean_score → rag_confidence ∈ [0,1]
  │
  ▼
PSPSPSResult       ranked docs + all scores + routing signals
```

---

## The perspective mechanism

Each document is mapped to the 8 harmonic basins by soft-assigning its
numeric content via a Gaussian kernel centred on each basin:

```
affinity_i = Σ_n  exp( −0.5 · (|n − basin_i| / σ)² )   σ = 0.5·α
```

The perspective score is then:

```
perspective = affinity · (index_activations / Σ activations)
```

So if you have been running `/sim` and the index is hot in shard 0 (basin 1.96),
documents that discuss values near 1.96 get a higher perspective score.

---

## Module map

```
psspps/
├── __init__.py        ← run_psspps, PSPSPSResult, ScoredDoc
├── retriever.py       ← load_vault_docs(), _parse(), _clean()
├── scorer.py          ← TF-IDF, harmonic_affinity, perspective_scores
├── router.py          ← should_retrieve(), rag_was_useful()
└── pipeline.py        ← run_psspps() — full pipeline orchestrator
```

---

## MCP tool

```
/psspps <query>
```

| Parameter          | Default | Description |
|--------------------|---------|-------------|
| `query`            | —       | Natural-language question or search string |
| `top_k`            | 3       | Number of top-ranked documents to return |
| `perspective_alpha`| 0.5     | 0.0 = pure semantic · 1.0 = pure perspective |

MCP tool: `psspps_query(query, top_k=3, perspective_alpha=0.5)`

---

## Example output shape

```json
{
  "query": "what is the Lambert W fixed point",
  "retrieval_triggered": true,
  "retrieval_confidence": 0.75,
  "rag_useful": true,
  "rag_confidence": 0.82,
  "n_docs_searched": 11,
  "top_docs": [
    {
      "title": "lambert-w",
      "semantic_score": 0.4312,
      "perspective_score": 0.1389,
      "combined_score": 0.285,
      "headings": ["Lambert-W fixed point", "Derivation"],
      "wikilinks": ["MATH", "attractors", "sims"],
      "snippet": "The fixed point of f(x) = −eˣ is x* = −W(1) ≈ −0.5671…"
    }
  ]
}
```

---

## Connections

→ [[HOME]] ← grand central  
→ [[CODE]] — sibling modules  
→ [[harmonic-index]] — provides the perspective activations  
→ [[mcp-server]] — exposes `psspps_query` as an MCP tool  
→ [[COMMANDS]] — `/psspps` slash command

---

## Auto-linked

→ [[live-state]]
→ [[graph]]
→ [[MATH]]
→ [[sessions]]
→ [[sims]]
→ [[environment]]

→ [[cairrn]]
→ [[index]]
→ [[temporal-index]]

→ [[README]]
→ [[2026-07-13-102400-temporal-sharding-index-cairrn-aware-ana-chi-hosted]]
→ [[ana-chi]]
→ [[2026-07-13-integrate-ana-chi-constant-modulate-cairrn-stable-states]]
→ [[hub-classifier]]

→ [[attractors]]
→ [[2026-07-16-011935-slash-commands-spotify-rip]]
→ [[2026-07-16-011935-mcp-tool-command-reference]]
→ [[2026-07-16-011935-cairrn-cairrn-worker-system]]

→ [[2026-07-16-011935-spotify-rip-mcp-server-global-agent-contract]]
→ [[2026-07-16-011935-spotify-rip-slash-commands]]
→ [[2026-07-13-042743-configure-the-obsidian-graph-as-the-hub-buil]]
→ [[lambert-w]]
→ [[cursor-skills]]
→ [[2026-07-16-011935-scribble-files-are-read-only]]

→ [[config]]
→ [[2026-07-16-011935-mamba-environment-spotify-rip]]
→ [[2026-07-16-011935-find]]
→ [[dev]]
→ [[git-log]]
→ [[2026-07-16-011935-modular-pipeline-rebuild]]
