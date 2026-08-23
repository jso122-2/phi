# source / scripts-train-d4.md

#doc #md

> path: source/scripts-train-d4.md  
> ext: .md  

---

# scripts/train_d4

#code #module #scripts #code

> source_path: scripts/train_d4.py  
> package: scripts  
> module: scripts/train_d4  
> hub: CODE  
> created_ts:   

---

**Package:** `scripts`  
**Module:** `scripts/train_d4`  
**Source:** `scripts/train_d4.py`

scripts/train_d4.py — D4 XGBoost baseline training script.

Pulls all track metadata from ~/.phi/meta.db, runs GeminiClipper to produce
dragon curve features, fits D4XGBoostModel, and saves to ~/.phi/d4_xgb.joblib.

The phi app auto-loads the checkpoint on next startup.

Usage:
    python scripts/train_d4.py
    python scripts/train_d4.py --batch-size 32 --depth 8 --window 16
    python scripts/train_d4.py --skip-existing     # resume interrupted run
    python scripts/train_d4.py --dry-run           # annotate only, don't fit

## API

- `def _load_tracks` — Return all (path, meta) pairs from the tracks table.
- `def _load_existing_annotations` — Bulk-load existing annotation dicts from the annotations table.
- `def _save_annotations` — Bulk upsert annotation dicts to the annotations table.
- `def annotate` — Run MetaClipper over all items, using cached annotations where possible.
- `def fit_model` — Fit D4XGBoostModel and save checkpoint to ~/.phi/d4_xgb.joblib.
- `def main`

---

## Semantic links

→ [[2026-04-25-210442-2026-04-26t07-06-10-849-10-00]]
→ [[git-log]]
→ [[cursor-skills]]
→ [[2024-12-23-072054-october-1-tips-gpt-4-23-12-24]]
→ [[git-log]]

## Related notes

→ [[source/engine-phi-session]]
→ [[source/scripts-pretrain-loop]]
→ [[source/scripts-embed-tracks]]
→ [[source/engine-vault-garden]]
→ [[source/scripts-train]]

— import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[scripts-index]]
→ [[scripts-train]]
→ [[scripts-embed-tracks]]
→ [[index]]
→ [[scripts-rescrape-short]]
→ [[scripts-pretrain-loop]]

---

## Semantic links

→ [[scripts-train-d4]]
→ [[scripts-train]]
→ [[scripts-pretrain-loop]]
→ [[pipeline-fetcher-init]]
→ [[scripts-embed-tracks]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-scripts-train-d4-py]]
→ [[cursor-ingest/2026-08-04-072347-source-scripts-train-md]]
→ [[cursor-ingest/2026-08-04-072347-source-scripts-pretrain-loop-md]]
→ [[cursor-ingest/2026-08-04-072347-source-scripts-embed-tracks-md]]
→ [[cursor-ingest/2026-08-04-072347-source-scripts-rescrape-short-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
