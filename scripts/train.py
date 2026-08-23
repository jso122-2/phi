"""
SambaGNN Training Script
Supports two stages:
  1. Pretrain  — on a synthetic/public knowledge graph (no vault needed)
  2. Finetune  — adaptive scheduled training on live Obsidian vault via MCP

Usage:
    python train.py --stage pretrain
    python train.py --stage finetune --vault_url http://localhost:27123
    python train.py --stage finetune --resume checkpoints/best.pt
"""
import argparse
import os
import random
import time
import logging

from dotenv import load_dotenv
load_dotenv()

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import yaml

from phi.gnn.samba_gnn import SambaGNN
from phi.gnn.coherence import CoherenceWeightSchedule
from phi.data.obsidian_graph import ObsidianGraph
from phi.data.dataset import ObsidianGraphDataset
from phi.utils.scheduler import AdaptiveTopologyScheduler
from phi.utils.log import setup_logger, MetricLogger

logger = setup_logger("train")


# ──────────────────────────────────────────────────────────────────────────────
# Losses
# ──────────────────────────────────────────────────────────────────────────────

def link_prediction_loss(
    model: SambaGNN,
    h: torch.Tensor,
    batch,
) -> torch.Tensor:
    """Binary cross-entropy over positive and negative link pairs."""
    pos_logits = model.predict_links(h, batch.pos_src, batch.pos_dst)
    neg_logits = model.predict_links(h, batch.neg_src, batch.neg_dst)
    pos_loss = F.binary_cross_entropy_with_logits(pos_logits, torch.ones_like(pos_logits))
    neg_loss = F.binary_cross_entropy_with_logits(neg_logits, torch.zeros_like(neg_logits))
    return (pos_loss + neg_loss) / 2


def cluster_loss(model: SambaGNN, h: torch.Tensor) -> torch.Tensor:
    """Prototype alignment + entropy regularization for cluster head."""
    assignments = model.cluster(h)
    proto_loss = model.cluster_head.prototype_loss(h, assignments)
    # entropy regularization: push toward confident assignments
    entropy = -(assignments * torch.log(assignments + 1e-8)).sum(dim=-1).mean()
    return proto_loss + 0.1 * entropy


def contrastive_retrieval_loss(
    model: SambaGNN,
    h: torch.Tensor,
    pos_src: torch.LongTensor,
    pos_dst: torch.LongTensor,
    temperature: float = 0.07,
) -> torch.Tensor:
    """
    InfoNCE-style contrastive loss for retrieval head.
    Pulls linked note embeddings together, pushes random pairs apart.
    """
    if len(pos_src) == 0:
        return torch.tensor(0.0, device=h.device)
    q = model.retrieval_head(h[pos_src])     # (M, proj_dim) — normalized
    k = model.retrieval_head(h[pos_dst])     # (M, proj_dim) — normalized
    logits = (q @ k.T) / temperature         # (M, M)
    labels = torch.arange(len(pos_src), device=h.device)
    return F.cross_entropy(logits, labels)


# ──────────────────────────────────────────────────────────────────────────────
# Training loop
# ──────────────────────────────────────────────────────────────────────────────

def build_edge_index(batch, device: torch.device):
    """Build (2, E) edge_index tensor from positive link pairs in a batch."""
    if batch.pos_src.numel() == 0:
        return torch.zeros(2, 0, dtype=torch.long, device=device), None
    edge_index = torch.stack([batch.pos_src, batch.pos_dst], dim=0).to(device)
    return edge_index, None


def train_epoch(
    model: SambaGNN,
    dataset: ObsidianGraphDataset,
    optimizer: torch.optim.Optimizer,
    scheduler: AdaptiveTopologyScheduler,
    coh_schedule: CoherenceWeightSchedule,
    device: torch.device,
    hop_radius: int,
) -> dict:
    model.train()
    batch = dataset.get_batch(hop_radius=hop_radius).to(device)

    # update coherence weights from schedule
    coh_weights = coh_schedule.weights()
    model.set_coherence_weights(coh_weights)
    coh_schedule.step()

    optimizer.zero_grad()

    edge_index, edge_weight = build_edge_index(batch, device)

    # GNN forward with coherence
    h, coh_info = model(
        batch.node_emb,
        batch.neighbor_seqs,
        batch.edge_type_ids,
        batch.neighbor_mask,
        edge_index=edge_index,
        edge_weight=edge_weight,
        return_coherence=True,
    )

    # Task losses
    lp_loss  = link_prediction_loss(model, h, batch)
    cl_loss  = cluster_loss(model, h)
    ret_loss = contrastive_retrieval_loss(model, h, batch.pos_src, batch.pos_dst)

    # Coherence energy (annealed)
    E_coh = coh_info["E_coh"] if coh_info else torch.tensor(0.0, device=device)

    loss = lp_loss + 0.3 * cl_loss + 0.5 * ret_loss + E_coh

    assert not torch.isnan(loss), "Loss is NaN at step — check inputs"

    loss.backward()
    nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
    optimizer.step()
    scheduler.step_optimizer()

    metrics = {
        "train/loss": loss.item(),
        "train/lp_loss": lp_loss.item(),
        "train/cl_loss": cl_loss.item(),
        "train/ret_loss": ret_loss.item(),
    }
    if coh_info:
        metrics.update(coh_info["terms"])
    return metrics


@torch.no_grad()
def evaluate(
    model: SambaGNN,
    dataset: ObsidianGraphDataset,
    device: torch.device,
) -> dict:
    model.eval()
    batch = dataset.get_batch().to(device)
    h, _ = model(batch.node_emb, batch.neighbor_seqs, batch.edge_type_ids, batch.neighbor_mask)

    lp_loss = link_prediction_loss(model, h, batch)
    pos_logits = model.predict_links(h, batch.pos_src, batch.pos_dst)
    accuracy = (pos_logits > 0).float().mean().item()

    return {"val_loss": lp_loss.item(), "link_accuracy": accuracy}


# ──────────────────────────────────────────────────────────────────────────────
# Checkpoint
# ──────────────────────────────────────────────────────────────────────────────

def save_checkpoint(model, optimizer, scheduler, epoch, loss, path):
    torch.save({
        "epoch": epoch,
        "model_state_dict": model.state_dict(),
        "optimizer_state_dict": optimizer.state_dict(),
        "scheduler_state_dict": scheduler.state_dict(),
        "loss": loss,
    }, path)
    logger.info(f"Checkpoint saved → {path}")


def load_checkpoint(path, model, optimizer=None, scheduler=None):
    ckpt = torch.load(path, map_location="cpu")
    model.load_state_dict(ckpt["model_state_dict"])
    if optimizer:
        optimizer.load_state_dict(ckpt["optimizer_state_dict"])
    if scheduler:
        scheduler.load_state_dict(ckpt["scheduler_state_dict"])
    logger.info(f"Loaded checkpoint from epoch {ckpt['epoch']} (loss={ckpt['loss']:.4f})")
    return ckpt["epoch"]


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("--stage", choices=["pretrain", "finetune"], default="finetune")
    parser.add_argument("--resume", default=None, help="Path to checkpoint to resume from")
    parser.add_argument("--vault_url", default=None, help="Override Obsidian API URL")
    args = parser.parse_args()

    with open(args.config) as f:
        cfg = yaml.safe_load(f)

    # Reproducibility
    seed = cfg["training"]["seed"]
    torch.manual_seed(seed)
    np.random.seed(seed)
    random.seed(seed)
    torch.backends.cudnn.benchmark = True

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info(f"Device: {device}")

    os.makedirs(cfg["training"]["checkpoint_dir"], exist_ok=True)
    os.makedirs(cfg["training"]["log_dir"], exist_ok=True)
    metric_logger = MetricLogger(cfg["training"]["log_dir"])

    # ── Build graph ────────────────────────────────────────────────────────
    vault_path = (
        os.environ.get("OBSIDIAN_VAULT_PATH")
        or cfg.get("graph", {}).get("vault_path", "")
    )
    graph = ObsidianGraph(
        vault_path=vault_path or None,
        semantic_threshold=cfg["edges"]["semantic_threshold"],
    )
    graph.build()

    # ── Build model ────────────────────────────────────────────────────────
    enc_cfg = cfg["model"]["encoder"]
    gnn_cfg = cfg["model"]["gnn"]
    ssm_cfg = cfg["model"]["ssm"]
    head_cfg = cfg["model"]["heads"]

    model = SambaGNN(
        encoder_model=enc_cfg["model_name"],
        clip_layers=enc_cfg["clip_layers"],
        hidden_dim=gnn_cfg["hidden_dim"],
        num_layers=gnn_cfg["num_layers"],
        d_state=ssm_cfg["d_state"],
        d_conv=ssm_cfg["d_conv"],
        share_weights=gnn_cfg["share_weights"],
        dropout=gnn_cfg["dropout"],
        num_clusters=head_cfg["num_clusters"],
        max_neighbors=cfg["walk"]["max_neighbors"],
        max_length=enc_cfg["max_length"],
    ).to(device)

    report = model.parameter_report()
    logger.info("Parameter budget:")
    for k, v in report.items():
        logger.info(f"  {k:30s} {v:>10,}")
    assert report["total_trainable"] <= 1_650_000, (
        f"Model exceeds 1.65M param budget: {report['total_trainable']:,}"
    )

    # ── Encode all nodes once (frozen encoder — cache embeddings) ──────────
    logger.info("Encoding all notes with BERT clippings encoder...")
    model.encoder.eval()
    texts = graph.all_texts
    with torch.no_grad():
        node_emb = model.encoder(texts, device).cpu()
    logger.info(f"Encoded {len(texts)} notes → shape {node_emb.shape}")

    # Add semantic edges using computed embeddings
    added = graph.add_semantic_edges(node_emb.numpy(), threshold=cfg["edges"]["semantic_threshold"])
    logger.info(f"Added {added} semantic edges")

    # ── Dataset ────────────────────────────────────────────────────────────
    train_cfg = cfg["training"]
    curr_cfg = train_cfg["curriculum"]
    dataset = ObsidianGraphDataset(
        graph=graph,
        node_embeddings=node_emb,
        walk_strategy=cfg["walk"]["strategy"],
        max_neighbors=cfg["walk"]["max_neighbors"],
        hop_radius=curr_cfg["start_hop"],
    )

    # ── Optimizer + Scheduler ──────────────────────────────────────────────
    optimizer = torch.optim.AdamW(
        [p for p in model.parameters() if p.requires_grad],
        lr=train_cfg["learning_rate"],
        weight_decay=train_cfg["weight_decay"],
    )
    sched_cfg = train_cfg["scheduler"]
    scheduler = AdaptiveTopologyScheduler(
        optimizer=optimizer,
        base_lr=train_cfg["learning_rate"],
        min_lr=sched_cfg["min_lr"],
        patience=sched_cfg["patience"],
        factor=sched_cfg["factor"],
        warmup_steps=sched_cfg["warmup_steps"],
        vault_change_boost=sched_cfg["vault_change_lr_boost"],
        start_hop=curr_cfg["start_hop"],
        max_hop=curr_cfg["max_hop"],
        total_finetune_epochs=train_cfg["finetune_epochs"],
    )

    epochs = (
        train_cfg["pretrain_epochs"] if args.stage == "pretrain"
        else train_cfg["finetune_epochs"]
    )
    checkpoint_dir = train_cfg["checkpoint_dir"].rstrip("/")

    # total_steps = one call to coh_schedule.step() per epoch
    coh_schedule = CoherenceWeightSchedule(
        alpha=0.10, beta=0.05, gamma=0.08, delta=0.03,
        warmup_frac=0.15,   # coherence off for first 15% of epochs
        ramp_frac=0.40,     # fully active from epoch 40%
        total_steps=epochs,
    )

    start_epoch = 0
    if args.resume:
        start_epoch = load_checkpoint(args.resume, model, optimizer, scheduler)

    # ── Training loop ──────────────────────────────────────────────────────
    best_loss = float("inf")
    for epoch in range(start_epoch, start_epoch + epochs):
        hop = scheduler.hop_radius if curr_cfg["enabled"] else curr_cfg["max_hop"]

        # check vault for changes (finetune only)
        topology_changed = False
        if args.stage == "finetune" and epoch > 0:
            new_notes, modified = graph.detect_changes()
            if new_notes or modified:
                logger.info(f"Vault changed: {len(new_notes)} new, {len(modified)} modified")
                graph.build()
                with torch.no_grad():
                    node_emb = model.encoder(graph.all_texts, device).cpu()
                dataset = ObsidianGraphDataset(
                    graph=graph, node_embeddings=node_emb,
                    walk_strategy=cfg["walk"]["strategy"],
                    max_neighbors=cfg["walk"]["max_neighbors"],
                )
                topology_changed = True

        train_metrics = train_epoch(model, dataset, optimizer, scheduler, coh_schedule, device, hop)
        val_metrics = evaluate(model, dataset, device)

        sched_info = scheduler.epoch_end(val_metrics["val_loss"], topology_changed)

        log_dict = {
            **train_metrics,
            "val/loss": val_metrics["val_loss"],
            "val/link_accuracy": val_metrics["link_accuracy"],
            "train/lr": sched_info["lr"],
            "train/hop_radius": sched_info["hop_radius"],
        }
        metric_logger.log_dict(log_dict, step=epoch)

        coh_str = f"E_coh={train_metrics.get('coh/total', 0.0):.4f} | α={train_metrics.get('coh/alpha', 0.0):.2f}"
        logger.info(
            f"Epoch {epoch+1}/{start_epoch+epochs} | "
            f"loss={train_metrics['train/loss']:.4f} | val={val_metrics['val_loss']:.4f} | "
            f"link_acc={val_metrics['link_accuracy']:.3f} | "
            f"lr={sched_info['lr']:.2e} | hop={sched_info['hop_radius']} | {coh_str}"
        )

        if val_metrics["val_loss"] < best_loss:
            best_loss = val_metrics["val_loss"]
            save_checkpoint(model, optimizer, scheduler, epoch, best_loss,
                            f"{checkpoint_dir}/best.pt")
            logger.info(f"  New best val_loss: {best_loss:.4f}")

        if (epoch + 1) % train_cfg["checkpoint_every"] == 0:
            save_checkpoint(model, optimizer, scheduler, epoch, train_metrics["train/loss"],
                            f"{checkpoint_dir}/epoch_{epoch+1}.pt")

    metric_logger.close()
    logger.info(f"Training complete. Best val loss: {best_loss:.4f}")


if __name__ == "__main__":
    main()
