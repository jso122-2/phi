# phi / gnn / coherence.py

#source #python

> path: phi/gnn/coherence.py  
> ext: .py  

---

# phi / gnn / coherence.py


Coherence Layer — Negative Energy Formulas + Euler Characteristic
Implements a suite of negative-energy regularizers that schedule themselves
across training, enforcing structural consistency through the GNN-SSM stack.

The total coherence energy is a sum of five terms:

    E_coh(h, L, dA, h_layers, G) =
        -α · J(h)               [negentropy: rewards structured, non-Gaussian representations]
      + β · h^T L h             [Laplacian smoothness: penalises incoherent neighbor signals]
      + γ · Φ(dA)              [Lyapunov stability: keeps Euler SSM dynamics contractive]
      + δ · Ω

Defines: negentropy_loss, laplacian_smoothness_loss, ssm_lyapunov_loss, euler_characteristic_loss, layer_coherence_loss, CoherenceWeightSchedule, CoherenceLayer, __init__, step, weights, load_state, __init__, set_weights, forward

---

## Semantic links

→ [[engine-coherence-daemon]]
→ [[engine-gate]]
→ [[MATH]]
→ [[workers-cairrn-layers]]
→ [[engine-cairrn-scheduler]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-utils-perpetual-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-gnn-euler-ssm-py]]
→ [[cursor-ingest/2026-08-04-072347-scripts-pretrain-loop-py]]
→ [[cursor-ingest/2026-08-04-072347-engine-gate-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-gate-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
