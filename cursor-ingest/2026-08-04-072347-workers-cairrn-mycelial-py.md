# workers / cairrn / mycelial.py

#source #python

> path: workers/cairrn/mycelial.py  
> ext: .py  

---

# workers / cairrn / mycelial.py


CAIRRN Mycelial Formula Set — pure math, no state.

Implements the full metabolic substrate formula set from:
    "Rationale: Mycelial Intelligence in DAWN"
    (Keep note, 2026-07-13 → keep/2025-08-09-024311-*.md → mycelial-layer.md)

The mycelial layer treats the CAIRRN node graph as a living metabolic
substrate.  Every node carries an energy state; every edge is a conductive
channel.  Each tick the system computes demand, allocates nutrients, converts
them to energy, diffuses and transports resources, updates edge weights, and
applies growth/decay mechanics.

All functions here are **pure*

Defines: demand, nutrient_alloc, metabolise, conductance, passive_flow, active_flow, weight_update, shimmer_decay, growth_gate, autophagy_trigger, metabolite_value, absorb_metabolite, cluster_fusion_efficiency, cluster_fission_out, f_hebbian_learning, f_connection_decay, f_spore_energy_decay, f_adaptive_capacity

---

## Semantic links

→ [[workers-cairrn-mycelial]]
→ [[engine-mycelial-substrate]]
→ [[engine-mycelial]]
→ [[workers-cairrn-init]]
→ [[mycelial-layer]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-engine-mycelial-substrate-py]]
→ [[cursor-ingest/2026-08-04-072347-workers-cairrn-formulas-py]]
→ [[cursor-ingest/2026-08-04-072347-source-engine-mycelial-substrate-md]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-cairrn-mycelial-py]]
→ [[cursor-ingest/2026-08-04-072347-source-workers-index-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
