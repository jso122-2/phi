# Notion export — Reservoir skills + maths

Exported 2026-09-07 from the Notion workspace *jack dev's Space*.

Two trees:

```
notion/
├── skills/     — 12 skills, each as <name>/SKILL.md (frontmatter + body)
└── maths/      — 12 markdown files, chronological by derivation
```

---

## skills/

Drop-in shaped for `/mnt/skills/user/`. Each has YAML frontmatter with `name`, `description`, and a `source` line pointing back at the Notion page it came from.

| Folder | What it is | Notion source |
|---|---|---|
| `jackson-manifest/` | Constitutional layer. Always active. Tone, posture, hard stops. | ⚙️ Skills — Compressed |
| `init/` | `/init` boot sequence — inventory shards, load edges, report one line. | ⚙️ Skills — Compressed |
| `inference-graph/` | Edge layer. Edge format, traversal rules, six declared edges. | inference-graph page |
| `user-index/` | Retrieval protocol. P_sps → relevance → PSI → drift. Surface vs throughline. | ⚙️ Skills — Compressed |
| `backfill/` | One-shot bootstrap from conversation history, with confidence tagging. | ⚙️ Skills — Compressed |
| `schema-fragments/` | Shard — Schema essay series. | Shards DB + Skills — Compressed |
| `dawn-fragments/` | Shard — DAWN architecture and commercial. | Shards DB + Skills — Compressed |
| `novel-fragments/` | Shard — the 2300 novel. | Shards DB + Skills — Compressed |
| `valence-high/` | Shard — charged register, cross-topic. | Shards DB + Skills — Compressed |
| `recursive-thought/` | Shard — meta layer. | Shards DB + Skills — Compressed |
| `autonomous-index/` | Claude operating protocol for running the graph live against Notion. Activation, edge writes, score recompute, tick protocol, dormancy. | ⚙️ Autonomous Index |
| `edge-address-index/` | Routing table for external environments. Shard page addresses, edge record format, traversal logic. | 🗺️ Edge Address Index |

Each shard file carries its live Shards-DB scoring row (Idx, Qe, Si, Ss, Et, Ta, To_A) as of export.

---

## maths/

| File | Content |
|---|---|
| `01-mathematics-canonical-stack.md` | **The law.** Layers 0–9 plus the seven cross-layer laws. Start here. |
| `02-semantic-field-formulae.md` | May 2025 — radial position, cosine similarity, edge weight, path cost, nutrient decay, pressure heatmap. |
| `03-planck-to-relativity.md` | Aug 2025 — Planck anchors, cognitive pressure, SHI, shimmer decay, cognitive gravity, entropy loop, voice mutation, Wolf repair. |
| `04-rag-formula.md` | Dec 2025 — P_sps derivation with full variable sourcing. |
| `05-monday-formula-sheet.md` | Oct 2025 — Shannon extension, load coefficient, forecast index, recursive depth, error correction. |
| `06-formulas-1212-25.md` | Dec 2025 handwritten sheets — pointer only, images not exportable. |
| `07-formulas-13-12-25.md` | Dec 2025 handwritten sheets — pointer only, images not exportable. |
| `08-anderson-schema-logic-matrix.md` | May 2025 — six paths, six gates, semantic attention validation, BERT/Bi-LSTM pipeline. |
| `09-gemini-ana-chi-attractor-states.md` | Dec 2025 — 𝒜_χ = 1.5414, SSDDCS, the four attractor states and their fractal dimensions. |
| `10-notion-data-stream-score-formalisation.md` | **The longest file.** Ec/Ns1/Ns2/Ns3 formalisation, full corpus restatement, the three handwritten sheets transcribed, Layers 6–8 (semantic field integration, math-based edges, edge state definition). |
| `11-reservoir-maths-database.md` | All 5 rows of the `reservoir-maths` DB — equation, variables, Python and SQL reference implementations for relevance, drift, resonance, valence, traversal. |
| `12-shards-database-formulas.md` | Shards DB formula properties (Ec, Ns1, Ns2, Ns3, R_node, Si_delta), input field definitions, and live row state. |

---

## Not exported

- The two `Formulas 12/13-12-25` image sets (handwritten sheets) — Notion's signed image URLs expire and the connector only pulls text. The typed transcriptions are in `01` Layer 9 and `10` "New maths — handwritten sheets".
- Entries, Edges and Scores database rows — these are running state, not maths or skills. Say the word if you want them too.
