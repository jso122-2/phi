# phi / models / base.py

#source #python

> path: phi/models/base.py  
> ext: .py  

---

# phi / models / base.py

phi.models.base — abstract base for all phi inference models.

The interface is intentionally thin: one method to check eligibility, one to
run.  Models return a plain dict that is merged into Library.annotations[path].
They never touch playback state — they are pure annotation engines.

Dropping in a new model:
    1. Subclass PhiModel, set name / version.
    2. Implement can_process() and run().
    3. Register with ModelRegistry.register(MyModel()).

The system handles threading, error isolation, and progress reporting.


Defines: PhiModel, can_process, run, batch, __repr__

---

## Semantic links

→ [[models-init]]
→ [[engine-phi-session]]
→ [[engine-phi-player]]
→ [[scripts-embed-tracks]]
→ [[mcp-server-tools-phi-dispatch]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-models-init-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-models-derivative-loaders-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-core-library-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-phi-player-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-audio-init-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
