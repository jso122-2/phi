# phi / data / extractors / markdown_extractor.py

#source #python

> path: phi/data/extractors/markdown_extractor.py  
> ext: .py  

---

# phi / data / extractors / markdown_extractor.py


Markdown extractor — refactored from ObsidianGraph._fetch_notes().

One SymbolNode per .md file. Preserves all NoteNode semantics:
  - title extracted from # heading or filename
  - wikilinks → outlinks
  - #tags → tags
  - timestamps from filename pattern or mtime


Defines: MarkdownExtractor, extract, _extract_frontmatter, _extract_title, _extract_body, _extract_timestamps

---

## Semantic links

→ [[tools-ingest]]
→ [[graph-source-extractor]]
→ [[psspps-retriever]]
→ [[graph-node]]
→ [[graph-ingestion]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-data-extractors-init-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-data-extractors-txt-extractor-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-data-obsidian-graph-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-data-symbol-node-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-data-extractors-js-extractor-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
