# phi / data / crawler.py

#source #python

> path: phi/data/crawler.py  
> ext: .py  

---

# phi / data / crawler.py


FilesystemCrawler — walk ~/  and dispatch to per-language extractors.

Produces a flat list of SymbolNode objects for UnifiedGraph.build().

Usage:
    crawler = FilesystemCrawler(cfg["crawler"])
    symbols = crawler.scan()                        # full scan
    new_syms = crawler.scan_incremental(since_ts)   # only changed files


Defines: FilesystemCrawler, __init__, scan, scan_incremental, _walk, _extract, _find_repo

---

## Semantic links

→ [[engine-coherence-gate]]
→ [[graph-source-extractor]]
→ [[graph-worker]]
→ [[graph-linker]]
→ [[graph-node]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-data-symbol-node-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-data-extractors-init-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-data-unified-graph-py]]
→ [[cursor-ingest/2026-08-04-072347-engine-coherence-gate-py]]
→ [[cursor-ingest/2026-08-04-072347-source-graph-source-extractor-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
