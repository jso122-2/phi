# phi / gnn / euler_ssm.py

#source #python

> path: phi/gnn/euler_ssm.py  
> ext: .py  

---

# phi / gnn / euler_ssm.py


EulerSSM — Complex Euler State Space Model

Replaces the real-diagonal A matrix of SelectiveSSM with complex eigenvalues
parameterized via Euler's formula:

    A_k = r_k · e^(i·θ_k) = r_k · (cos θ_k  +  i · sin θ_k)

Where:
    r_k  ∈ (0, 1)  — contraction rate (decay toward stability)
    θ_k  ∈ ℝ       — oscillation frequency (learned)
    |A_k| = r_k < 1 — guaranteed stability (all eigenvalues inside unit circle)

The state transition becomes a rotation-then-contraction in the complex plane:

    h'_r = r · (cos θ · h_r  −  sin θ · h_i)  +  B_r · x
    h'_i = r · (sin θ · h_r  +  cos θ · 

Defines: EulerSSM, __init__, euler_rotate, forward, get_eigenvalues, eigenvalue_summary

---

## Semantic links

→ [[models-ssm]]
→ [[sims-attractors]]
→ [[workers-cairrn-constants]]
→ [[MATH]]
→ [[attractors]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-gnn-euler-pos-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-gnn-coherence-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-gnn-samba-gnn-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-gnn-samba-layer-py]]
→ [[cursor-ingest/2026-08-04-072347-sims-attractors-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
