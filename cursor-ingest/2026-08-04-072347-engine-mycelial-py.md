# engine / mycelial.py

#source #python

> path: engine/mycelial.py  
> ext: .py  

---

# engine / mycelial.py


MycelialNetwork — CAIRRN-aware soft edge activation for the Obsidian graph.

Biological model (from "Rationale: Mycelial Intelligence in DAWN"):
  - Notes are nodes (root tips / fungal junction points)
  - Samba GNN semantic scores are resting edge conductances
  - CAIRRN hub pipeline modulates activation along hyphae
  - harmonic_propagate diffuses activation N steps across the ring
  - Edges below threshold are dormant; above are lit (anastomosed)
  - C-layer: each hub's memory_decay applies every tick → hyphal dormancy

CAIRRN integration constants (from CAIRRN SKILL):
  κ = 0.15   harmoni

Defines: HyphalEdge, CAIRRNRun, SporeResult, CAIRRNPipeline, MycelialNetwork, conductance, is_active, to_dict, to_dict, to_dict, __init__, tick, step, set_step, run, __init__, spore, trace_hyphae, surface_anastomoses, propagate, decay_all, activation_map, network_stats, apply_anastomoses, apply_all_anastomoses, _diffuse_step, _vault_log_dir, _append_event_log, _write_state_snapshot, _fmt_spore_log, _fmt_decay_log, _fmt_growth_log, _save_state, _load_state

---

## Semantic links

→ [[engine-mycelial]]
→ [[engine-mycelial-substrate]]
→ [[2026-07-13-102400-temporal-sharding-index-cairrn-aware-ana-chi-hosted]]
→ [[workers-cairrn-mycelial]]
→ [[engine-cairrn-scheduler]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-engine-mycelial-md]]
→ [[cursor-ingest/2026-08-04-072347-workers-cairrn-mycelial-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-graph-phi-graph-gnn-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-gnn-octopus-tracer-py]]
→ [[cursor-ingest/2026-08-04-072347-engine-mycelial-substrate-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
