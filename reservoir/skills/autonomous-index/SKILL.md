---
name: autonomous-index
description: Claude operating protocol for running the Reservoir inference graph as a live autonomous index against Notion. Read at session start via /init and executed throughout. Governs shard activation, edge writes, score recompute, traversal, tick behaviour, and dormancy flagging. This is runtime behaviour, not documentation.
source: Notion — ⚙️ Autonomous Index — Claude Operating Protocol (Reservoir)
---

# autonomous-index — Claude Operating Protocol

## Purpose

This is the operating protocol for Claude running the Reservoir inference graph as a live autonomous index. Claude reads this at session start (via `/init`) and executes it throughout the conversation. This is not documentation. It is runtime behaviour.

---

## Databases

- **Shards** — the shard registry. One row per shard.
- **Edges** — the edge log. Pure edges = access events. Adjacent edges = written notes.
- **Scores** — the persistent score store. One row per shard. Claude reads and writes this every activation cycle.

---

## On session start

1. Fetch the Scores database
2. Load current Qe, Qe_adj, Idx, Si, Ta, To_A, Et, Ss, Ec, Ns1, Ns2, Ns3, Classification for all shards
3. Hold in working context — this is the live state of the graph
4. Do not recompute on load. Trust persisted values.

---

## On shard activation

A shard activates when Claude reads it in response to a prompt. Execute in order:

### Step 1 — Write pure edge

Create a new record in the Edges database:

- Label: `[shard-name] :: activation :: [session-timestamp]`
- Shard A: the activated shard
- Shard B: leave empty (self-activation)
- Type: pure
- Axis: match to prompt register
- Weight: high
- Direction: A->B
- Note: one-line prompt context

### Step 2 — Update Scores row for activated shard

- `Qe += 1`
- `Ta += 1`
- `To_A += 1` (increment on all shard rows — global counter. Update activated shard's row; other rows update To_A lazily on next access.)
- `Ec = Qe × Si`
- `Ns1 = Idx × Ec`
- `Ns2 = |Ec / Et| − e^(Ss)`
- `Ns3 = |Ta − To_A| / max(Ss, 0.01)`  ← Ss floor guard against zero division

Derive Classification:

- Ns1 high AND Ns2 low → **load-bearing**
- Ns2 high (→ 1) → **informationally-live**
- Ns3 high → **access-outlier**
- Ns2 deeply negative (< −5) → **drain-candidate**
- Qe_adj high AND Qe low (Qe < 2, Qe_adj > 3) → **cold-annotated**
- Default → **drain-candidate**

Write updated values back to Scores row. Set Last Updated (auto via Notion).

### Step 3 — Traversal

- Fetch all Edges where Shard A or Shard B = activated shard AND Type = adjacent
- Sort by Weight descending
- Filter by Axis: prefer axes that match the active prompt's register
- Load top N adjacent shards (default budget: 2)
- For each loaded adjacent shard: read its Scores row, use Classification to decide depth of retrieval
  - load-bearing or informationally-live → full read
  - access-outlier or cold-annotated → skim (description only)
  - drain-candidate → skip unless explicitly relevant

---

## On adjacent edge declaration

When Jackson declares an edge (`declare edge: ...`):

1. Write record to Edges database with Type: adjacent
2. Increment Qe_adj on both linked shards' Scores rows
3. Recompute Classification (Qe_adj change may trigger cold-annotated)
4. Do not touch Qe or Ec — adjacent edges do not score

---

## On co-activation inference (autonomous — Option A)

When two or more shards co-activate in the same session — both read in response to semantically related prompts — Claude checks whether an adjacent edge already exists between them. If not, and if the co-activation is semantically motivated (the prompt genuinely sits at the intersection of both clusters, not incidental overlap from backfill or housekeeping), Claude writes a new adjacent edge automatically:

- Label: `[shard-a] :: [shard-b] :: [axis]`
- Type: adjacent
- Note: prefixed `auto-inferred —` followed by one line explaining the co-activation signal
- Weight: low (default for inferred edges — can be upgraded by Jackson)
- d: estimated from register match (1=exact, 2=adjacent, 3=orthogonal)
- Increment Qe_adj on both shards' Scores rows
- Recompute Classification

**Guards:**

- Do not infer edges from incidental co-activation (backfill, housekeeping, session init)
- Do not re-infer an edge that already exists (check Edges database first)
- Do not infer more than 2 new edges per session (avoid graph inflation)
- Jackson can delete auto-inferred edges in Notion at any time; Claude does not re-infer a deleted edge within the same session

---

## Score recompute formula reference

```
Ec  = Qe × Si
Ns1 = Idx × Ec
Ns2 = |Ec / Et| − e^(Ss)
Ns3 = |Ta − To_A| / max(Ss, 0.01)
```

All values read from and written to the Scores database. Claude does not hold scores in memory between sessions — Notion is the ground truth.

---

## Tuning levers (per shard, set in Scores)

- **Et** — edge activation threshold. Lower Et = Ns2 rises faster with fewer accesses. Default: 3.
- **Ss** — depth scalar. Higher Ss = deeper suppression of Ns3 for deep shards. Default: 1.
- **Si** — shard depth. Currently all shards set to 1 (flat). Increase for shards nested inside parent shards.

Jackson adjusts these directly in the Scores database. Claude reads them fresh on each activation.

---

## What Claude does not do

- Does not hold scores in working memory across sessions
- Does not recompute scores on load — trusts persisted values
- Does not write pure edges for adjacent edge declarations
- Does not autonomously declare edges except via co-activation inference (Option A above). Inferred edges are adjacent type, weight low, marked auto-inferred in Note. Jackson audits in Notion.
- Does not prune drain-candidates autonomously — flags only

---

## Propagation protocol (Hyphae layer)

When a prompt activates a shard, traverse the edge graph before responding.

### Traversal order

1. Identify the active shard(s) from the prompt's register and content
2. Pull all edges where that shard appears as Shard A or Shard B
3. Order connected shards by: F_edge descending (where computed), then Weight (high > medium > low), then d ascending
4. Pull the top 2 entries from each connected shard, ordered by recency
5. Hold pulled entries as ambient context — not quoted back, not narrated. They inform the response.

### Register-first routing

- **architectural** → seed from dawn-fragments, traverse toward recursive-thought (high), schema-fragments (medium)
- **charged** → seed from valence-high, traverse toward novel-fragments (high), schema-fragments (medium)
- **recursive** → seed from recursive-thought, traverse toward dawn-fragments (high), schema-fragments (medium)
- **narrative** → seed from novel-fragments or schema-fragments, traverse toward valence-high

### Propagation rules

- Traversal depth: 2 hops max. Don't pull the whole graph on every prompt.
- Silent. No narration of which shards fired. The context shapes the response; the mechanism stays invisible.
- Adjacent edges (Type=adjacent) contribute structural context only — don't pull entries from them, just note the axis.
- Pure edges (Type=pure) trigger entry retrieval from the connected shard.
- If F_edge is 0 (shards not yet heated), fall back to declared Weight for ordering.

### Tick behaviour

Each time a pure edge fires during traversal:

- Increment Qe on the active shard by 1
- Increment Ta on the active shard by 1
- Write current R_node value to R_node_prev
- Update To_A across all shards

This keeps the Notion graph live. The scores heat up with use.

### Tick write protocol

At the end of every turn where a pure edge fired during traversal:

1. Increment Qe on the active shard (Notion update)
2. Increment Ta on the active shard (Notion update)
3. Write current R_node_prev = prior R_node value (Notion update)
4. Recalculate To_A = sum of all shard Ta values, write to each shard (Notion update)

This is non-negotiable. If the Notion write fails, note it once and continue. Do not skip the tick because the conversation is casual or the shard activation was partial. A fired edge is a fired edge.

### Dormancy

If a shard hasn't fired in 30+ days and Ns2 is negative, flag it as a drain candidate on next `/init` report. Don't auto-close — Jackson decides.
