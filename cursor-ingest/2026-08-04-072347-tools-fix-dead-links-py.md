# tools / fix_dead_links.py

#source #python

> path: tools/fix_dead_links.py  
> ext: .py  

---

# tools / fix_dead_links.py


fix_dead_links.py — prune every dead wikilink from the vault.

Strategy
--------
1. Load all .md files and build the set of valid stems (filename without .md).
2. For each file:
   a. Find every [[wikilink]] using the same regex as graph/node.py.
   b. A link is dead if its last path component (bare stem) is not in the stems set.
   c. Remove lines whose only content is `→ [[dead-link]]` or `→ [[dead-link]]`
      variants (the auto-linker format).
   d. For inline dead links that are mixed with real content, strip just the
      [[dead-link]] token.
3. Write the cleaned file back only if cha

Defines: load_stems, is_dead, clean_file, main

---

## Semantic links

→ [[tools-fix-dead-links]]
→ [[graph-worker]]
→ [[graph-node]]
→ [[graph-linker]]
→ [[graph-init]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-tools-fix-dead-links-md]]
→ [[cursor-ingest/2026-08-04-072347-source-graph-linker-md]]
→ [[cursor-ingest/2026-08-04-072347-graph-linker-py]]
→ [[cursor-ingest/2026-08-04-072347-source-graph-worker-md]]
→ [[cursor-ingest/2026-08-04-072347-graph-node-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
