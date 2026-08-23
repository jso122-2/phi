# source / psspps-traverser.md

#doc #md

> path: source/psspps-traverser.md  
> ext: .md  

---

# psspps/traverser

#code #module #psspps #code

> source_path: psspps/traverser.py  
> package: psspps  
> module: psspps/traverser  
> hub: CODE  
> created_ts:   

---

**Package:** `psspps`  
**Module:** `psspps/traverser`  
**Source:** `psspps/traverser.py`

Minecart graph traversal — semantic rail-riding through the vault.

Metaphor
--------
The vault is a mine.  Each document is a chamber connected by rails whose
gauge is cosine similarity.  The minecart:

  1. Starts at a seed (query string or vault note title).
  2. At each hop embeds its *current context window* (all text accumulated
     so far), then finds the nearest unvisited chamber.
  3. Loads the new chamber's content into the context window.
  4. Stops when it runs out of track (max_hops) or its context budget is
     exhausted (context_budget chars).

The context window is the "minecart" — it carries meaning as it travels,
so later hops are biased toward documents relevant to the *accumulated
journey*, not just the starting point.

Public surface
--------------
    traverse(seed, docs, embeddings, *, max_hops, context_budget, top_k)
    -> TraversalResult

## API

- `class Hop`
- `class TraversalResult`
- `def traverse` — Ride the semantic rail from `seed` through vault documents.
- `def find_doc_by_title`

## Internal imports

`psspps.embedder`

---

## Semantic links

→ [[2026-07-13-configure-the-obsidian-graph-as-the-hub-buil]]
→ [[graph]]
→ [[graph]]
→ [[sessions]]
→ [[sessions]]

## Related notes

→ [[source/graph-linker]]
→ [[source/psspps-init]]
→ [[source/graph-logger]]
→ [[source/psspps-pipeline]]
→ [[source/graph-ingestion]]

— import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[graph-logger]]
→ [[psspps-retriever]]
→ [[psspps-index]]
→ [[mcp-server-tools-graph]]
→ [[psspps-pipeline]]
→ [[graph-init]]

---

## Semantic links

→ [[psspps-traverser]]
→ [[psspps-pipeline]]
→ [[graph-logger]]
→ [[mcp-server-tools-graph]]
→ [[psspps-retriever]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-psspps-traverser-py]]
→ [[cursor-ingest/2026-08-04-072347-source-graph-linker-md]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-traverser-py]]
→ [[cursor-ingest/2026-08-04-072347-source-graph-node-md]]
→ [[cursor-ingest/2026-08-04-072347-mcp-server-tools-graph-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
