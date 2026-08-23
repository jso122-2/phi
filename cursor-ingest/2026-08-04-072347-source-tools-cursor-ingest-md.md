# source / tools-cursor-ingest.md

#doc #md

> path: source/tools-cursor-ingest.md  
> ext: .md  

---

# tools/cursor_ingest

#code #module #tools #code

> source_path: tools/cursor_ingest.py  
> package: tools  
> module: tools/cursor_ingest  
> hub: CODE  
> created_ts:   

---

**Package:** `tools`  
**Module:** `tools/cursor_ingest`  
**Source:** `tools/cursor_ingest.py`

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

Output
------
  <vault>/cursor-ingest/
      <timestamp>-<slug>.md        one file per Cursor config node
      index.md                     hub index listing all nodes
      ingest-manifest.json         for graph_sync_manifest

After running, call in Cursor:
  /graph-sync-manifest cursor-ingest/ingest-manifest.json
Then:
  samba_refresh (Samba GNN MCP tool)

Usage
-----
    python tools/cursor_ingest.py [--dry-run] [--no-wipe] [--threshold F] [--top-k N]

## API

- `def _now_ts`
- `def _slug`
- `def _should_skip`
- `def _parse_md`
- `def _parse_sh`
- `def _parse_json`
- `def _parse_file`
- `def _collect_sources` — Return list of (path, source_label) for all Cursor source trees.
- `def collect_docs`
- `def run`
- `def main`

## Internal imports

`graph.ingestion`, `graph.node`

---

## Semantic links

→ [[index]]
→ [[2026-07-16-011935-audit-full-system-health-audit]]
→ [[2026-07-16-011935-vault-coherence-engine]]
→ [[2026-07-16-011935-vault-hub-remote-bmod-maximum-prescription]]
→ [[2026-07-16-011935-cursor-cli-configuration]]

## Related notes

→ [[source/graph-ingestion]]
→ [[source/tools-ingest]]
→ [[sour

---

## Semantic links

→ [[tools-cursor-ingest]]
→ [[engine-cursor-tracer]]
→ [[tools-ingest]]
→ [[tools-keep-ingest]]
→ [[pipeline-fetcher-init]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-engine-cursor-tracer-md]]
→ [[cursor-ingest/2026-08-04-072347-tools-cursor-ingest-py]]
→ [[cursor-ingest/2026-08-04-072347-source-tools-keep-ingest-md]]
→ [[cursor-ingest/2026-08-04-072347-source-tools-index-md]]
→ [[cursor-ingest/2026-08-04-072347-source-tools-ingest-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
