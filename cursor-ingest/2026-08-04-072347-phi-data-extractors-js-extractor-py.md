# phi / data / extractors / js_extractor.py

#source #python

> path: phi/data/extractors/js_extractor.py  
> ext: .py  

---

# phi / data / extractors / js_extractor.py


JavaScript / TypeScript symbol extractor — regex-based (no tree-sitter dep).

Extracts:
  - Named functions:       function foo(
  - Arrow const:           const foo = (  /  const foo = async (
  - Class declarations:    class Foo  /  export class Foo
  - Export functions:      export function foo  /  export default function

JSDoc comment immediately above each match is captured as docstring.
Import statements are collected for connectivity edge detection.


Defines: JSExtractor, extract, _collect_imports, _extract_jsdoc

---

## Semantic links

→ [[graph-source-extractor]]
→ [[engine-phi-session]]
→ [[engine-coherence-gate]]
→ [[tools-ingest]]
→ [[tools-fix-dead-links]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-data-extractors-python-extractor-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-data-extractors-init-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-data-extractors-config-extractor-py]]
→ [[cursor-ingest/2026-08-04-072347-graph-source-extractor-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-data-extractors-markdown-extractor-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
