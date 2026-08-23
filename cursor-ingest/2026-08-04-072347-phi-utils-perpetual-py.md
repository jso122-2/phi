# phi / utils / perpetual.py

#source #python

> path: phi/utils/perpetual.py  
> ext: .py  

---

# phi / utils / perpetual.py


PerpetualTrainer — Continuous GNN-SSM Background Training Loop

Runs training indefinitely in a background thread, interleaving:
  1. Task losses  (link prediction, retrieval, clustering)
  2. Coherence energy  (all four negative-e terms, annealed by schedule)
  3. EMA target distillation  (soft self-consistency via exponential moving average)
  4. Replay mixing  (old vault + synthetic snapshots prevent catastrophic forgetting)

The trainer never "completes" — it sleeps between micro-steps to respect
a configurable CPU/GPU fraction, and wakes on vault-change signals.

EMA target network (θ_em

Defines: EMAModel, get_ema_targets, ema_distillation_loss, micro_step, PerpetualTrainer, __init__, update, __call__, __init__, notify_vault_change, stop, run, _save_checkpoint

---

## Semantic links

→ [[scripts-pretrain-loop]]
→ [[2025-08-12-045215-notes-for-thinkerbell-preso]]
→ [[2025-09-29-054631-2025-09-29t15-46-32-036-10-00]]
→ [[scripts-train]]
→ [[2025-08-30-032217-2025-08-30t13-22-19-162-10-00]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-scripts-pretrain-loop-py]]
→ [[cursor-ingest/2026-08-04-072347-source-scripts-pretrain-loop-md]]
→ [[cursor-ingest/2026-08-04-072347-phi-utils-scheduler-py]]
→ [[cursor-ingest/2026-08-04-072347-scripts-train-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-utils-replay-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
