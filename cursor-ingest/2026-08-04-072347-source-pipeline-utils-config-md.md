# source / pipeline-utils-config.md

#doc #md

> path: source/pipeline-utils-config.md  
> ext: .md  

---

# pipeline/utils/config

#code #module #pipeline #code

> source_path: pipeline/utils/config.py  
> package: pipeline  
> module: pipeline/utils/config  
> hub: CODE  
> created_ts:   

---

**Package:** `pipeline`  
**Module:** `pipeline/utils/config`  
**Source:** `pipeline/utils/config.py`

pipeline.utils.config — YAML + .env config loader.

Usage
-----
    from pipeline.utils.config import load_config
    cfg = load_config()                        # uses default config/config.yaml
    cfg = load_config(Path("my/config.yaml"))  # explicit path

## API

- `def _deep_get` — Nested dict access: _deep_get(cfg, 'vpn', 'timeout_s', default=30).
- `class Config` — Thin wrapper around the parsed YAML dict with attribute-style access.
- `def load_config` — Load config.yaml and .env, return a Config object.

---

## Semantic links

→ [[config]]
→ [[2025-05-11-042356-conda-commands]]
→ [[index]]
→ [[CODE]]
→ [[CODE]]

## Related notes

→ [[source/pipeline-worker-init]]
→ [[source/pipeline-fetcher-init]]
→ [[source/pipeline-worker-multi-source]]
→ [[source/pipeline-bridge-init]]
→ [[source/pipeline-sources-base]]

— import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[pipeline-bridge-init]]
→ [[pipeline-worker-init]]
→ [[pipeline-fetcher-init]]
→ [[pipeline-index]]
→ [[pipeline-sources-base]]
→ [[pipeline-worker-multi-source]]

---

## Semantic links

→ [[pipeline-utils-config]]
→ [[pipeline-bridge-init]]
→ [[pipeline-fetcher-init]]
→ [[pipeline-worker-multi-source]]
→ [[pipeline-worker-init]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-pipeline-sources-init-md]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-fetcher-init-md]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-utils-config-py]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-worker-init-md]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-vpn-init-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
