"""
CoherenceDaemon — main orchestration loop for the vault coherence engine.

Each cycle:
    1. orch.refresh()          — re-encode all notes in the vault
    2. topo.build()            — recompute topology primitives (V, E, T, χ, β₀, β₁)
    3. HealthLog.append()      — persist the topology snapshot
    4. OrphanDetector.scan()   — find weakly-clustered notes
    5. VaultWriter.append_links() for each orphan's suggestions
    6. BridgeFactory.scan()    — find isolated cluster pairs
    7. VaultWriter.create_bridge_note() for each bridge spec
    8. MycelialNetwork.decay_all() — every decay_interval_cycles cycles (C-layer)
    9. sleep(interval_seconds)

Topology is driven through TopologicalGraph (topology.topo_graph), which
decomposes the nx.DiGraph into Vertex / Edge / Triangle primitives and
computes the full suite of topological invariants (χ, β₀, β₁).  The
CoherenceLayer in models/coherence.py uses the current χ value from this
graph as its Euler-characteristic target each cycle.

CLI:
    python -m engine.coherence_daemon [options]

    --checkpoint PATH   Path to model checkpoint (auto-detected if omitted)
    --config PATH       Path to config.yaml
    --interval N        Seconds between cycles (default: 300)
    --dry-run           Log actions without writing to the vault
    --once              Run one cycle and exit (ignores --interval)
    --orphan-threshold          Cluster score below which a note is an orphan (default: 0.15)
    --min-bridges               Min inter-cluster wikilinks before bridging (default: 1)
    --top-k-links               Link suggestions per orphan (default: 5)
    --log-level                 Logging level (default: INFO)
    --no-mycelial               Disable the mycelial decay + growth layer
    --mycelial-decay-interval   Apply hyphal decay every N cycles (default 12 ≈ 1 hour)
    --mycelial-write-threshold  Min anastomosis_strength to write a link (default 0.60)
    --mycelial-apply-top-n      Top-active notes to grow links from per pulse (default 5)
"""
import argparse
import logging
import os
import sys
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger("coherence_daemon")


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _graph_snapshot(orch) -> dict:
    """
    Extract full topology metrics from the orchestrator's TopologicalGraph.

    Delegates to TopologicalGraph.snapshot() which returns the complete set of
    invariants (V, E, T, χ, β₀, β₁) plus per-type edge counts — all computed
    from the Vertex / Edge / Triangle primitive layer, not raw NetworkX calls.
    """
    topo = orch.topo
    topo.build()
    snap = topo.snapshot()

    inv = topo.invariant
    logger.debug(
        "Topology: V=%d  E=%d  T=%d  χ=%.1f  β₀=%d  β₁=%d",
        inv.V, inv.E, inv.T, inv.chi, inv.beta_0, inv.beta_1,
    )
    return snap


# ──────────────────────────────────────────────────────────────────────────────
# Daemon
# ──────────────────────────────────────────────────────────────────────────────

class CoherenceDaemon:
    """
    Runs the full coherence maintenance loop against a loaded SambaOrchestrator.

    Args:
        orchestrator:            Loaded SambaOrchestrator.
        dry_run:                 If True, nothing is written to the vault.
        interval_seconds:        Pause between cycles. Ignored when run_once=True.
        orphan_threshold:        Max cluster score to flag a note as orphan.
        min_bridges:             Inter-cluster link floor before bridging is triggered.
        top_k_links:             Suggestions per orphan.
        vault_path:              Override vault root (reads config by default).
        mycelial_enabled:        Enable the mycelial decay layer (default True).
        mycelial_decay_interval: Apply hyphal decay every N cycles (default 12 ≈ 1 hour).
    """

    def __init__(
        self,
        orchestrator,
        dry_run: bool = False,
        interval_seconds: int = 300,
        orphan_threshold: float = 0.15,
        min_bridges: int = 1,
        top_k_links: int = 5,
        vault_path: Optional[Path] = None,
        mycelial_enabled: bool = True,
        mycelial_decay_interval: int = 12,
        mycelial_write_threshold: float = 0.60,
        mycelial_apply_top_n: int = 5,
    ) -> None:
        from engine.vault_writer import VaultWriter
        from engine.orphan_detector import OrphanDetector
        from engine.bridge_factory import BridgeFactory
        from engine.health_log import HealthLog

        self.orch = orchestrator
        self.dry_run = dry_run
        self.interval = interval_seconds

        self.writer = VaultWriter(vault_path=vault_path, dry_run=dry_run)
        self.detector = OrphanDetector(orchestrator, threshold=orphan_threshold)
        self.factory = BridgeFactory(orchestrator, min_bridges=min_bridges)
        self.health_log = HealthLog()
        self.top_k_links = top_k_links

        self._cycle_count: int = 0
        self._mycelial_enabled = mycelial_enabled
        self._mycelial_decay_interval = mycelial_decay_interval
        self._mycelial_write_threshold = mycelial_write_threshold
        self._mycelial_apply_top_n = mycelial_apply_top_n
        self._mycelial: Optional[object] = None   # lazy-init on first decay tick

        if mycelial_enabled:
            try:
                from engine.mycelial import MycelialNetwork
                self._mycelial = MycelialNetwork(orchestrator)
                logger.info(
                    "MycelialNetwork online — decay every %d cycles (~%ds)",
                    mycelial_decay_interval,
                    mycelial_decay_interval * interval_seconds,
                )
            except Exception as e:
                logger.warning("MycelialNetwork failed to initialise: %s — mycelial layer disabled", e)

    def run_once(self) -> dict:
        """
        Execute one full coherence cycle.

        Returns:
            Summary dict with cycle metrics (chi, orphan_count, links_written,
            bridges_created) suitable for logging or MCP reporting.
        """
        logger.info("=== Coherence cycle start ===")

        # 1. Refresh
        logger.info("Refreshing vault embeddings…")
        self.orch.refresh()

        # 2. Topology snapshot (via TopologicalGraph primitives)
        snapshot = _graph_snapshot(self.orch)
        inv = self.orch.topo.invariant
        logger.info(
            "Vault: %d notes, %d edges, %d triangles  |  χ=%.1f  β₀=%d  β₁=%d",
            inv.V, inv.E, inv.T, inv.chi, inv.beta_0, inv.beta_1,
        )

        # Bind the current Euler characteristic to the CoherenceLayer target
        # so the model's topological regularizer tracks the live graph geometry.
        if hasattr(self.orch.model, "coherence"):
            self.orch.model.coherence.euler_chi_target = inv.chi

        # 3. Detect orphans
        orphans = self.detector.scan(top_k_links=self.top_k_links)
        snapshot["orphan_count"] = len(orphans)

        # 4. Patch orphan links
        links_written = 0
        for orphan in orphans:
            if orphan.suggestions:
                n = self.writer.append_links(orphan.path, orphan.suggestions)
                links_written += n
        snapshot["links_written"] = links_written
        logger.info("Wrote %d link(s) across %d orphan note(s)", links_written, len(orphans))

        # 5. Bridge isolated clusters
        bridge_specs = self.factory.scan()
        bridges_created = 0
        for spec in bridge_specs:
            self.writer.create_bridge_note(
                title=spec.title,
                cluster_a_note=spec.cluster_a_note,
                cluster_b_note=spec.cluster_b_note,
                body=spec.body,
            )
            bridges_created += 1
        snapshot["bridges_created"] = bridges_created
        logger.info("Created %d bridge note(s)", bridges_created)

        # 6. Mycelial pulse — decay + growth fire together every N cycles (C-layer)
        self._cycle_count += 1
        mycelial_summary: Optional[dict] = None
        if self._mycelial is not None and (self._cycle_count % self._mycelial_decay_interval == 0):
            # 6a. Decay — dormancy tick: edges fade by their hub's memory_decay
            try:
                decay_result = self._mycelial.decay_all()
                logger.info(
                    "Mycelial decay tick %d: %d active hyphae, %d went dormant",
                    self._cycle_count,
                    decay_result["active_after_decay"],
                    decay_result["went_dormant"],
                )
            except Exception as e:
                logger.warning("Mycelial decay failed: %s", e)
                decay_result = {}

            # 6b. Growth — anastomosis write for top-N hot nodes (dry_run mirrors daemon flag)
            growth_result: dict = {}
            try:
                growth_result = self._mycelial.apply_all_anastomoses(
                    write_threshold=self._mycelial_write_threshold,
                    dry_run=self.dry_run,
                    top_n_notes=self._mycelial_apply_top_n,
                )
                logger.info(
                    "Mycelial growth: checked %d notes, wrote %d link(s)%s",
                    growth_result.get("notes_checked", 0),
                    growth_result.get("total_links_written", 0),
                    " [dry-run]" if self.dry_run else "",
                )
            except Exception as e:
                logger.warning("Mycelial growth failed: %s", e)

            mycelial_summary = {"decay": decay_result, "growth": growth_result}

        snapshot["mycelial"] = mycelial_summary   # None when pulse didn't fire this cycle

        # 7. Persist snapshot
        self.health_log.append(snapshot)

        logger.info("=== Coherence cycle complete ===")
        return snapshot

    def run_loop(self) -> None:
        """Run cycles continuously, sleeping `interval` seconds between each."""
        logger.info(
            "Coherence daemon starting (interval=%ds, dry_run=%s)",
            self.interval, self.dry_run
        )
        while True:
            try:
                self.run_once()
            except KeyboardInterrupt:
                logger.info("Daemon interrupted, shutting down.")
                break
            except Exception as e:
                logger.error("Cycle failed: %s", e, exc_info=True)
            logger.info("Sleeping %d seconds…", self.interval)
            time.sleep(self.interval)


# ──────────────────────────────────────────────────────────────────────────────
# CLI entry point
# ──────────────────────────────────────────────────────────────────────────────

def _parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="Vault Coherence Engine — maintain topological coherence in an Obsidian vault.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--checkpoint", default=None, help="Model checkpoint path (auto-detected)")
    p.add_argument("--config", default=None, help="Path to config.yaml")
    p.add_argument("--interval", type=int, default=300, help="Seconds between cycles")
    p.add_argument("--dry-run", action="store_true", help="Log actions without writing to vault")
    p.add_argument("--once", action="store_true", help="Run one cycle and exit")
    p.add_argument("--orphan-threshold", type=float, default=0.15,
                   help="Max cluster score to flag a note as an orphan")
    p.add_argument("--min-bridges", type=int, default=1,
                   help="Min inter-cluster wikilinks before bridging")
    p.add_argument("--top-k-links", type=int, default=5,
                   help="Link suggestions per orphan")
    p.add_argument("--log-level", default="INFO",
                   choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                   help="Logging verbosity")
    p.add_argument("--no-mycelial", action="store_true",
                   help="Disable the mycelial decay layer entirely")
    p.add_argument("--mycelial-decay-interval", type=int, default=12,
                   help="Apply hyphal decay every N daemon cycles (default 12 ≈ 1 hour)")
    p.add_argument("--mycelial-write-threshold", type=float, default=0.60,
                   help="Min anastomosis_strength to write a link to the vault (default 0.60)")
    p.add_argument("--mycelial-apply-top-n", type=int, default=5,
                   help="Number of top-active notes to grow links from per decay pulse (default 5)")
    return p.parse_args(argv)


def main(argv=None):
    args = _parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    import glob as _glob

    project_root = Path(__file__).parent.parent

    # Ensure project root is on sys.path so `inference` and `models` are importable
    # whether this is run as `python -m engine.coherence_daemon` or directly.
    _root_str = str(project_root.resolve())
    if _root_str not in sys.path:
        sys.path.insert(0, _root_str)

    # Auto-detect checkpoint
    ckpt = args.checkpoint
    if ckpt is None:
        ckpt_dir = project_root / "checkpoints"
        best = ckpt_dir / "best.pt"
        if best.exists():
            ckpt = str(best)
        else:
            candidates = sorted(_glob.glob(str(ckpt_dir / "perpetual_step_*.pt")))
            if not candidates:
                candidates = sorted(_glob.glob(str(ckpt_dir / "epoch_*.pt")))
            ckpt = candidates[-1] if candidates else None

    if ckpt is None:
        logger.error("No checkpoint found. Run: python train.py --stage finetune")
        sys.exit(1)

    config = args.config or str(project_root / "config" / "config.yaml")

    from inference import SambaOrchestrator
    logger.info("Loading SambaOrchestrator from %s…", ckpt)
    orch = SambaOrchestrator(checkpoint_path=ckpt, config_path=config)

    daemon = CoherenceDaemon(
        orchestrator=orch,
        dry_run=args.dry_run,
        interval_seconds=args.interval,
        orphan_threshold=args.orphan_threshold,
        min_bridges=args.min_bridges,
        top_k_links=args.top_k_links,
        mycelial_enabled=not args.no_mycelial,
        mycelial_decay_interval=args.mycelial_decay_interval,
        mycelial_write_threshold=args.mycelial_write_threshold,
        mycelial_apply_top_n=args.mycelial_apply_top_n,
    )

    if args.once:
        import json
        result = daemon.run_once()
        print(json.dumps(result, indent=2))
    else:
        daemon.run_loop()


if __name__ == "__main__":
    main()
