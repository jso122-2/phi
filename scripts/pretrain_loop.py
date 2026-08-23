"""
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
    python pretrain_loop.py --no-crawl
"""
import argparse
import logging
import os
import random
import signal
import sys
import threading
import time
from typing import Dict, Optional

import numpy as np
import torch
import yaml

from phi.gnn.samba_gnn import SambaGNN
from phi.gnn.coherence import CoherenceWeightSchedule
from phi.gnn.encoder import BERTClippingEncoder, CodeBERTEncoder, DualEncoder
from phi.data.obsidian_graph import ObsidianGraph
from phi.data.unified_graph import UnifiedGraph
from phi.data.crawler import FilesystemCrawler
from phi.data.dataset import ObsidianGraphDataset
from engine.coherence_gate import AutonomousGate
from phi.utils.replay import ReplayBuffer, GraphSnapshot, prefill_buffer_synthetic, generate_synthetic_snapshot
from phi.utils.perpetual import PerpetualTrainer
from phi.utils.log import setup_logger, MetricLogger

logger = setup_logger("pretrain_loop")


# ──────────────────────────────────────────────────────────────────────────────
# Snapshot builders
# ──────────────────────────────────────────────────────────────────────────────

def _graph_to_snapshot(
    graph,  # ObsidianGraph | UnifiedGraph — both expose the same interface
    encoder,  # BERTClippingEncoder | DualEncoder
    device: torch.device,
    walk_strategy: str,
    max_neighbors: int,
    source: str = "unified",
    priority: float = 2.0,
) -> GraphSnapshot:
    """Encode any graph into a GraphSnapshot for the replay buffer."""
    texts = graph.all_texts
    with torch.no_grad():
        if hasattr(encoder, "forward_nodes") and hasattr(graph, "notes"):
            # DualEncoder path: route by language
            nodes = sorted(graph.notes.values(), key=lambda n: n.node_id)
            if nodes and hasattr(nodes[0], "language"):
                node_emb = encoder.forward_nodes(nodes, device).cpu()
            else:
                node_emb = encoder(texts, device).cpu()
        else:
            node_emb = encoder(texts, device).cpu()

    dataset = ObsidianGraphDataset(
        graph=graph,
        node_embeddings=node_emb,
        walk_strategy=walk_strategy,
        max_neighbors=max_neighbors,
    )
    batch = dataset.get_batch()

    edges = list(graph.nx_graph.edges(data=True))
    if edges:
        src = torch.tensor([e[0] for e in edges], dtype=torch.long)
        dst = torch.tensor([e[1] for e in edges], dtype=torch.long)
        edge_index = torch.stack([src, dst], dim=0)
        edge_weight = torch.tensor([e[2].get("weight", 1.0) for e in edges])
    else:
        edge_index = torch.zeros(2, 0, dtype=torch.long)
        edge_weight = torch.zeros(0)

    return GraphSnapshot(
        node_emb=batch.node_emb,
        edge_index=edge_index,
        edge_weight=edge_weight,
        neighbor_seqs=batch.neighbor_seqs,
        edge_type_ids=batch.edge_type_ids,
        neighbor_mask=batch.neighbor_mask,
        source=source,
        priority=priority,
    )


# Legacy alias kept for call sites that used the old name
def vault_to_snapshot(graph, model, device, walk_strategy, max_neighbors):
    return _graph_to_snapshot(
        graph, model.encoder, device, walk_strategy, max_neighbors,
        source="vault", priority=2.0,
    )


# ──────────────────────────────────────────────────────────────────────────────
# CrawlerWatcher — background thread for filesystem ingestion
# ──────────────────────────────────────────────────────────────────────────────

class CrawlerWatcher(threading.Thread):
    """
    Periodically re-scans the filesystem, gates new symbols, rebuilds the
    UnifiedGraph, and notifies the PerpetualTrainer of the updated snapshot.
    """

    def __init__(
        self,
        crawler: FilesystemCrawler,
        unified_graph: UnifiedGraph,
        gate: AutonomousGate,
        encoder,
        trainer,  # PerpetualTrainer
        device: torch.device,
        walk_strategy: str,
        max_neighbors: int,
        rescan_interval: float = 300.0,
    ) -> None:
        super().__init__(daemon=True, name="CrawlerWatcher")
        self.crawler = crawler
        self.unified_graph = unified_graph
        self.gate = gate
        self.encoder = encoder
        self.trainer = trainer
        self.device = device
        self.walk_strategy = walk_strategy
        self.max_neighbors = max_neighbors
        self.rescan_interval = rescan_interval
        self._stop_event = threading.Event()
        self._last_scan_ts: float = 0.0

    def run(self) -> None:
        while not self._stop_event.is_set():
            self._stop_event.wait(self.rescan_interval)
            if self._stop_event.is_set():
                break
            try:
                self._cycle()
            except Exception as exc:
                logger.warning("CrawlerWatcher cycle error: %s", exc)

    def stop(self) -> None:
        self._stop_event.set()

    def _cycle(self) -> None:
        since = self._last_scan_ts
        self._last_scan_ts = time.time()

        new_syms = self.crawler.scan_incremental(since_ts=since)
        if not new_syms:
            return

        logger.info("CrawlerWatcher: %d new/modified symbols found", len(new_syms))

        # Gate evaluation (no embeddings on incremental — use connectivity only)
        decisions = self.gate.evaluate_batch(new_syms)
        admitted = [s for s, d in zip(new_syms, decisions)
                    if d.action.value == "admit"]

        if not admitted:
            logger.info("CrawlerWatcher: all %d symbols deferred/skipped", len(new_syms))
            return

        # Add to graph and rebuild snapshot
        all_syms = list(self.unified_graph.notes.values()) + admitted
        self.unified_graph.build(all_syms)
        self.gate.update_name_index(self.unified_graph._name_index)

        if self.unified_graph.num_nodes == 0:
            return

        snap = _graph_to_snapshot(
            self.unified_graph, self.encoder, self.device,
            self.walk_strategy, self.max_neighbors,
            source="unified_incremental", priority=2.5,
        )
        self.trainer.notify_vault_change(snap)
        logger.info(
            "CrawlerWatcher: injected %d new admitted symbols → graph now %d nodes",
            len(admitted), self.unified_graph.num_nodes,
        )


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("--resume", default=None, help="Path to perpetual checkpoint")
    parser.add_argument("--gpu_fraction", type=float, default=0.30,
                        help="Fraction of wallclock time to use GPU/CPU (0–1)")
    parser.add_argument("--buffer_size", type=int, default=32,
                        help="Replay buffer capacity (snapshots)")
    parser.add_argument("--warmup_steps", type=int, default=50,
                        help="Foreground micro-steps before background thread starts")
    parser.add_argument("--no-crawl", action="store_true",
                        help="Skip filesystem crawl; use Obsidian vault only")
    args = parser.parse_args()

    with open(args.config) as f:
        cfg = yaml.safe_load(f)

    seed = cfg["training"]["seed"]
    torch.manual_seed(seed)
    np.random.seed(seed)
    random.seed(seed)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info(f"Device: {device} | GPU fraction: {args.gpu_fraction:.0%}")

    os.makedirs(cfg["training"]["checkpoint_dir"], exist_ok=True)
    os.makedirs(cfg["training"]["log_dir"], exist_ok=True)

    metric_logger = MetricLogger(os.path.join(cfg["training"]["log_dir"], "perpetual"))

    # ── Build model ────────────────────────────────────────────────────────
    enc_cfg = cfg["model"]["encoder"]
    gnn = cfg["model"]["gnn"]
    ssm = cfg["model"]["ssm"]

    model = SambaGNN(
        encoder_model=enc_cfg["model_name"],
        clip_layers=enc_cfg["clip_layers"],
        hidden_dim=gnn["hidden_dim"],
        num_layers=gnn["num_layers"],
        d_state=ssm["d_state"],
        d_conv=ssm["d_conv"],
        share_weights=gnn["share_weights"],
        dropout=gnn["dropout"],
        num_edge_types=gnn.get("num_edge_types", 7),
        num_clusters=cfg["model"]["heads"]["num_clusters"],
        max_neighbors=cfg["walk"]["max_neighbors"],
        max_length=enc_cfg["max_length"],
    ).to(device)

    # ── Build encoder (DualEncoder if code_model configured) ──────────────
    text_encoder = model.encoder  # BERTClippingEncoder already on model
    code_model_name: Optional[str] = enc_cfg.get("code_model")
    if code_model_name:
        logger.info(f"Loading CodeBERTEncoder: {code_model_name}")
        code_encoder = CodeBERTEncoder(
            model_name=code_model_name,
            clip_layers=enc_cfg.get("code_clip_layers", 2),
            output_dim=gnn["hidden_dim"],
            max_length=enc_cfg.get("code_max_length", 128),
        ).to(device)
        encoder = DualEncoder(text_encoder=text_encoder, code_encoder=code_encoder)
    else:
        encoder = text_encoder  # plain BERTClippingEncoder for all nodes

    optimizer = torch.optim.AdamW(
        [p for p in model.parameters() if p.requires_grad],
        lr=cfg["training"]["learning_rate"],
        weight_decay=cfg["training"]["weight_decay"],
    )

    # ── Coherence weight schedule ──────────────────────────────────────────
    total_steps = cfg["training"]["finetune_epochs"] * 200
    coh_schedule = CoherenceWeightSchedule(
        alpha=0.10, beta=0.05, gamma=0.08, delta=0.03,
        warmup_frac=0.15,
        ramp_frac=0.40,
        total_steps=total_steps,
    )

    start_step = 0
    if args.resume:
        ckpt = torch.load(args.resume, map_location=device)
        model.load_state_dict(ckpt["model_state_dict"])
        optimizer.load_state_dict(ckpt["optimizer_state_dict"])
        start_step = ckpt.get("step", 0)
        coh_schedule.load_state(ckpt.get("coh_schedule_step", 0))
        logger.info(f"Resumed from step {start_step}")

    # ── Replay buffer — synthetic cold start ───────────────────────────────
    buffer = ReplayBuffer(
        capacity=args.buffer_size,
        recency_decay=0.005,
        min_vault_frac=0.4,
    )
    prefill_buffer_synthetic(
        buffer,
        n_snapshots=max(8, args.buffer_size // 2),
        hidden_dim=gnn["hidden_dim"],
        max_neighbors=cfg["walk"]["max_neighbors"],
    )

    # ── Filesystem crawl + AutonomousGate (Phase 2) ───────────────────────
    unified_graph = UnifiedGraph(
        semantic_threshold=cfg["edges"]["semantic_threshold"],
        temporal_window_days=7.0,
    )
    gate = AutonomousGate(
        cfg=cfg.get("gate", {}),
        log_path=cfg.get("gate", {}).get("log_path", "logs/gate.db"),
    )
    crawler_watcher: Optional[CrawlerWatcher] = None

    if not args.no_crawl:
        crawler_cfg = cfg.get("crawler", {})
        crawler = FilesystemCrawler(crawler_cfg)

        logger.info("Starting full filesystem crawl (this may take a minute)...")
        all_symbols = crawler.scan()
        logger.info("Crawl complete: %d raw symbols found", len(all_symbols))

        decisions = gate.evaluate_batch(all_symbols)
        admitted = [s for s, d in zip(all_symbols, decisions)
                    if d.action.value == "admit"]
        logger.info(
            "Gate: %d admitted | %d deferred | %d skipped",
            sum(1 for d in decisions if d.action.value == "admit"),
            sum(1 for d in decisions if d.action.value == "defer"),
            sum(1 for d in decisions if d.action.value == "skip"),
        )

        if admitted:
            unified_graph.build(admitted)
            gate.update_name_index(unified_graph._name_index)
            logger.info(
                "UnifiedGraph: %d nodes, %d edges",
                unified_graph.num_nodes, unified_graph.nx_graph.number_of_edges(),
            )

            unified_snap = _graph_to_snapshot(
                unified_graph, encoder, device,
                walk_strategy=cfg["walk"]["strategy"],
                max_neighbors=cfg["walk"]["max_neighbors"],
                source="unified_full", priority=3.0,
            )
            buffer.add(unified_snap)
            logger.info(
                "UnifiedGraph snapshot added: %d nodes, %d edges",
                unified_snap.num_nodes, unified_snap.num_edges,
            )
    else:
        logger.info("--no-crawl: skipping filesystem ingestion")

    # ── Obsidian vault snapshot (legacy Phase 3) ───────────────────────────
    import os as _os
    vault_path = (
        _os.environ.get("SAMBA_VAULT_PATH")
        or _os.environ.get("OBSIDIAN_VAULT_PATH")
        or _os.path.expandvars(cfg["graph"]["vault_path"])
    )
    vault_path = str(_os.path.expanduser(vault_path))
    obsidian_graph = ObsidianGraph(vault_path=vault_path)
    obsidian_graph.build()

    if obsidian_graph.num_nodes > 0:
        vault_snap = _graph_to_snapshot(
            obsidian_graph, encoder, device,
            walk_strategy=cfg["walk"]["strategy"],
            max_neighbors=cfg["walk"]["max_neighbors"],
            source="vault", priority=2.0,
        )
        buffer.add(vault_snap)
        logger.info(
            "Obsidian vault snapshot added: %d nodes, %d edges",
            vault_snap.num_nodes, vault_snap.num_edges,
        )

    # ── Foreground warmup ──────────────────────────────────────────────────
    logger.info(f"Foreground warmup: {args.warmup_steps} micro-steps...")
    from phi.utils.perpetual import micro_step, EMAModel
    ema_model = EMAModel(model, decay=0.999)

    for step in range(args.warmup_steps):
        snap = buffer.sample(1)[0]
        metrics = micro_step(model, ema_model, optimizer, snap, coh_schedule, device)
        coh_schedule.step()
        if (step + 1) % 10 == 0:
            logger.info(
                f"Warmup {step+1}/{args.warmup_steps} | "
                f"loss={metrics['loss']:.4f}"
            )
        metric_logger.log_dict(metrics, step=start_step + step)

    # ── Start perpetual background trainer ────────────────────────────────
    def on_step_end(step: int, metrics: Dict):
        metric_logger.log_dict(metrics, step=step)

    trainer = PerpetualTrainer(
        model=model,
        optimizer=optimizer,
        buffer=buffer,
        coh_schedule=coh_schedule,
        device=device,
        gpu_fraction=args.gpu_fraction,
        ema_decay=0.999,
        checkpoint_every_steps=200,
        checkpoint_dir=cfg["training"]["checkpoint_dir"],
        on_step_end=on_step_end,
    )
    trainer.ema_model = ema_model
    trainer._step = start_step + args.warmup_steps
    trainer.start()

    # ── Start CrawlerWatcher (if crawl enabled) ────────────────────────────
    if not args.no_crawl:
        rescan_interval = cfg.get("crawler", {}).get("rescan_interval_seconds", 300)
        crawler_watcher = CrawlerWatcher(
            crawler=crawler,
            unified_graph=unified_graph,
            gate=gate,
            encoder=encoder,
            trainer=trainer,
            device=device,
            walk_strategy=cfg["walk"]["strategy"],
            max_neighbors=cfg["walk"]["max_neighbors"],
            rescan_interval=rescan_interval,
        )
        crawler_watcher._last_scan_ts = time.time()  # avoid re-processing initial scan
        crawler_watcher.start()
        logger.info(
            "CrawlerWatcher started — rescanning ~/  every %ds", rescan_interval
        )

    logger.info("Perpetual training running. Press Ctrl-C to stop cleanly.")

    # ── Graceful shutdown ──────────────────────────────────────────────────
    def _shutdown(sig, frame):
        logger.info("Shutdown signal received...")
        if crawler_watcher:
            crawler_watcher.stop()
        trainer.stop()
        trainer.join(timeout=10.0)
        metric_logger.close()
        logger.info("Clean shutdown complete.")
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    # ── Main loop: Obsidian vault watcher ──────────────────────────────────
    poll_interval = cfg["graph"]["sync_interval_seconds"]
    while True:
        time.sleep(poll_interval)
        try:
            new_notes, modified = obsidian_graph.detect_changes()
            if new_notes or modified:
                logger.info(
                    "Obsidian vault changed: %d new, %d modified",
                    len(new_notes), len(modified),
                )
                obsidian_graph.build()
                vault_snap = _graph_to_snapshot(
                    obsidian_graph, encoder, device,
                    walk_strategy=cfg["walk"]["strategy"],
                    max_neighbors=cfg["walk"]["max_neighbors"],
                    source="vault", priority=2.0,
                )
                trainer.notify_vault_change(vault_snap)
        except Exception as e:
            logger.warning(f"Vault poll error: {e}")

        if not trainer.is_alive():
            logger.error("PerpetualTrainer thread died unexpectedly — restarting")
            trainer = PerpetualTrainer(
                model=model, optimizer=optimizer, buffer=buffer,
                coh_schedule=coh_schedule, device=device,
                gpu_fraction=args.gpu_fraction,
                checkpoint_dir=cfg["training"]["checkpoint_dir"],
            )
            trainer.start()
            if crawler_watcher:
                crawler_watcher.trainer = trainer


if __name__ == "__main__":
    main()
