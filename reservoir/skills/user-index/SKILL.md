---
name: user-index
description: Reservoir retrieval protocol. Triggers when Jackson asks reflective questions about his own thinking — "what have I been circling on", "where did I leave that thread", "have I said this before", "show me my reservoir", "what does my thinking look like" — or explicitly invokes the index. Operates on shard files as a corpus. Returns Jackson's own prompts, surfaced and weighted by the relevance equations below. Not summary. His voice, back at him.
source: Notion — ⚙️ Skills — Compressed (Reservoir)
---

# user-index

**Triggers:** Reflective questions — "what have I been circling", "where did I leave that", "show me my reservoir", "what does my thinking look like".

Returns Jackson's own prompts, not Claude's summaries.

---

## Stage 1 — Shard Selection (P_sps)

Before intra-shard retrieval, score all active shards via P_sps. Pull in descending order.

```
P_sps = (X_norm / O(N)) − (T_pos / P_risk)
```

- `X_norm` — semantic similarity of shard to active prompt (Layer 1 cosine, approximated interpretively)
- `O(N)` — shard size penalty — entry count. Larger shard = higher penalty = depressed priority
- `T_pos` — recency decay — time since shard last accessed. Older = higher T_pos = lower P_sps
- `P_risk` — register tolerance — distance between shard valence profile and active prompt register. High P_risk = softer penalty for peripheral content

Higher P_sps = open this shard first. P_sps < 0 = deprioritised but not excluded.

---

## Stage 2 — Intra-shard Retrieval (a)

```
a = |p - f/v| * x     (interpretive frame, not real math)
```

- `p` — semantic context of active prompt
- `f` — friction: semantic distance
- `v` — valence: register match
- `x` — retrieval cost: depth

Lower `a` = higher relevance. Runs inside each shard in P_sps rank order.

---

## Stage 3 — Depth Control (PSI)

```
PSI = |E−1| / n · DH
```

Sets how deep to go inside the winning shard. High PSI = wide search. Low PSI = tight local. Downstream of P_sps, upstream of node-level scoring (Ns1/Ns2/Ns3).

---

## Drift

```
drift = |a - z| / r
```

- High drift, low resonance = new territory
- Low drift, high resonance = circling familiar ground
- High drift, high resonance = sharp pivot inside known space
- Low drift, low resonance = stuck on something rare

---

## Output modes

- **Surface** — material, not synthesis. His words, dated, lightly framed.
- **Throughline** — pattern synthesis grounded in quoted fragments.

Default to surface if ambiguous.

---

## Update

Only via `shard this`. No automatic clustering.
