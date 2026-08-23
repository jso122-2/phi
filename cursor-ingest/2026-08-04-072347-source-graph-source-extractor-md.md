# source / graph-source-extractor.md

#doc #md

> path: source/graph-source-extractor.md  
> ext: .md  

---

# graph/source_extractor

#code #module #graph #code

> source_path: graph/source_extractor.py  
> package: graph  
> module: graph/source_extractor  
> hub: CODE  
> created_ts:   

---

**Package:** `graph`  
**Module:** `graph/source_extractor`  
**Source:** `graph/source_extractor.py`

source_extractor.py — parse Python source files into IngestedDoc objects.

Uses Python's ast module to extract:
  - Module docstring (becomes the node body)
  - Top-level class and function names + their docstrings
  - Import graph (informs wikilink suggestions)
  - Package / module metadata (tags, hub assignment)

Produces one IngestedDoc per .py file, ready to pass to IngestionPipeline.

## API

- `def _slug`
- `def _module_docstring`
- `def _top_level_items` — Return (kind, name, docstring) for every top-level class / function.
- `def _imports` — Return all locally-scoped module names (e.g. 'graph.node', 'sims.harmonic').
- `def extract_module` — Parse a single .py file into an IngestedDoc.
- `class SourceScanResult`
- `def scan_source` — Scan source packages and return IngestedDocs.

## Internal imports

`graph.ingestion`, `graph.node`

---

## Semantic links

→ [[graph]]
→ [[graph]]
→ [[2026-07-13-configure-the-obsidian-graph-as-the-hub-buil]]
→ [[logger]]
→ [[2026-07-13-042743-configure-the-obsidian-graph-as-the-hub-buil]]

## Related notes

→ [[source/graph-ingestion]]
→ [[source/tools-ingest]]
→ [[source/graph-init]]
→ [[source/graph-node]]
→ [[source/graph-linker]]

— import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[graph-logger]]
→ [[graph-index]]
→ [[graph-init]]
→ [[graph-node]]
→ [[mcp-server-tools-graph]]
→ [[graph-worker]]

---

## Semantic links

→ [[graph-source-extractor]]
→ [[graph-ingestion]]
→ [[graph-node]]
→ [[tools-ingest]]
→ [[graph-linker]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-graph-source-extractor-py]]
→ [[cursor-ingest/2026-08-04-072347-source-graph-ingestion-md]]
→ [[cursor-ingest/2026-08-04-072347-source-graph-index-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-graph-md]]
→ [[cursor-ingest/2026-08-04-072347-source-tools-ingest-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
