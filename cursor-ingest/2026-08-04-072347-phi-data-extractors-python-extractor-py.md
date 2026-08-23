# phi / data / extractors / python_extractor.py

#source #python

> path: phi/data/extractors/python_extractor.py  
> ext: .py  

---

# phi / data / extractors / python_extractor.py


Python symbol extractor — uses stdlib ast.

One SymbolNode per top-level function, async function, class, and per-method
inside classes. Module-level imports are attached to every symbol in the file
(so the gate can check connectivity via import names).


Defines: PythonExtractor, extract, _from_function, _from_class, _body_snippet, _collect_imports, _collect_calls, _collect_bases, _collect_decorators, _is_method

---

## Semantic links

→ [[graph-source-extractor]]
→ [[engine-phi-session]]
→ [[mcp-server-tools-phi-dispatch]]
→ [[source]]
→ [[engine-coherence-gate]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-data-extractors-init-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-data-extractors-js-extractor-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-data-extractors-config-extractor-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-data-extractors-markdown-extractor-py]]
→ [[cursor-ingest/2026-08-04-072347-graph-source-extractor-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
