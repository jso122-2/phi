# engine / phi_session.py

#source #python

> path: engine/phi_session.py  
> ext: .py  

---

# engine / phi_session.py


PhiTracerSession — wires PhiGraph to TracerDaemon.

Data flow:

    PhiLibrary  ──scan──►  Track[]
                                │
    MetadataEncoder / CLAP.npy  │
                                ▼
    CLAPProjection(512→256) ──► snap.H  (N, 256)
                                │
    TagJaccard adjacency ─────► snap.A  (N, N)
                                │
                     run_once(A=snap.A, X=snap.H)
                                │
                          SSMCore.tick(X)         ← SSM transforms snap.H → H_ssm
                                │
                          compute_

Defines: PhiTracerSession, make_phi_session, __init__, build, snapshot, tick, refresh_and_tick, clip, harmonic_index, bridge, daemon_tick, n_tracks, n_tracers, __repr__

---

## Semantic links

→ [[engine-phi-session]]
→ [[engine-tracer-daemon]]
→ [[mcp-server-tools-phi-clip]]
→ [[engine-cairrn-tracer-daemon]]
→ [[engine-cairrn-scheduler]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-engine-phi-session-md]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-phi-session-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-graph-phi-tracer-bridge-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-graph-phi-graph-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-models-init-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
