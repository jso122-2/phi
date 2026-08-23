# phi / data / extractors / __init__.py

#source #python

> path: phi/data/extractors/__init__.py  
> ext: .py  

---

# phi / data / extractors / __init__.py


Symbol extractors — one per language/file-type.

Each extractor accepts a file path and returns a list of SymbolNode objects.
The FilesystemCrawler dispatches to the right extractor based on file suffix.

Public surface:
    from data.extractors import (
        PythonExtractor,
        JSExtractor,
        MarkdownExtractor,
        ConfigExtractor,
    )

---

## Semantic links

→ [[graph-source-extractor]]
→ [[tools-ingest]]
→ [[models-init]]
→ [[psspps-retriever]]
→ [[engine-phi-session]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-data-extractors-markdown-extractor-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-data-extractors-python-extractor-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-data-extractors-js-extractor-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-data-crawler-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-data-extractors-config-extractor-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
