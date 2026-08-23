# engine / vault_writer.py

#source #python

> path: engine/vault_writer.py  
> ext: .py  

---

# engine / vault_writer.py


SambaWriter — arm score → vault mutation layer.

Final stage of the OctopusTracer pipeline (ARCHITECTURE LOCKED — pow.md):

    8 MLP HEADS (arms) → SUCKER LAYER → Samba MCP → vault writes

Arm → vault action mapping:
    PRUNE     → prune-flag node  (mark high-score nodes for human review)
    GRAFT     → graft node       (structural join between complement neighbours)
    CLUSTER   → cluster node     (wikilinks between high-score neighbour pairs)
    RANK      → rank node        (priority metadata update)
    TAG       → tag node         (content-derived tag annotation)
    RESURFACE → resu

Defines: SambaWrite, SambaResult, SambaWriter, _slug, make_samba_writer, summary, __init__, process, _render_arm_node, _write, samba_dir, __repr__

---

## Semantic links

→ [[engine-vault-writer]]
→ [[engine-vault-garden]]
→ [[mcp-server-vault-hub]]
→ [[source]]
→ [[scripts-mcp-bridge]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-engine-vault-writer-md]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-vault-writer-py]]
→ [[cursor-ingest/2026-08-04-072347-engine-vault-garden-py]]
→ [[cursor-ingest/2026-08-04-072347-engine-coherence-daemon-py]]
→ [[cursor-ingest/2026-08-04-072347-source-engine-vault-garden-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
