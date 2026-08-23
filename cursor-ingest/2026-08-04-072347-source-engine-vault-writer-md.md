# source / engine-vault-writer.md

#doc #md

> path: source/engine-vault-writer.md  
> ext: .md  

---

# engine/vault_writer

#code #module #engine #code

> source_path: engine/vault_writer.py  
> package: engine  
> module: engine/vault_writer  
> hub: CODE  
> created_ts:   

---

**Package:** `engine`  
**Module:** `engine/vault_writer`  
**Source:** `engine/vault_writer.py`

SambaWriter — arm score → vault mutation layer.

Final stage of the OctopusTracer pipeline (ARCHITECTURE LOCKED — pow.md):

    8 MLP HEADS (arms) → SUCKER LAYER → Samba MCP → vault writes

Arm → vault action mapping:
    PRUNE     → prune-flag node  (mark high-score nodes for human review)
    GRAFT     → graft node       (structural join between complement neighbours)
    CLUSTER   → cluster node     (wikilinks between high-score neighbour pairs)
    RANK      → rank node        (priority metadata update)
    TAG       → tag node         (content-derived tag annotation)
    RESURFACE → resurface node   (orphan → hub wikilink reinstated)
    MERGE     → merge-candidate  (annotation on both merge targets)
    SPROUT    → sprout node      (new node — structural gap in graph)

Coherence gate (engine/gate.py):
    coherence < W(1) ≈ 0.5671  →  dry-run; decisions computed but NOT written to disk
    coherence ≥ W(1) ≈ 0.5671  →  live writes to  sessions/samba/<timestamp>-<arm>-<slug>.md

Each arm fires independently when its mean score exceeds `arm_threshold`.
Arm nodes are written to:  <vault_root>/sessions/samba/

All writes are append-only — SambaWriter never overwrites existing nodes.

## API

- `class SambaWrite` — Record of one arm's vault write decision.
- `class SambaResult` — Aggregated result from one SambaWriter.process() call.
- `class SambaWriter` — Translates TracerDaemon arm scores into vault file mutations.
- `def _slug`
- `def make_samba_writer` — Construct a SambaWriter.  Defaults to the project vault root if not given.

## Internal imports

`engine.gate`, `graph.node`

---

## Semantic links

→ [[2026-07-16-011935-vault-coherence-engine]]
→ [[graph]]
→ [[hub-classifier]]
→ [[gr

---

## Semantic links

→ [[engine-vault-writer]]
→ [[engine-vault-garden]]
→ [[engine-coherence-daemon]]
→ [[engine-gate]]
→ [[mcp-server-vault-hub]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-engine-vault-writer-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-vault-writer-py]]
→ [[cursor-ingest/2026-08-04-072347-source-engine-vault-garden-md]]
→ [[cursor-ingest/2026-08-04-072347-source-engine-coherence-daemon-md]]
→ [[cursor-ingest/2026-08-04-072347-engine-coherence-daemon-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
