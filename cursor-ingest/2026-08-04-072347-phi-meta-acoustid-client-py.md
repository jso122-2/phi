# phi / meta / acoustid_client.py

#source #python

> path: phi/meta/acoustid_client.py  
> ext: .py  

---

# phi / meta / acoustid_client.py

phi.meta.acoustid_client — chromaprint fingerprinting + AcoustID lookup.

Wraps pyacoustid (which wraps fpcalc / libchromaprint) and the AcoustID
web API.  All network calls are synchronous — run on a background thread.

Typical flow
------------
1. fingerprint(path) → (fingerprint_str, duration_secs)
2. lookup(api_key, fingerprint, duration) → list[AcoustIDResult]
3. best_match(results, threshold=0.70) → AcoustIDResult | None


Defines: AcoustIDRecording, AcoustIDResult, fingerprint, lookup, lookup_raw, best_match, best_recording

---

## Semantic links

→ [[engine-phi-session]]
→ [[engine-cairrn-scheduler]]
→ [[engine-cairrn-tracer-daemon]]
→ [[mcp-server-tools-phi-clip]]
→ [[engine-mycelial-substrate]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-engine-phi-session-py]]
→ [[cursor-ingest/2026-08-04-072347-source-engine-phi-session-md]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-phi-session-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-graph-phi-tracer-bridge-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-app-workers-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
