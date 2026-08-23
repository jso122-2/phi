# tools / cursor_ingest.py

#source #python

> path: tools/cursor_ingest.py  
> ext: .py  

---

# tools / cursor_ingest.py


Cursor file ingestion — push all .cursor/ config into the Obsidian vault graph.

Scans two source trees:
  1. <workspace>/.cursor/   — local workspace rules, hooks, mcp config
  2. ~/.cursor/skills/       — project workflow skills
  3. ~/.cursor/skills-cursor/ — cursor-specific skills
  4. ~/.cursor/rules/        — global rules

Supported file types
--------------------
  .md  / .mdc  — Markdown / MDC rules  (first # heading = title)
  .sh          — Shell scripts          (filename = title, body = content)
  .json        — JSON config            (selective: skips mcp.json credential files)



Defines: _now_ts, _slug, _should_skip, _parse_md, _parse_sh, _parse_json, _parse_file, _collect_sources, collect_docs, run, main

---

## Semantic links

→ [[tools-cursor-ingest]]
→ [[engine-vault-garden]]
→ [[graph-ingestion]]
→ [[mcp-server-tools-graph]]
→ [[tools-ingest]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-tools-cursor-ingest-md]]
→ [[cursor-ingest/2026-08-04-072347-source-tools-ingest-md]]
→ [[cursor-ingest/2026-08-04-072347-graph-ingestion-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-data-obsidian-graph-py]]
→ [[cursor-ingest/2026-08-04-072347-source-tools-keep-ingest-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
