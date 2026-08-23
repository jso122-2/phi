# phi / gnn / euler_pos.py

#source #python

> path: phi/gnn/euler_pos.py  
> ext: .py  

---

# phi / gnn / euler_pos.py


Euler Walk Position Encoding
Applies Euler rotations e^(i·k·ω) to neighbor embeddings before they enter
the EulerSSM, encoding their position in the neighborhood walk sequence.

This is the graph analogue of Rotary Position Embedding (RoPE):
    - In LLMs: token at position k gets rotated by e^(i·k·ω_d) per dimension pair
    - Here:    neighbor at walk position k gets rotated by e^(i·k·ω_d)

The key property of Euler rotations is that the dot product between two
embeddings depends only on their *relative* walk distance:
    ⟨f(x_j, j), f(x_k, k)⟩ = ⟨x_j, x_k⟩_rotated by (j-k)

So the SSM nat

Defines: EulerWalkPositionEncoder, __init__, forward, encode_single, visualise_rotation

---

## Semantic links

→ [[engine-phi-session]]
→ [[workers-cairrn-constants]]
→ [[workers-cairrn-z-space]]
→ [[CODE]]
→ [[CODE]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-gnn-euler-ssm-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-gnn-samba-layer-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-gnn-samba-gnn-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-models-dragon-curve-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-utils-walk-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
