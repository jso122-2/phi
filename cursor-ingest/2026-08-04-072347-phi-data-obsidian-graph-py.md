# phi / data / obsidian_graph.py

#source #python

> path: phi/data/obsidian_graph.py  
> ext: .py  

---

# phi / data / obsidian_graph.py


Local Graph Builder
Reads .md files directly from the vault path on disk.
No REST API, no plugins, no network required.


Defines: NoteNode, ObsidianGraph, encoding_text, content_hash, __init__, build, _fetch_notes, _add_wikilink_edges, _add_tag_overlap_edges, _add_temporal_edges, add_semantic_edges, detect_changes, _extract_title, _extract_body, _extract_timestamps, _extract_tags, _extract_wikilinks, get_ordered_neighbors, num_nodes, all_texts, _build_mock_graph

---

## Semantic links

→ [[graph-node]]
→ [[graph-ingestion]]
→ [[mcp-server-tools-graph]]
→ [[graph-init]]
→ [[engine-vault-garden]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-graph-node-py]]
→ [[cursor-ingest/2026-08-04-072347-graph-md]]
→ [[cursor-ingest/2026-08-04-072347-source-graph-node-md]]
→ [[cursor-ingest/2026-08-04-072347-source-tools-ingest-md]]
→ [[cursor-ingest/2026-08-04-072347-graph-ingestion-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
