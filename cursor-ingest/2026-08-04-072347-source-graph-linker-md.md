# source / graph-linker.md

#doc #md

> path: source/graph-linker.md  
> ext: .md  

---

# graph/linker

#code #module #graph #code

> source_path: graph/linker.py  
> package: graph  
> module: graph/linker  
> hub: CODE  
> created_ts:   

---

**Package:** `graph`  
**Module:** `graph/linker`  
**Source:** `graph/linker.py`

Vault auto-linker — uses PSSPPS semantic scoring to discover and inject
wikilinks between related nodes.

Strategy
--------
For each node, build a TF-IDF query from its title + clean text, score every
other node, and inject links for any that exceed the similarity threshold.
Links are appended in a clearly-marked section so they can be audited or
removed without touching the human-authored content above.

## API

- `def score_against_corpus` — Return (score, node) pairs for every node in corpus except target.
- `def suggest_links` — Return stems of nodes that should be linked from target (new links only).
- `def inject_links` — Append or extend the Auto-linked section of a node file.
- `def link_all` — Auto-link every node in the vault.  Returns a list of (stem, new_links) pairs

## Internal imports

`graph.node`, `psspps.retriever`, `psspps.scorer`

---

## Semantic links

→ [[graph]]
→ [[graph]]
→ [[2026-07-13-configure-the-obsidian-graph-as-the-hub-buil]]
→ [[2026-07-13-042743-configure-the-obsidian-graph-as-the-hub-buil]]
→ [[logger]]

## Related notes

→ [[source/graph-init]]
→ [[source/graph-logger]]
→ [[source/graph-node]]
→ [[source/graph-worker]]
→ [[source/mcp-server-tools-graph]]

— import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[graph-logger]]
→ [[graph-init]]
→ [[graph-node]]
→ [[graph-index]]
→ [[mcp-server-tools-graph]]
→ [[graph-worker]]

---

## Semantic links

→ [[graph-linker]]
→ [[graph-logger]]
→ [[graph-init]]
→ [[graph-worker]]
→ [[graph]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-graph-linker-py]]
→ [[cursor-ingest/2026-08-04-072347-graph-md]]
→ [[cursor-ingest/2026-08-04-072347-source-graph-worker-md]]
→ [[cursor-ingest/2026-08-04-072347-graph-init-py]]
→ [[cursor-ingest/2026-08-04-072347-source-graph-node-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
