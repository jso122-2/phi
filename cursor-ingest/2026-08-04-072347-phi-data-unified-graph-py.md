# phi / data / unified_graph.py

#source #python

> path: phi/data/unified_graph.py  
> ext: .py  

---

# phi / data / unified_graph.py


UnifiedGraph — generalised knowledge graph for the Samba GNN.

Accepts a list of SymbolNode objects (from any extractor) and builds a
NetworkX DiGraph with 7 edge types:

    wikilink    (0)   [[link]] between markdown notes
    tag_overlap (1)   shared tags / decorators
    temporal    (2)   files modified within the same time window
    semantic    (3)   cosine similarity of embeddings (added post-encode)
    import      (4)   Python/JS import edges between symbols
    co_file     (5)   symbols in the same source file
    co_repo     (6)   symbols in the same git repo

Public interface mirr

Defines: UnifiedGraph, __init__, build, _add_wikilink_edges, _add_import_edges, _add_call_edges, _add_inheritance_edges, _add_co_file_edges, _add_co_repo_edges, _add_tag_overlap_edges, _add_temporal_edges, add_semantic_edges, num_nodes, all_texts, get_ordered_neighbors, detect_changes, nearest_similarity, cache_embeddings

---

## Semantic links

→ [[graph-linker]]
→ [[graph-node]]
→ [[graph-worker]]
→ [[graph-source-extractor]]
→ [[graph-init]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-data-symbol-node-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-gnn-samba-gnn-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-topology-primitives-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-data-dataset-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-data-crawler-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
