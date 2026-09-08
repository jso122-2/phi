---
name: edge-address-index
description: Machine-readable address index and routing table for the Reservoir inference graph. Read when an external environment needs to query edges, resolve shard page addresses, declare new edges, or execute traversal locally. Notion is the bridge, not the destination.
source: Notion — 🗺️ Edge Address Index — Protocol (Reservoir)
---

# edge-address-index — Protocol

## Purpose

This document is a machine-readable address index for the Reservoir inference graph. It is not documentation. It is a routing table. The intended use is: another environment queries this page, parses the edge records, and executes traversal logic locally. Notion is the bridge, not the destination.

---

## Edge record format

Each edge is one row in the **Edges** database.

Fields per record:

- **Label** — human-readable address in the form `[node_a] :: [node_b] :: [axis]`
- **Shard A** — relation link to source shard page
- **Shard B** — relation link to target shard page
- **Axis** — semantic | valence | recursive | structural | biographical
- **Weight** — high | medium | low
- **Direction** — bidirectional | A->B
- **Type** — **pure** | **adjacent**
  - pure = access event, increments Qe, drives Ec and Ns1/Ns2/Ns3
  - adjacent = written note, structural routing metadata only, does not score
- **Note** — plain language description of why the edge exists
- **Declared** — auto-timestamp of when the edge was written

---

## Shard address table

Canonical identifiers when referencing shards from an external environment.

| Shard | Notion page |
|---|---|
| dawn-fragments | `https://app.notion.com/p/352350886c9d81c38263ce95469d73e4` |
| schema-fragments | `https://app.notion.com/p/352350886c9d81229773d570a046c882` |
| novel-fragments | `https://app.notion.com/p/352350886c9d81ca9d16ebaedd008e86` |
| valence-high | `https://app.notion.com/p/352350886c9d81caa79bfae32067a88b` |
| recursive-thought | `https://app.notion.com/p/352350886c9d8167be66c1ae82404aa2` |

**Edges database:** `https://app.notion.com/p/1c53019e6d7d44b99bb7540bad2ce732`

To query all edges from an external environment: fetch this database, filter by Shard A or Shard B URL, sort by Weight descending. Direction field tells you whether traversal is one-way or open.

---

## Declaring new edges

New edges are written to the Edges database by Claude on instruction. Format:

```
declare edge: [shard-a] <-> [shard-b] :: [axis] :: [weight] :: [note]
```

Or for asymmetric:

```
declare edge: [shard-a] -> [shard-b] :: [axis] :: [weight] :: [note]
```

Claude writes the record. The Declared timestamp is automatic. The index is live immediately.

---

## Traversal logic for external environments

When a shard activates:

1. Write a new pure edge record for the activation event (Type: pure). This increments Qe for scoring.
2. Fetch all edges where Shard A or Shard B matches the active shard URL
3. Split by Type: pure edges update scoring (Qe → Ec → Ns1/Ns2/Ns3). Adjacent edges govern traversal candidates.
4. Filter adjacent edges by Direction: bidirectional edges load both nodes, A->B edges load only B from A
5. Sort adjacent candidates by Weight: high first
6. Apply Axis filter: match axis to active prompt's register (semantic prompt → semantic edges weighted higher, etc.)
7. Load adjacent shards in order until traversal budget is exhausted

Pure edges are not traversal candidates — they are the activation record. Do not route on pure edges.
