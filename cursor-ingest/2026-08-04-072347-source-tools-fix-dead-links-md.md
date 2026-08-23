# source / tools-fix-dead-links.md

#doc #md

> path: source/tools-fix-dead-links.md  
> ext: .md  

---

# tools/fix_dead_links

#code #module #tools #code

> source_path: tools/fix_dead_links.py  
> package: tools  
> module: tools/fix_dead_links  
> hub: CODE  
> created_ts:   

---

**Package:** `tools`  
**Module:** `tools/fix_dead_links`  
**Source:** `tools/fix_dead_links.py`

fix_dead_links.py — prune every dead wikilink from the vault.

Strategy
--------
1. Load all .md files and build the set of valid stems (filename without .md).
2. For each file:
   a. Find every  using the same regex as graph/node.py.
   b. A link is dead if its last path component (bare stem) is not in the stems set.
   c. Remove lines whose only content is `` or ``
      variants (the auto-linker format).
   d. For inline dead links that are mixed with real content, strip just the
       token.
3. Write the cleaned file back only if changed.
4. Print a summary.

## API

- `def load_stems`
- `def is_dead`
- `def clean_file` — Returns (n_removed, dead_links_found) and writes cleaned content if changed.
- `def main`

---

## Semantic links

→ [[graph]]
→ [[graph]]
→ [[2026-07-13-configure-the-obsidian-graph-as-the-hub-buil]]
→ [[2026-07-13-042743-configure-the-obsidian-graph-as-the-hub-buil]]
→ [[logger]]

## Related notes

→ [[source/graph-worker]]
→ [[source/graph-linker]]
→ [[source/graph-node]]
→ [[source/mcp-server-tools-graph]]
→ [[source/graph-init]]

— import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[graph-worker]]
→ [[graph-init]]
→ [[mcp-server-tools-graph]]
→ [[graph-logger]]
→ [[graph-node]]
→ [[graph-linker]]

---

## Semantic links

→ [[tools-fix-dead-links]]
→ [[graph-worker]]
→ [[graph-linker]]
→ [[tools-ingest]]
→ [[engine-orphan-detector]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-tools-fix-dead-links-py]]
→ [[cursor-ingest/2026-08-04-072347-source-graph-worker-md]]
→ [[cursor-ingest/2026-08-04-072347-source-tools-index-md]]
→ [[cursor-ingest/2026-08-04-072347-source-graph-linker-md]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-worker-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
