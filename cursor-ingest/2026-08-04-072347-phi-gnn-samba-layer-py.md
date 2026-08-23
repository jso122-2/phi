# phi / gnn / samba_layer.py

#source #python

> path: phi/gnn/samba_layer.py  
> ext: .py  

---

# phi / gnn / samba_layer.py


Samba SSM Layer for Graph Message Passing
Implements Euler SSM dynamics as the aggregation operator over an ordered
sequence of neighbor embeddings.

Key insight: instead of permutation-invariant mean/sum pooling, we order the
neighborhood and run an EulerSSM through it — giving the layer oscillatory
memory of traversal, parameterized via Euler's formula e^(iθ).

"Roving weights" = the EulerSSM instance is shared across all GNN layers,
so the same Euler dynamics rove the entire graph depth.

Walk position encoding via EulerWalkPositionEncoder encodes each neighbor's
walk position as a Euler p

Defines: SelectiveSSM, SambaSSMLayer, __init__, forward, __init__, forward

---

## Semantic links

→ [[scripts-samba-mcp-server]]
→ [[2026-07-17T01-33-09Z-CLAPProjection and PhiGraph — DAWN bridge layer]]
→ [[scripts-inference]]
→ [[graph-init]]
→ [[engine-mycelial]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-gnn-samba-gnn-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-utils-walk-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-data-dataset-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-data-unified-graph-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-gnn-euler-pos-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
