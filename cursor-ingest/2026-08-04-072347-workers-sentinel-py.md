# workers / sentinel.py

#source #python

> path: workers/sentinel.py  
> ext: .py  

---

# workers / sentinel.py


Sentinel — sensitive-file protection layer for the oesophagus pipeline.

Every file is screened before ingestion.  The sentinel runs three passes:

  1. Extension block-list  — hard-reject file types that should never enter
                             the vault (key files, env files, credential stores)
  2. Pattern scan          — regex scan of the first SCAN_BYTES of text files
                             for credentials, tokens, private keys, PII
  3. Path quarantine       — path component check for suspicious directory
                             names (shadow, vault, .ssh, .gnupg, etc.

Defines: SentinelReport, _extension_blocked, _path_quarantined, _scan_content, screen, screen_batch, __str__, _replace

---

## Semantic links

→ [[workers-sentinel]]
→ [[workers-oesophagus]]
→ [[pipeline-worker-fs-organizer]]
→ [[engine-vault-writer]]
→ [[source]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-workers-sentinel-md]]
→ [[cursor-ingest/2026-08-04-072347-workers-oesophagus-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-oesophagus-py]]
→ [[cursor-ingest/2026-08-04-072347-source-workers-oesophagus-md]]
→ [[cursor-ingest/2026-08-04-072347-source-tools-ingest-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
