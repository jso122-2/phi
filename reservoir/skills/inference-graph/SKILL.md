---
name: inference-graph
description: Edge layer of the reservoir. Declares relationships between shards — which clusters relate to which, along which axis, with what weight. Loaded by /init. Read whenever shard retrieval is active, to determine traversal order. Edges are textual and structured. Not auto-generated; declared by Jackson over time.
source: Notion — inference-graph (Reservoir) + ⚙️ Skills — Compressed
---

# inference-graph

Edge layer of the reservoir. Declares relationships between shards — which clusters relate to which, along which axis, with what weight. Loaded by `/init`. Read whenever shard retrieval is active, to determine traversal order. Edges are textual and structured. Not auto-generated; declared by Jackson over time.

---

## Edge format

`shard-A`, `shard-B` — names matching skill files in `/mnt/skills/user/`

```
[shard-A] <-> [shard-B] :: axis :: weight :: note
```

- `axis` — what dimension connects them (semantic, valence, recursive, structural, biographical)
- `weight` — high / medium / low. Soft signal for retrieval ordering.
- `note` — one-line context. Why this edge exists.

Bidirectional by default (`<->`). Use `->` for asymmetric edges (A pulls from B, but not the reverse).

---

## Traversal rules

When a prompt activates a shard, also pull from edge-connected shards weighted by:

1. Edge weight (high pulls more than low)
2. Axis match to active prompt's register
3. Recency of edge declaration (newer edges weight higher — declared edges are still being thought through)

---

## Declared edges

```
[schema-fragments] <-> [dawn-fragments] :: structural :: medium :: both are published/architectural output — prose and system design share a load-bearing register

[valence-high] <-> [novel-fragments] :: valence :: high :: novel is gift-work, woman-recipient context activates both simultaneously

[recursive-thought] -> [schema-fragments] :: recursive :: medium :: Schema essays often emerge from Jackson revisiting a prior frame

[recursive-thought] -> [dawn-fragments] :: recursive :: medium :: DAWN architecture iterates — design decisions get re-examined

[recursive-thought] -> [valence-high] :: recursive :: low :: recurrence and emotional charge sometimes co-occur but aren't structurally linked

[valence-high] -> [schema-fragments] :: valence :: medium :: Schema can carry charge — the tunnel rave piece, the "1 of 2" framing
```

---

## Edges to consider declaring

- Biographical memory edits and shards aren't connected directly — memory holds state, shards hold voice. Different layers.

---

## Update protocol

New edges enter via Jackson's explicit declaration:

```
declare edge: [A] <-> [B] :: axis :: weight :: note
```

Or implicit, when Jackson observes a connection in conversation and asks Claude to record it. Claude does not declare edges autonomously — the wiring is Jackson's call.
