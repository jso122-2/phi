---
name: backfill
description: Bootstrap protocol for populating empty shards from past conversation history. Triggers when Jackson invokes "backfill", "backfill shards", or "populate the reservoir". Runs conversation_search against past chats per shard, presents candidates for review, writes approved entries with confidence tags. Designed for one-time or periodic use, not continuous. Honest about the contamination risk — backfilled material is Claude's retrieval of Jackson, not Jackson's voice unmediated, and is tagged accordingly.
source: Notion — ⚙️ Skills — Compressed (Reservoir)
---

# backfill

**Triggers:** "backfill", "backfill shards", "populate the reservoir".

One-shot bootstrap. Contamination risk is surfaced and tagged, not hidden.

## Stage 1 — Retrieval

Per shard, run `conversation_search` 2–5x with varied queries. Tag each candidate: `verbatim` / `trimmed` / `reconstructed`.

## Stage 2 — Review

Present batches grouped by shard. Jackson responds:

- `approve all`
- `approve [N,N]`
- `trim [N]: [edit]`
- `reject [N]`
- `redo [shard]`

## Stage 3 — Write

Approved entries land with `backfilled` + confidence tag. Reconstructed entries get `~` prefix.

## Weighting downstream

- `verbatim` = full signal (Cw = 1.0)
- `trimmed` = slightly lower (Cw = 0.7)
- `reconstructed` = lowest, excludable (Cw = 0.4)

Re-run with `backfill fresh [shard]` — clears backfilled entries, keeps manually added ones.
