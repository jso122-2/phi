# phi / gnn / samba_gnn.py

#source #python

> path: phi/gnn/samba_gnn.py  
> ext: .py  

---

# phi / gnn / samba_gnn.py


SambaGNN — Full model orchestrating Obsidian knowledge graph.

Architecture overview:
    [Note text] → BERTClippingEncoder (frozen) → proj → (N, 256)
                                                          ↓
                                  EulerWalkPositionEncoder (e^ikω rotations, 0 params)
                                                          ↓
                                  SambaSSMLayer × 3  (shared EulerSSM weights)
                                      EulerSSM: r·e^iθ eigenvalues, oscillatory memory
                                                          ↓
               

Defines: SambaGNN, __init__, encode_nodes, forward, predict_links, retrieve, cluster, set_coherence_weights, euler_eigenvalue_report, parameter_report, count

---

## Semantic links

→ [[scripts-samba-mcp-server]]
→ [[README]]
→ [[2026-07-17T01-33-09Z-CLAPProjection and PhiGraph — DAWN bridge layer]]
→ [[engine-mycelial]]
→ [[scripts-inference]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-gnn-encoder-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-gnn-samba-layer-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-data-unified-graph-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-models-bert-encoder-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-data-dataset-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
