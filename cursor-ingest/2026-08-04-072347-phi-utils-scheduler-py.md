# phi / utils / scheduler.py

#source #python

> path: phi/utils/scheduler.py  
> ext: .py  

---

# phi / utils / scheduler.py


Adaptive Topology Scheduler
Manages learning rate and curriculum based on two signals:
  1. Standard training loss plateau (ReduceLROnPlateau-style)
  2. Vault topology changes (new notes / links → boost LR to adapt fast)


Defines: AdaptiveTopologyScheduler, __init__, step_optimizer, epoch_end, hop_radius, _set_lr, state_dict, load_state_dict

---

## Semantic links

→ [[engine-cairrn-scheduler]]
→ [[scripts-pretrain-loop]]
→ [[scripts-train]]
→ [[hub-classifier]]
→ [[engine-cursor-tracer]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-scripts-train-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-utils-perpetual-py]]
→ [[cursor-ingest/2026-08-04-072347-source-scripts-train-md]]
→ [[cursor-ingest/2026-08-04-072347-scripts-pretrain-loop-py]]
→ [[cursor-ingest/2026-08-04-072347-engine-cairrn-scheduler-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
