# phi / metadata / extractor.py

#source #python

> path: phi/metadata/extractor.py  
> ext: .py  

---

# phi / metadata / extractor.py

phi.metadata.extractor — librosa audio analysis → AudioFeatures.

Single public entry point:

    features = extract(path)           # Path → AudioFeatures
    features = extract_or_zero(path)   # never raises; zeroed on failure

librosa is loaded lazily so the module can be imported even if librosa has
not been installed yet — ImportError is raised only at call time.


Defines: extract, extract_or_zero

---

## Semantic links

→ [[pipeline-sources-soundcloud]]
→ [[scripts-embed-tracks]]
→ [[pipeline-sources-internet-archive]]
→ [[graph-source-extractor]]
→ [[tools-enrich-c7]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-watch-librosa-worker-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-init-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-discovery-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-meta-batch-extractor-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-metadata-node-builder-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
