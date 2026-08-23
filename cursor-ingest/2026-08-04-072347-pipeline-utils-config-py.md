# pipeline / utils / config.py

#source #python

> path: pipeline/utils/config.py  
> ext: .py  

---

# pipeline / utils / config.py


pipeline.utils.config — YAML + .env config loader.

Usage
-----
    from pipeline.utils.config import load_config
    cfg = load_config()                        # uses default config/config.yaml
    cfg = load_config(Path("my/config.yaml"))  # explicit path


Defines: _deep_get, Config, load_config, __init__, __getattr__, get, as_dict, __repr__

---

## Semantic links

→ [[pipeline-utils-config]]
→ [[pipeline-bridge-init]]
→ [[pipeline-fetcher-init]]
→ [[pipeline-worker-multi-source]]
→ [[pipeline-worker-init]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-pipeline-utils-config-md]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-utils-init-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-data-extractors-config-extractor-py]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-fetcher-init-md]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-vpn-init-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
