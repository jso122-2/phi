# psspps / traverser.py

#source #python

> path: psspps/traverser.py  
> ext: .py  

---

# psspps / traverser.py


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

The context window is the "mine

Defines: Hop, TraversalResult, traverse, find_doc_by_title, to_dict

---

## Semantic links

→ [[psspps-traverser]]
→ [[graph-logger]]
→ [[graph-linker]]
→ [[VAULT]]
→ [[psspps-pipeline]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-psspps-traverser-md]]
→ [[cursor-ingest/2026-08-04-072347-graph-linker-py]]
→ [[cursor-ingest/2026-08-04-072347-source-graph-linker-md]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-traverser-py]]
→ [[cursor-ingest/2026-08-04-072347-graph-ingestion-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
