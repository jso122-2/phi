# source / scripts-train.md

#doc #md

> path: source/scripts-train.md  
> ext: .md  

---

# scripts/train

#code #module #scripts #code

> source_path: scripts/train.py  
> package: scripts  
> module: scripts/train  
> hub: CODE  
> created_ts:   

---

**Package:** `scripts`  
**Module:** `scripts/train`  
**Source:** `scripts/train.py`

SambaGNN Training Script
Supports two stages:
  1. Pretrain  — on a synthetic/public knowledge graph (no vault needed)
  2. Finetune  — adaptive scheduled training on live Obsidian vault via MCP

Usage:
    python train.py --stage pretrain
    python train.py --stage finetune --vault_url http://localhost:27123
    python train.py --stage finetune --resume checkpoints/best.pt

## API

- `def link_prediction_loss` — Binary cross-entropy over positive and negative link pairs.
- `def cluster_loss` — Prototype alignment + entropy regularization for cluster head.
- `def contrastive_retrieval_loss` — InfoNCE-style contrastive loss for retrieval head.
- `def build_edge_index` — Build (2, E) edge_index tensor from positive link pairs in a batch.
- `def train_epoch`
- `def evaluate`
- `def save_checkpoint`
- `def load_checkpoint`
- `def main`

## Internal imports

`models`, `models.coherence`

---

## Semantic links

→ [[2026-07-13-configure-the-obsidian-graph-as-the-hub-buil]]
→ [[hub-classifier]]
→ [[graph]]
→ [[2026-07-16-011935-vault-coherence-engine]]
→ [[graph]]

## Related notes

→ [[source/scripts-pretrain-loop]]
→ [[source/scripts-mcp-bridge]]
→ [[source/scripts-samba-mcp-server]]
→ [[source/mcp-server-vault-hub]]
→ [[source/engine-vault-garden]]

— import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[scripts-mcp-bridge]]
→ [[scripts-index]]
→ [[index]]
→ [[mcp-server-tools-graph]]
→ [[scripts-train-d4]]
→ [[scripts-inference]]

---

## Semantic links

→ [[scripts-train]]
→ [[scripts-pretrain-loop]]
→ [[scripts-mcp-bridge]]
→ [[scripts-samba-mcp-server]]
→ [[scripts-inference]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-scripts-train-py]]
→ [[cursor-ingest/2026-08-04-072347-source-scripts-pretrain-loop-md]]
→ [[cursor-ingest/2026-08-04-072347-source-scripts-mcp-bridge-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-vault-hub-md]]
→ [[cursor-ingest/2026-08-04-072347-scripts-pretrain-loop-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
