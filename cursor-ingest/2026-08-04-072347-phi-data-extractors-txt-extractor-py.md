# phi / data / extractors / txt_extractor.py

#source #python

> path: phi/data/extractors/txt_extractor.py  
> ext: .py  

---

# phi / data / extractors / txt_extractor.py


TxtExtractor — ingest plain-text files into the unified graph.

Handles three common patterns found in the vault:
  1. Structured key-value  →  lines of the form  "key: value"
                              extracted as tags for edge connectivity
  2. Hash/state files      →  lines of hex or base64 content
                              content-fingerprinted; hash prefix stored as tag
  3. Plain prose / logs    →  treated as prose notes (kind="document")

One SymbolNode per file.  Empty files are skipped.

Design notes:
  - .txt files in the Obsidian vault often carry CAIRRN hub state, agent
  

Defines: TxtExtractor, extract

---

## Semantic links

→ [[tools-ingest]]
→ [[graph-source-extractor]]
→ [[psspps-traverser]]
→ [[engine-phi-session]]
→ [[psspps-retriever]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-tools-ingest-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-data-extractors-markdown-extractor-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-data-obsidian-graph-py]]
→ [[cursor-ingest/2026-08-04-072347-graph-ingestion-py]]
→ [[cursor-ingest/2026-08-04-072347-graph-source-extractor-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
