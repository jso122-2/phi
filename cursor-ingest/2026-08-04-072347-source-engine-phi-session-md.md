# source / engine-phi-session.md

#doc #md

> path: source/engine-phi-session.md  
> ext: .md  

---

# engine/phi_session

#code #module #engine #code

> source_path: engine/phi_session.py  
> package: engine  
> module: engine/phi_session  
> hub: CODE  
> created_ts:   

---

**Package:** `engine`  
**Module:** `engine/phi_session`  
**Source:** `engine/phi_session.py`

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
                          compute_R(A, H, tau)    ← regression pipeline
                                │
                          OctopusArms.forward(R)  ← 8 MLP arms
                                │
                     ◄──── TracerSummary ──────►  CAIRRNBridge → HarmonicIndex

Snapshot lifecycle:
    - `build()` rescans the library and recomputes H, A.
      Cheap to call infrequently; expensive for 372-track library (~0.5s).
    - `tick()` reuses the current snapshot and does one daemon tick.
      Call in a loop (2Hz or slower — SSM is stateful).
    - `refresh_and_tick()` rebuilds then ticks; call when library changes.

TracerDaemon is constructed with:
    d               = 256   (matches CLAPProjection D_OUT)
    max_tracers     = 8
    tick_gate_interval = 4
    coherence_tau   = 10.0
    vault_root      = None  (no vault writes unless explicitly set)

Usage (one-shot):

    session = make_phi_session()
    session.build()
    summary = session.tick()

Usage (loop):

    session = make_phi_session(vault_root=Path("vault"))
    session.build()
    for _ in range(100):
        summary = session.tick()
        print(summary.arm_sprout,

---

## Semantic links

→ [[engine-phi-session]]
→ [[engine-tracer-daemon]]
→ [[mcp-server-tools-phi-clip]]
→ [[engine-init]]
→ [[scripts-train-d4]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-engine-phi-session-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-models-init-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-graph-phi-tracer-bridge-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-meta-track-helpers-py]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-phi-dispatch-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
