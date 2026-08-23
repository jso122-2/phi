# source / engine-main.md

#doc #md

> path: source/engine-main.md  
> ext: .md  

---

# engine/__main__

#code #module #engine #code

> source_path: engine/__main__.py  
> package: engine  
> module: engine/__main__  
> hub: CODE  
> created_ts:   

---

**Package:** `engine`  
**Module:** `engine/__main__`  
**Source:** `engine/__main__.py`

Allows the engine package to be run as a module from any working directory:

    python -m engine [--once] [--dry-run] [--interval N] ...

Equivalent to running engine.coherence_daemon directly, but with the project
root automatically resolved so `inference`, `models`, and `data` are importable
regardless of cwd.

## Internal imports

`engine.coherence_daemon`

---

## Semantic links

→ [[environment]]
→ [[agent-context]]
→ [[agent-context]]
→ [[2025-02-20-075321-docker-and-celery-commands]]
→ [[2025-05-11-042356-conda-commands]]

## Related notes

→ [[source/pipeline-worker-init]]
→ [[source/engine-init]]
→ [[source/pipeline-fetcher-init]]
→ [[source/mcp-server-main]]
→ [[source/pipeline-bridge-init]]

— import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[index]]
→ [[engine-index]]
→ [[engine-health-log]]
→ [[pipeline-bridge-init]]
→ [[cognitive-init]]
→ [[engine-init]]

---

## Semantic links

→ [[engine-main]]
→ [[pipeline-bridge-init]]
→ [[engine-index]]
→ [[pipeline-fetcher-init]]
→ [[pipeline-worker-init]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-engine-main-py]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-sources-init-md]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-worker-init-md]]
→ [[cursor-ingest/2026-08-04-072347-source-engine-cairrn-scheduler-md]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-fetcher-init-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
