# source / tools-ingest.md

#doc #md

> path: source/tools-ingest.md  
> ext: .md  

---

# tools/ingest

#code #module #tools #code

> source_path: tools/ingest.py  
> package: tools  
> module: tools/ingest  
> hub: CODE  
> created_ts:   

---

**Package:** `tools`  
**Module:** `tools/ingest`  
**Source:** `tools/ingest.py`

General-purpose folder ingestion CLI.

Ingests any folder of .txt, .md, or .json files into the Obsidian vault
graph using MiniLM semantic similarity for link discovery.

Supported file types
--------------------
  .md   — Markdown: first `# Heading` becomes title, rest is body
  .txt  — Plain text: filename becomes title, content is body
  .json — Structured: expects {title?, text?, body?, content?, tags?[]}
          or Google Keep format (textContent, labels, etc.)

Output
------
  <vault>/<output-dir-name>/
      <timestamp>-<slug>.md        one file per ingested document
      index.md                     hub node listing all docs
      ingest-manifest.json         hub counts for graph_sync_manifest

Usage
-----
    python tools/ingest.py <source-folder> [--out-dir NAME]
                            [--threshold F] [--top-k N]
                            [--dry-run] [--no-wipe] [--skip-cross-link]

Arguments
---------
  source-folder   Path to the folder containing documents to ingest
  --out-dir       Name of the output subdirectory in the vault
                  (default: folder name of source)
  --threshold     Cosine similarity cutoff (default 0.30)
  --top-k         Max vault links per doc (default 5)
  --dry-run       Print what would happen, write nothing
  --no-wipe       Don't delete the output dir before re-running
  --skip-cross-link  Skip cross-linking docs within the batch
  --tags          Comma-separated tags to add to all docs
                  (default: "imported")
  --recursive     Recurse into subdirectories (default: False)

Examples
--------
    # Ingest a folder of markdown notes
    python tools/ingest.py ~/notes/ --out-dir notes

    # Ingest text files from Downloads with custom threshold
    python t

---

## Semantic links

→ [[tools-ingest]]
→ [[graph-ingestion]]
→ [[tools-keep-ingest]]
→ [[workers-oesophagus]]
→ [[tools-cursor-ingest]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-tools-ingest-py]]
→ [[cursor-ingest/2026-08-04-072347-source-tools-keep-ingest-md]]
→ [[cursor-ingest/2026-08-04-072347-graph-ingestion-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-data-obsidian-graph-py]]
→ [[cursor-ingest/2026-08-04-072347-source-graph-ingestion-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
