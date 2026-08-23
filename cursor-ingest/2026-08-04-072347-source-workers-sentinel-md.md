# source / workers-sentinel.md

#doc #md

> path: source/workers-sentinel.md  
> ext: .md  

---

# workers/sentinel

#code #module #workers #code

> source_path: workers/sentinel.py  
> package: workers  
> module: workers/sentinel  
> hub: CODE  
> created_ts:   

---

**Package:** `workers`  
**Module:** `workers/sentinel`  
**Source:** `workers/sentinel.py`

Sentinel — sensitive-file protection layer for the oesophagus pipeline.

Every file is screened before ingestion.  The sentinel runs three passes:

  1. Extension block-list  — hard-reject file types that should never enter
                             the vault (key files, env files, credential stores)
  2. Pattern scan          — regex scan of the first SCAN_BYTES of text files
                             for credentials, tokens, private keys, PII
  3. Path quarantine       — path component check for suspicious directory
                             names (shadow, vault, .ssh, .gnupg, etc.)

A file must pass all three gates.  Blocked files are never read beyond what
is needed for screening — they are quarantined in place and a SentinelReport
is returned explaining why.

Sensitive content found inside a file that is not block-listed is REDACTED
from the ingested text, not blocked outright.  The file enters the vault
with a [REDACTED] marker so the graph knows it exists but the secret is
never written to any .md node.

## API

- `class SentinelReport`
- `def _extension_blocked` — Return block reason string if extension is on the block-list, else ''.
- `def _path_quarantined` — Return block reason if any parent directory is on the quarantine list.
- `def _scan_content` — Scan text for sensitive patterns.
- `def screen` — Screen a single file.
- `def screen_batch` — Screen a list of paths, returning one SentinelReport per path.

---

## Semantic links

→ [[index]]
→ [[worker]]
→ [[2026-07-13-configure-the-obsidian-graph-as-the-hub-buil]]
→ [[graph]]
→ [[dev]]

## Related notes

→ [[source/workers-oesophagus]]
→ [[source/tools-ingest]]
→ [[source/engine-vault-writer]]
→ [[source/pipeline-worker-fs-organize

---

## Semantic links

→ [[workers-sentinel]]
→ [[workers-oesophagus]]
→ [[pipeline-worker-fs-organizer]]
→ [[workers-cairrn-layers]]
→ [[tools-ingest]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-workers-sentinel-py]]
→ [[cursor-ingest/2026-08-04-072347-workers-oesophagus-py]]
→ [[cursor-ingest/2026-08-04-072347-source-workers-oesophagus-md]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-oesophagus-py]]
→ [[cursor-ingest/2026-08-04-072347-source-tools-ingest-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
