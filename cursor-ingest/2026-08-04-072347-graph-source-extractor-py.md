# graph / source_extractor.py

#source #python

> path: graph/source_extractor.py  
> ext: .py  

---

# graph / source_extractor.py


source_extractor.py — parse Python source files into IngestedDoc objects.

Uses Python's ast module to extract:
  - Module docstring (becomes the node body)
  - Top-level class and function names + their docstrings
  - Import graph (informs wikilink suggestions)
  - Package / module metadata (tags, hub assignment)

Produces one IngestedDoc per .py file, ready to pass to IngestionPipeline.


Defines: _slug, _module_docstring, _top_level_items, _imports, _sanitize_wikilinks, extract_module, SourceScanResult, scan_source, summary

---

## Semantic links

→ [[graph-source-extractor]]
→ [[graph-ingestion]]
→ [[tools-ingest]]
→ [[tools-keep-ingest]]
→ [[graph-linker]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-graph-source-extractor-md]]
→ [[cursor-ingest/2026-08-04-072347-source-graph-ingestion-md]]
→ [[cursor-ingest/2026-08-04-072347-graph-ingestion-py]]
→ [[cursor-ingest/2026-08-04-072347-tools-ingest-py]]
→ [[cursor-ingest/2026-08-04-072347-source-tools-ingest-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
