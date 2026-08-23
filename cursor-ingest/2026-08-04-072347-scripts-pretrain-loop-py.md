# scripts / pretrain_loop.py

#source #python

> path: scripts/pretrain_loop.py  
> ext: .py  

---

# scripts / pretrain_loop.py


Perpetual Pretraining Entry Point
Starts the GNN-SSM in a never-ending training loop that:

  Phase 0 — Cold start (if no checkpoint):
      Fill ReplayBuffer with synthetic Barabási-Albert graphs
      Run foreground training for `warmup_steps` to initialize weights

  Phase 1 — Perpetual loop (background thread):
      PerpetualTrainer runs micro_step continuously
      Coherence weights anneal from 0 → full via CoherenceWeightSchedule
      EMA target network stabilises representations between vault changes

  Phase 2 — Full filesystem ingestion (CrawlerWatcher thread):
      FilesystemCra

Defines: _graph_to_snapshot, vault_to_snapshot, CrawlerWatcher, main, __init__, run, stop, _cycle, on_step_end, _shutdown

---

## Semantic links

→ [[scripts-pretrain-loop]]
→ [[scripts-train]]
→ [[engine-coherence-daemon]]
→ [[engine-hot-loader]]
→ [[scripts-train-d4]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-scripts-pretrain-loop-md]]
→ [[cursor-ingest/2026-08-04-072347-phi-utils-perpetual-py]]
→ [[cursor-ingest/2026-08-04-072347-scripts-train-py]]
→ [[cursor-ingest/2026-08-04-072347-source-scripts-train-md]]
→ [[cursor-ingest/2026-08-04-072347-phi-utils-replay-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
