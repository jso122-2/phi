---
name: init
description: Reservoir boot sequence. Triggers on the literal string /init anywhere in a message. Inventories shards, loads the inference graph, cross-references memory, and reports one line of state. Executes silently — no preamble, no narration.
source: Notion — ⚙️ Skills — Compressed (Reservoir)
---

# init

**Triggers:** Literal string `/init` anywhere in message.

Execute silently. No preamble.

1. `view /mnt/skills/user/` — inventory shards
2. `view inference-graph/SKILL.md` — load edges
3. `memory_user_edits view` — hold autobiographical ledger
4. Cross-reference: populated vs empty shards, broken edges, memory edits implying undeclared shards
5. Output one line:

```
reservoir online :: N shards (M populated) :: K edges :: last delta: <date|none> :: anomalies: <list|none>
```

## Does not

- Bootstrap from `conversation_search`
- Run shard updates
- Narrate execution
