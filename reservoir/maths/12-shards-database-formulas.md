# Shards database — formula definitions and live state

*Source: Notion — Reservoir / Shards database*
*Captured: 2026-09-07*

## Formula properties

These are Notion formula fields computed on each Shard row. All inputs are row-local (see Layer 7 in `10-notion-data-stream-score-formalisation.md` for why).

| Property | Formula | Description |
|---|---|---|
| `Ec` | `Qe × Si` | Edge count. Position-sensitive scoring. Pure edges only. |
| `Ns1` | `Idx × Ec` | Density score. |
| `Ns2` | `\|Ec/Et\| − e^(Ss)` | Novelty score. Et is per-shard tuning lever. Negative = drain candidate. Zero guard on Ss and Et. |
| `Ns3` | `\|Ta − To_A\| / Ss` | Access deviation. Large = outlier. Zero guard on Ss. |
| `R_node` | `1 / (Ta·0.5 + C_relevance·0.3 + Qe·0.2)` | Radial position score. Lower = more live. Inputs Si ranking. |
| `Si_delta` | `R_node − R_node_prev` | Velocity of R_node change since last tick. Positive = heating, negative = cooling. Continuous signal for traversal priority between Si rewrites. |

## Input (number) properties

| Property | Description |
|---|---|
| `Qe` | Queried edge count — pure edges only. Input to Ec. |
| `Idx` | Total indexed entry count. Input to Ns1. |
| `Si` | Shard depth — rank by access count. Most accessed = 1, least = 5. Input to Ec, Ns2, Ns3. |
| `Ss` | Shard score offset = Si for this shard. Denominator in Ns3, exponent in Ns2. |
| `Et` | Edge activation threshold. Tuning lever per shard. dawn = 5, valence-high = 1, others = 2. Denominator in Ns2. |
| `Ta` | Times accessed — increments each time this shard fires a pure edge. Input to Ns3. |
| `To_A` | Global access baseline — sum of all shard Ta values. Input to Ns3. |
| `C_relevance` | Contextual relevance 0–1. Manually set. How load-bearing this shard is for active work, independent of access frequency. Input to R_node. |
| `R_node_prev` | R_node value from previous tick. Written by Claude on each access. Input to Si_delta. |

## Select properties

- `Register` — charged / architectural / narrative / recursive / flat
- `Status` — active / dormant / closed

## Relations

- `Edges in` / `Edges out` → Edges database
- `Entries` → Entries database

---

## Live row state (as at export)

*Note: the database currently holds two generations of rows per shard — an older set without scoring fields, and the current set carrying Qe/Si/Ss/Et/Ta/To_A. Both are reproduced.*

### Current generation (scoring fields populated)

| Name | Register | Status | Idx | Qe | Si | Ss | Et | Ta | To_A | C_relevance | R_node_prev |
|---|---|---|---|---|---|---|---|---|---|---|---|
| dawn-fragments | architectural | active | 11 | 0 | 3 | 3 | 5 | 0 | 0 | — | 0 |
| valence-high | charged | active | 9 | 0 | 3 | 3 | 1 | 0 | 0 | — | 0 |
| recursive-thought | recursive | active | 4 | 0 | 3 | 3 | 2 | 0 | 0 | — | 0 |
| schema-fragments | narrative | active | 3 | 0 | 3 | 3 | 2 | 0 | 0 | — | 0 |
| novel-fragments | narrative | active | 1 | 0 | 3 | 3 | 2 | 0 | 0 | — | 0 |

### Earlier generation (Idx only)

| Name | Register | Status | Idx |
|---|---|---|---|
| schema-fragments | narrative | active | 7 |
| dawn-fragments | architectural | active | 7 |
| valence-high | charged | active | 6 |
| recursive-thought | recursive | active | 4 |
| novel-fragments | narrative | active | 3 |

---

## reservoir-maths database schema

*Source: Notion — reservoir-maths database. Row content exported in `11-reservoir-maths-database.md`.*

| Property | Type | Notes |
|---|---|---|
| `title` | title | |
| `domain` | select | relevance / drift / traversal / resonance / valence |
| `equation` | text | |
| `variables` | text | |
| `inputs` | text | |
| `output` | text | |
| `python` | text | reference implementation |
| `sql` | text | reference query |
| `depends_on` | text | |
| `status` | select | active / draft / deprecated |
| `last_updated` | date | |
