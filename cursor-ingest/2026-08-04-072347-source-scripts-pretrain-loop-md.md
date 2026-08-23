# source / scripts-pretrain-loop.md

#doc #md

> path: source/scripts-pretrain-loop.md  
> ext: .md  

---

# scripts/pretrain_loop

#code #module #scripts #code

> source_path: scripts/pretrain_loop.py  
> package: scripts  
> module: scripts/pretrain_loop  
> hub: CODE  
> created_ts:   

---

**Package:** `scripts`  
**Module:** `scripts/pretrain_loop`  
**Source:** `scripts/pretrain_loop.py`

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
      FilesystemCrawler walks ~/ and extracts SymbolNodes from every .py,
      .js, .ts, .md, and config file found on disk.
      AutonomousGate filters symbols before they enter the UnifiedGraph:
        ADMIT  → added to the live graph immediately
        DEFER  → re-evaluated next cycle (connectivity may improve)
        SKIP   → discarded permanently
      New UnifiedGraph snapshot is injected into the replay buffer
      with elevated priority, same mechanism as the existing vault watcher.

  Phase 3 — Obsidian vault watcher (legacy, kept for MCP coherence tools):
      Checks the configured vault_path for new/modified markdown files
      and re-injects them through the gate into the unified graph.

The main thread stays alive monitoring both watchers and flushing metrics.
Ctrl-C cleanly stops all threads and saves a final checkpoint.

Usage:
    # Cold start, build from scratch:
    python pretrain_loop.py --config config/config.yaml

    # Resume from a perpetual checkpoint:
    python pretrain_loop.py --resume checkpoints/perpetual_step_001000.pt

    # Skip full filesystem scan (vault-only mode):

---

## Semantic links

→ [[scripts-pretrain-loop]]
→ [[scripts-train]]
→ [[scripts-train-d4]]
→ [[engine-hot-loader]]
→ [[scripts-run]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-scripts-pretrain-loop-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-utils-perpetual-py]]
→ [[cursor-ingest/2026-08-04-072347-source-scripts-train-md]]
→ [[cursor-ingest/2026-08-04-072347-scripts-train-py]]
→ [[cursor-ingest/2026-08-04-072347-source-scripts-train-d4-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
