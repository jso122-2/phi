"""
TracerDaemon — lifecycle manager for OctopusTracer instances.

Sits alongside CoherenceDaemon and spawns/despawns OctopusTracer agents
in response to vault graph conditions. Multiple live tracers cohere by
aggregating their arm signals before any vault writes are issued.

CAIRRN-BOUND MODE (default)
────────────────────────────
When cairrn_bound=True, all spawn decisions are driven by the local CairnBridge.
The bridge ingests vault topology snapshots, runs the three-layer CAIRRN pipeline,
and surfaces incoherent hubs as spawn triggers. Manual degree/drift checks are
replaced entirely — the model is autonomous.

Spawn conditions in CAIRRN-bound mode:
    HUB_INCOHERENT  — any CAIRRN hub drops below coherence_floor
    TICK_GATE       — every tick_gate_every cycles regardless

LEGACY MODE (cairrn_bound=False)
──────────────────────────────────
Manual conditions (degree anomaly, BERT drift) are still supported for
ablation studies or environments where CAIRRN is not active.

Swarm coherence:
    Multiple live tracers mean-aggregate their write-gated arm outputs.
    Tracers are culled after cull_after_readonly_ticks consecutive read-only cycles.

Integration:
    tracer_daemon = TracerDaemon.from_config(cfg)
    summary = tracer_daemon.run_once(snapshot, H)  ← adj not needed in soft_edge_mode
"""
import logging
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import torch

from phi.gnn.octopus_tracer import OctopusTracer, TracerOutput
from engine.cairrn_bridge import CairnBridge

logger = logging.getLogger("tracer_daemon")


# ──────────────────────────────────────────────────────────────────────────────
# Spawn condition flags
# ──────────────────────────────────────────────────────────────────────────────

SPAWN_HUB_INCOHERENT = "hub_incoherent"   # CAIRRN-bound mode
SPAWN_COHERENCE_DROP = "coherence_drop"   # legacy alias
SPAWN_DEGREE_ANOMALY = "degree_anomaly"   # legacy mode
SPAWN_BERT_DRIFT     = "bert_drift"       # legacy mode
SPAWN_TICK_GATE      = "tick_gate"
SPAWN_COLD_START     = "cold_start"       # first cycle seed — always spawn 1

# ──────────────────────────────────────────────────────────────────────────────
# Ana-Chi hub params for dual-arm smoothing (Tag → MATH, Merge → CODE)
#
# Tag   (Arm 5) is routed through the MATH hub  — tag assignment reflects
#              mathematical / conceptual structure in the vault.
# Merge (Arm 7) is routed through the CODE hub  — deduplication is a
#              content/symbol-density operation.
#
# Both hubs are rattling=True, so memory decay is applied per tick.
# ──────────────────────────────────────────────────────────────────────────────

_ANA_CHI_TAG   = {"gravity": 2.00, "decay": 0.95}   # MATH hub  χ=1.96
_ANA_CHI_MERGE = {"gravity": 1.50, "decay": 0.93}   # CODE hub  χ=0.99


@dataclass
class TracerInstance:
    """Wraps a single live OctopusTracer with its lifecycle metadata."""
    tracer:             OctopusTracer
    spawn_cycle:        int
    spawn_condition:    str                    # which condition triggered this spawn
    readonly_streak:    int = 0               # consecutive cycles with coherence < 0.50
    last_output:        Optional[TracerOutput] = None


@dataclass
class TracerSummary:
    """Summary returned to CoherenceDaemon after one tracer daemon cycle."""
    active_tracers:     int
    spawned_this_cycle: int
    culled_this_cycle:  int
    spawn_conditions:   List[str]
    aggregated_prune:   Optional[torch.Tensor]   # (N,)      — simple mean
    aggregated_graft:   Optional[torch.Tensor]   # (N, N)    — simple mean, upper-tri
    aggregated_cluster: Optional[torch.Tensor]   # (N, K)    — simple mean
    aggregated_rank:    Optional[torch.Tensor]   # (N,)      — simple mean
    aggregated_resurface: Optional[torch.Tensor] # (N,)      — simple mean
    aggregated_sprout:  Optional[torch.Tensor]   # (N,)      — simple mean
    aggregated_tag:     Optional[torch.Tensor]   # (N, T)    — Ana-Chi weighted (MATH hub)
    aggregated_merge:   Optional[torch.Tensor]   # (N, N)    — Ana-Chi weighted (CODE hub)
    write_gated:        bool
    total_suckers:      Dict[str, int]


# ──────────────────────────────────────────────────────────────────────────────
# TracerDaemon
# ──────────────────────────────────────────────────────────────────────────────

class TracerDaemon:
    """
    Manages a swarm of OctopusTracer instances in sync with CAIRRN tick cycles.

    Args:
        d_model:                   GNN hidden dimension (must match SambaGNN)
        num_clusters:              cluster head K
        num_tags:                  tag head T
        lora_rank:                 LoRA rank for sucker pools
        spawn_threshold:           ‖R(u)‖ floor for sucker spawn
        tau_cairrn:                CAIRRN coherence time constant
        cairrn_spawn_threshold:    coherence drop below this spawns a tracer
        degree_delta_threshold:    edge delta that triggers degree-anomaly spawn
        bert_drift_threshold:      L2 embedding drift that triggers bert-drift spawn
        tick_gate_every:           unconditional spawn every N cycles
        max_tracers:               cap on simultaneously live tracers
        cull_after_readonly_ticks: remove tracer after N consecutive read-only cycles
        device:                    torch device
    """

    def __init__(
        self,
        d_model: int = 256,
        num_clusters: int = 16,
        num_tags: int = 64,
        lora_rank: int = 8,
        spawn_threshold: float = 1.0,
        scup_temp: float = 1.0,
        tau_cairrn: float = 30.0,
        cairrn_spawn_threshold: float = 0.60,
        degree_delta_threshold: int = 3,
        bert_drift_threshold: float = 0.20,
        tick_gate_every: int = 10,
        max_tracers: int = 8,
        cull_after_readonly_ticks: int = 5,
        soft_edge_mode: bool = True,
        cairrn_bound: bool = True,
        device: Optional[torch.device] = None,
    ) -> None:
        self.d_model = d_model
        self.num_clusters = num_clusters
        self.num_tags = num_tags
        self.lora_rank = lora_rank
        self.spawn_threshold = spawn_threshold
        self.scup_temp = scup_temp
        self.tau_cairrn = tau_cairrn
        self.cairrn_spawn_threshold = cairrn_spawn_threshold
        self.degree_delta_threshold = degree_delta_threshold
        self.bert_drift_threshold = bert_drift_threshold
        self.tick_gate_every = tick_gate_every
        self.max_tracers = max_tracers
        self.cull_after_readonly_ticks = cull_after_readonly_ticks
        self.soft_edge_mode = soft_edge_mode
        self.cairrn_bound = cairrn_bound
        self.device = device or torch.device("cpu")

        self._tracers: List[TracerInstance] = []
        self._cycle: int = 0
        self._prev_degrees: Optional[torch.Tensor] = None
        self._prev_H: Optional[torch.Tensor] = None

        # CAIRRN bridge — lives here, ingests vault snapshots, drives spawning
        self.cairrn = CairnBridge(
            tau=tau_cairrn,
            coherence_floor=cairrn_spawn_threshold,
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Spawn
    # ──────────────────────────────────────────────────────────────────────────

    def _spawn(self, condition: str) -> TracerInstance:
        tracer = OctopusTracer(
            d_model=self.d_model,
            num_clusters=self.num_clusters,
            num_tags=self.num_tags,
            lora_rank=self.lora_rank,
            spawn_threshold=self.spawn_threshold,
            tau_cairrn=self.tau_cairrn,
            scup_temp=self.scup_temp,
            soft_edge_mode=self.soft_edge_mode,
        ).to(self.device)
        instance = TracerInstance(
            tracer=tracer,
            spawn_cycle=self._cycle,
            spawn_condition=condition,
        )
        self._tracers.append(instance)
        logger.info(
            "Tracer spawned (condition=%s, total_live=%d)", condition, len(self._tracers)
        )
        return instance

    def _check_spawn_conditions_cairrn(self, snapshot: dict, H: torch.Tensor) -> List[str]:
        """
        CAIRRN-bound spawn logic.

        1. Ingest vault snapshot into CairnBridge (routes metrics through 5 hubs)
        2. Propagate harmonic activation one step
        3. Any hub below coherence_floor → spawn trigger
        4. Tick gate still fires unconditionally every N cycles
        """
        # Feed snapshot through the three-layer pipeline
        self.cairrn.ingest_vault_snapshot(snapshot)
        self.cairrn.propagate(steps=1)

        triggered = []

        # Hub incoherence signals
        signals = self.cairrn.spawn_signals()
        if signals:
            triggered.append(SPAWN_HUB_INCOHERENT)
            logger.debug("Incoherent CAIRRN hubs: %s", signals)

        # Tick gate (still fires even in CAIRRN mode — minimum gardening pulse)
        if self._cycle > 0 and (self._cycle % self.tick_gate_every) == 0:
            triggered.append(SPAWN_TICK_GATE)

        return triggered

    def _check_spawn_conditions_legacy(
        self,
        snapshot: dict,
        H: torch.Tensor,
        adj: Optional[torch.Tensor],
        cairrn_coherence: float,
    ) -> List[str]:
        """Legacy spawn logic (degree anomaly + BERT drift). Used when cairrn_bound=False."""
        triggered = []

        if cairrn_coherence < self.cairrn_spawn_threshold:
            triggered.append(SPAWN_COHERENCE_DROP)

        if adj is not None:
            degrees = adj.sum(dim=-1)
            if self._prev_degrees is not None and degrees.shape == self._prev_degrees.shape:
                delta = (degrees - self._prev_degrees).abs().max().item()
                if delta >= self.degree_delta_threshold:
                    triggered.append(SPAWN_DEGREE_ANOMALY)
            self._prev_degrees = degrees.detach()

        if self._prev_H is not None and H.shape == self._prev_H.shape:
            drift = (H - self._prev_H).norm(dim=-1).max().item()
            if drift > self.bert_drift_threshold:
                triggered.append(SPAWN_BERT_DRIFT)
        self._prev_H = H.detach()

        if self._cycle > 0 and (self._cycle % self.tick_gate_every) == 0:
            triggered.append(SPAWN_TICK_GATE)

        return triggered

    # ──────────────────────────────────────────────────────────────────────────
    # Cull
    # ──────────────────────────────────────────────────────────────────────────

    def _cull(self) -> int:
        """Remove tracers that have been read-only for too long. Returns cull count."""
        before = len(self._tracers)
        self._tracers = [
            inst for inst in self._tracers
            if inst.readonly_streak < self.cull_after_readonly_ticks
        ]
        culled = before - len(self._tracers)
        if culled:
            logger.info("Culled %d incoherent tracer(s)", culled)
        return culled

    # ──────────────────────────────────────────────────────────────────────────
    # Aggregate swarm outputs
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _aggregate(outputs: List[TracerOutput]) -> Optional[TracerOutput]:
        """
        Simple mean-aggregate outputs across all write-gated tracers.
        Used for arms 1-4, 6, 8 (Prune, Graft, Cluster, Rank, Resurface, Sprout).
        Tag and Merge use Ana-Chi weighted aggregation — see _aggregate_anachi().
        """
        gated = [o for o in outputs if o.write_gated]
        if not gated:
            return None

        def mean_stack(attr: str) -> torch.Tensor:
            tensors = [getattr(o, attr) for o in gated]
            return torch.stack(tensors, dim=0).mean(dim=0)

        return TracerOutput(
            prune     = mean_stack("prune"),
            graft     = mean_stack("graft"),
            cluster   = mean_stack("cluster"),
            rank      = mean_stack("rank"),
            tag       = mean_stack("tag"),
            resurface = mean_stack("resurface"),
            merge     = mean_stack("merge"),
            sprout    = mean_stack("sprout"),
            R         = mean_stack("R"),
            coherence_score = sum(o.coherence_score for o in gated) / len(gated),
            write_gated     = True,
            sucker_counts   = {},
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Ana-Chi dual-arm smoothing (Tag + Merge)
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _anachi_weight(coherence: float, tick: int, gravity: float, decay: float) -> float:
        """
        Ana-Chi modulation weight for one tracer instance.

        Mirrors CAIRRN Layer 1 with rattling=True:
            weight = coherence × gravity × decay^tick

        Args:
            coherence:  tracer's exp(−tick/τ) coherence score ∈ [0, 1]
            tick:       number of steps this tracer has been alive
            gravity:    hub gravity constant
            decay:      hub per-cycle memory decay factor

        Returns:
            Non-negative scalar weight. Zero if coherence is zero.
        """
        return coherence * gravity * (decay ** max(tick, 0))

    def _aggregate_anachi(
        self,
        pairs: List[Tuple["TracerInstance", TracerOutput]],
    ) -> Tuple[Optional[torch.Tensor], Optional[torch.Tensor]]:
        """
        Ana-Chi dual-arm smoothing for Tag (Arm 5) and Merge (Arm 7).

        Each write-gated tracer's contribution is weighted by its Ana-Chi
        modulated coherence, routed through the appropriate CAIRRN hub:

            Tag   → MATH hub  (gravity=2.00, decay=0.95, rattling)
            Merge → CODE hub  (gravity=1.50, decay=0.93, rattling)

        Weighted mean:
            w_i       = coherence_i × gravity × decay^tick_i
            agg_arm   = Σ(w_i × arm_i) / Σ(w_i)

        The rattling decay causes recently-spawned tracers (low tick) to
        contribute more strongly than stale ones, smoothly rather than via
        the hard coherence gate used for other arms.

        Args:
            pairs: list of (TracerInstance, TracerOutput) for the current cycle,
                   captured before culling so tick counts are accurate.

        Returns:
            (aggregated_tag, aggregated_merge) — both None if no write-gated
            tracers exist or all weights collapse to zero.
        """
        gated = [(inst, out) for inst, out in pairs if out.write_gated]
        if not gated:
            return None, None

        def _weighted_mean(
            attr: str,
            hub_params: Dict,
        ) -> Optional[torch.Tensor]:
            weights = torch.tensor([
                self._anachi_weight(
                    out.coherence_score,
                    inst.tracer._tick,
                    hub_params["gravity"],
                    hub_params["decay"],
                )
                for inst, out in gated
            ], dtype=torch.float32)

            denom = weights.sum()
            if denom < 1e-9:
                return None

            stacked = torch.stack([getattr(out, attr) for _, out in gated], dim=0)
            # weights shape: (M,) → broadcast over (M, ...) tensor
            shape = (-1,) + (1,) * (stacked.ndim - 1)
            return (weights.view(shape) * stacked).sum(dim=0) / denom

        agg_tag   = _weighted_mean("tag",   _ANA_CHI_TAG)
        agg_merge = _weighted_mean("merge", _ANA_CHI_MERGE)
        return agg_tag, agg_merge

    # ──────────────────────────────────────────────────────────────────────────
    # Main cycle
    # ──────────────────────────────────────────────────────────────────────────

    def run_once(
        self,
        snapshot: dict,
        H: torch.Tensor,                            # (N, D) from SambaGNN
        adj: Optional[torch.Tensor] = None,         # (N, N) — only needed when soft_edge_mode=False
        bert_proj_weight: Optional[torch.Tensor] = None,
        cairrn_coherence: float = 1.0,              # only used in legacy mode
        existing_edge_mask: Optional[torch.Tensor] = None,
    ) -> TracerSummary:
        """
        One tracer daemon cycle.  In CAIRRN-bound soft-edge mode, only
        `snapshot` and `H` are required — the daemon is fully autonomous.

        Steps:
            1. Evaluate spawn conditions (CAIRRN or legacy)
            2. Spawn new tracers up to max_tracers
            3. Advance tick + forward all live tracers
            4. Update read-only streak counters
            5. Cull incoherent tracers
            6. Mean-aggregate write-gated outputs
            7. Decay CAIRRN hub activations
            8. Return TracerSummary

        Args:
            snapshot:            topology snapshot dict from CoherenceDaemon
            H:                   (N, D) node embeddings (output of SambaGNN.forward)
            adj:                 (N, N) adjacency — optional in soft_edge_mode
            bert_proj_weight:    BERT proj weight for sucker warm-start
            cairrn_coherence:    external coherence signal (legacy mode only)
            existing_edge_mask:  (N, N) bool for Graft arm suppression

        Returns:
            TracerSummary with aggregated arm outputs and CAIRRN state
        """
        self._cycle += 1
        H = H.to(self.device)
        if adj is not None:
            adj = adj.to(self.device)

        # 1. Spawn conditions
        if self.cairrn_bound:
            conditions = self._check_spawn_conditions_cairrn(snapshot, H)
        else:
            conditions = self._check_spawn_conditions_legacy(
                snapshot, H, adj, cairrn_coherence
            )

        # Cold-start: seed exactly one tracer on the very first cycle so there
        # is always at least one octopus arm tracing the graph from boot.
        if self._cycle == 1 and not self._tracers:
            conditions = [SPAWN_COLD_START] + conditions

        spawned_count = 0
        for cond in conditions:
            if len(self._tracers) >= self.max_tracers:
                logger.debug("max_tracers=%d reached — skipping %s", self.max_tracers, cond)
                break
            self._spawn(cond)
            spawned_count += 1

        # 2. Tick + forward all live tracers
        # Snapshot (inst, out) pairs before culling — needed for Ana-Chi weighting.
        outputs:      List[TracerOutput] = []
        live_pairs:   List[Tuple[TracerInstance, TracerOutput]] = []
        for inst in self._tracers:
            inst.tracer.tick()
            try:
                out = inst.tracer(
                    H=H,
                    adj=adj,
                    existing_edge_mask=existing_edge_mask,
                    bert_proj_weight=bert_proj_weight,
                    auto_spawn=True,
                )
                inst.last_output = out
                inst.readonly_streak = 0 if out.write_gated else inst.readonly_streak + 1
                outputs.append(out)
                live_pairs.append((inst, out))
                logger.debug(
                    "Tracer (spawn=%d cond=%s): coh=%.3f write=%s suckers=%s",
                    inst.spawn_cycle, inst.spawn_condition,
                    out.coherence_score, out.write_gated, out.sucker_counts,
                )
            except Exception as e:
                logger.warning("Tracer forward failed: %s", e)
                inst.readonly_streak += 1

        # 3. Cull
        culled = self._cull()

        # 4. Simple mean aggregate (Prune, Graft, Cluster, Rank, Resurface, Sprout)
        agg = self._aggregate(outputs)

        # 5. Ana-Chi dual-arm smoothing (Tag → MATH hub, Merge → CODE hub)
        #    Uses pre-cull live_pairs so tick counts remain accurate.
        agg_tag, agg_merge = self._aggregate_anachi(live_pairs)

        # 6. Route arm score means back through the harmonic sharding system.
        #    This creates a one-cycle-lag feedback loop: the tracer's assessments
        #    of the vault inject energy into the CAIRRN ring, which influences
        #    future propagation and (indirectly) future spawn pressure.
        if agg is not None:
            def _ms(t: Optional[torch.Tensor]) -> float:
                """Mean of a score tensor; for pairwise arms take nonzero elements."""
                if t is None:
                    return 0.0
                nonzero = t[t > 0]
                return float(nonzero.mean().item()) if nonzero.numel() > 0 else 0.0

            self.cairrn.ingest_arm_scores({
                "prune":     _ms(agg.prune),
                "graft":     _ms(agg.graft),
                "cluster":   _ms(agg.cluster),
                "rank":      _ms(agg.rank),
                "resurface": _ms(agg.resurface),
                "sprout":    _ms(agg.sprout),
                "tag":       _ms(agg_tag),
                "merge":     _ms(agg_merge),
            })

        # 7. CAIRRN decay tick
        self.cairrn.decay_all()

        # 7. Total sucker count
        total_suckers: Dict[str, int] = {}
        for inst in self._tracers:
            for arm_name, cnt in inst.tracer.sucker_report().items():
                total_suckers[arm_name] = total_suckers.get(arm_name, 0) + cnt

        summary = TracerSummary(
            active_tracers       = len(self._tracers),
            spawned_this_cycle   = spawned_count,
            culled_this_cycle    = culled,
            spawn_conditions     = conditions,
            aggregated_prune     = agg.prune       if agg else None,
            aggregated_graft     = agg.graft       if agg else None,
            aggregated_cluster   = agg.cluster     if agg else None,
            aggregated_rank      = agg.rank        if agg else None,
            aggregated_resurface = agg.resurface   if agg else None,
            aggregated_sprout    = agg.sprout      if agg else None,
            aggregated_tag       = agg_tag,
            aggregated_merge     = agg_merge,
            write_gated          = agg.write_gated if agg else False,
            total_suckers        = total_suckers,
        )

        logger.info(
            "TracerDaemon cycle %d | live=%d spawned=%d culled=%d write=%s | %s",
            self._cycle, summary.active_tracers, spawned_count, culled,
            summary.write_gated, self.cairrn.report(),
        )
        return summary

    # ──────────────────────────────────────────────────────────────────────────
    # Factory
    # ──────────────────────────────────────────────────────────────────────────

    @classmethod
    def from_config(cls, cfg) -> "TracerDaemon":
        """
        Build TracerDaemon from OmegaConf/dict config.

        Reads from cfg.tracer section:
            d_model, num_clusters, num_tags, lora_rank, spawn_threshold,
            scup_temp, tau_cairrn, cairrn_spawn_threshold, degree_delta_threshold,
            bert_drift_threshold, tick_gate_every, max_tracers,
            cull_after_readonly_ticks, device
        """
        tc = cfg.get("tracer", {})
        device_str = tc.get("device", "cpu")
        device = torch.device(device_str)

        return cls(
            d_model                  = cfg.get("model", {}).get("gnn", {}).get("hidden_dim", 256),
            num_clusters             = cfg.get("model", {}).get("heads", {}).get("num_clusters", 16),
            num_tags                 = tc.get("num_tags", 64),
            lora_rank                = tc.get("lora_rank", 8),
            spawn_threshold          = tc.get("spawn_threshold", 1.0),
            scup_temp                = tc.get("scup_temp", 1.0),
            tau_cairrn               = tc.get("tau_cairrn", 30.0),
            cairrn_spawn_threshold   = tc.get("cairrn_spawn_threshold", 0.60),
            degree_delta_threshold   = tc.get("degree_delta_threshold", 3),
            bert_drift_threshold     = tc.get("bert_drift_threshold", 0.20),
            tick_gate_every          = tc.get("tick_gate_every", 10),
            max_tracers              = tc.get("max_tracers", 8),
            cull_after_readonly_ticks= tc.get("cull_after_readonly_ticks", 5),
            soft_edge_mode           = tc.get("soft_edge_mode", True),
            cairrn_bound             = tc.get("cairrn_bound", True),
            device                   = device,
        )

