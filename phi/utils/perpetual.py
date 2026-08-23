"""
PerpetualTrainer — Continuous GNN-SSM Background Training Loop

Runs training indefinitely in a background thread, interleaving:
  1. Task losses  (link prediction, retrieval, clustering)
  2. Coherence energy  (all four negative-e terms, annealed by schedule)
  3. EMA target distillation  (soft self-consistency via exponential moving average)
  4. Replay mixing  (old vault + synthetic snapshots prevent catastrophic forgetting)

The trainer never "completes" — it sleeps between micro-steps to respect
a configurable CPU/GPU fraction, and wakes on vault-change signals.

EMA target network (θ_ema):
    θ_ema ← τ·θ_ema + (1-τ)·θ_live
The EMA model generates "soft targets" for retrieval that remain stable
while the live model adapts — this prevents representation collapse during
rapid vault changes.

Stopping:
    call trainer.stop() — sets the stop event, lets the current step finish.
"""
from __future__ import annotations
import copy
import logging
import math
import os
import threading
import time
from typing import TYPE_CHECKING, Callable, Dict, List, Optional

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    _TORCH_OK = True
except ImportError:
    torch = None  # type: ignore[assignment]
    nn = None     # type: ignore[assignment]
    F = None      # type: ignore[assignment]
    _TORCH_OK = False

from phi.gnn.coherence import CoherenceWeightSchedule
from phi.utils.replay import ReplayBuffer, GraphSnapshot

if TYPE_CHECKING:
    from phi.gnn.samba_gnn import SambaGNN

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# EMA model wrapper
# ──────────────────────────────────────────────────────────────────────────────

class EMAModel:
    """
    Exponential Moving Average of SambaGNN weights.
    Used as a stable target network during perpetual training.
    """

    def __init__(self, model: SambaGNN, decay: float = 0.999) -> None:
        self.decay = decay
        self.shadow = copy.deepcopy(model)
        self.shadow.eval()
        for p in self.shadow.parameters():
            p.requires_grad_(False)

    @torch.no_grad()
    def update(self, model: SambaGNN) -> None:
        for s_param, m_param in zip(self.shadow.parameters(), model.parameters()):
            s_param.data.mul_(self.decay).add_(m_param.data, alpha=1 - self.decay)

    def __call__(self, *args, **kwargs):
        return self.shadow(*args, **kwargs)


# ──────────────────────────────────────────────────────────────────────────────
# EMA distillation loss
# ──────────────────────────────────────────────────────────────────────────────

@torch.no_grad()
def get_ema_targets(
    ema_model: EMAModel,
    snapshot: GraphSnapshot,
    device: torch.device,
) -> torch.Tensor:
    """Get stable node representations from the EMA model for distillation."""
    snap = snapshot.to(device)
    h_ema, _ = ema_model.shadow(
        snap.node_emb, snap.neighbor_seqs, snap.edge_type_ids, snap.neighbor_mask
    )
    return h_ema.detach()


def ema_distillation_loss(
    h_live: torch.Tensor,
    h_ema: torch.Tensor,
    temperature: float = 0.1,
) -> torch.Tensor:
    """
    Soft self-consistency loss: live model matches EMA model's distribution.
    Uses cosine similarity rather than L2 to avoid magnitude collapse.
    """
    p = F.normalize(h_live / temperature, dim=-1)
    q = F.normalize(h_ema  / temperature, dim=-1)
    return -( p * q ).sum(dim=-1).mean()   # maximise cosine → minimise negative


# ──────────────────────────────────────────────────────────────────────────────
# Per-step micro-training
# ──────────────────────────────────────────────────────────────────────────────

def micro_step(
    model: SambaGNN,
    ema_model: EMAModel,
    optimizer: torch.optim.Optimizer,
    snapshot: GraphSnapshot,
    coh_schedule: CoherenceWeightSchedule,
    device: torch.device,
    ema_weight: float = 0.2,
    link_weight: float = 1.0,
) -> Dict[str, float]:
    """
    One micro training step on a single GraphSnapshot.

    Returns dict of loss components for logging.
    """
    model.train()
    snap = snapshot.to(device)

    # build positive/negative link pairs from this snapshot's edges
    E = snap.edge_index.size(1)
    if E > 0:
        pos_src = snap.edge_index[0]
        pos_dst = snap.edge_index[1]
        neg_dst = torch.randint(0, snap.num_nodes, (E,), device=device)
    else:
        # no edges — skip link loss
        pos_src = pos_dst = neg_dst = torch.zeros(1, dtype=torch.long, device=device)

    optimizer.zero_grad()

    # ── Forward with coherence ─────────────────────────────────────────────
    coh_weights = coh_schedule.weights()
    model.set_coherence_weights(coh_weights)

    h, coh_info = model(
        snap.node_emb,
        snap.neighbor_seqs,
        snap.edge_type_ids,
        snap.neighbor_mask,
        edge_index=snap.edge_index,
        edge_weight=snap.edge_weight,
        return_coherence=True,
    )

    # ── Task loss: link prediction ─────────────────────────────────────────
    if E > 0:
        pos_logits = model.predict_links(h, pos_src, pos_dst)
        neg_logits = model.predict_links(h, pos_src, neg_dst)
        lp_loss = (
            F.binary_cross_entropy_with_logits(pos_logits, torch.ones_like(pos_logits))
          + F.binary_cross_entropy_with_logits(neg_logits, torch.zeros_like(neg_logits))
        ) / 2
    else:
        lp_loss = h.new_zeros(1).squeeze()

    # ── EMA distillation ───────────────────────────────────────────────────
    h_ema = get_ema_targets(ema_model, snapshot, device)
    if h_ema.size(0) == h.size(0):
        dist_loss = ema_distillation_loss(h, h_ema)
    else:
        dist_loss = h.new_zeros(1).squeeze()

    # ── Coherence energy ───────────────────────────────────────────────────
    E_coh = coh_info["E_coh"] if coh_info else h.new_zeros(1).squeeze()

    # ── Total ──────────────────────────────────────────────────────────────
    loss = link_weight * lp_loss + ema_weight * dist_loss + E_coh

    assert not torch.isnan(loss), "NaN loss in perpetual micro_step"

    loss.backward()
    nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
    optimizer.step()

    # update EMA
    ema_model.update(model)
    coh_schedule.step()

    metrics = {
        "loss": loss.item(),
        "lp_loss": lp_loss.item(),
        "dist_loss": dist_loss.item(),
    }
    if coh_info:
        metrics.update(coh_info["terms"])
    return metrics


# ──────────────────────────────────────────────────────────────────────────────
# PerpetualTrainer
# ──────────────────────────────────────────────────────────────────────────────

class PerpetualTrainer(threading.Thread):
    """
    Background training daemon.

    Runs micro_step in a loop, sleeping between steps to honour
    `gpu_fraction` (fraction of wallclock time the GPU/CPU is active).

    Step timing:
        active_time  = step_duration
        sleep_time   = active_time * (1 - gpu_fraction) / gpu_fraction

    Vault-change signals:
        Call trainer.notify_vault_change(snapshot) to inject a new vault
        snapshot with elevated priority. The trainer will prioritise it
        in the next several steps.

    Checkpointing:
        Saves model every `checkpoint_every_steps` steps to
        `checkpoint_dir/perpetual_step_{N}.pt`

    Args:
        model:                  Live SambaGNN model (trained in-place)
        optimizer:              Optimizer (shared with foreground training if desired)
        buffer:                 ReplayBuffer with pre-filled snapshots
        coh_schedule:           CoherenceWeightSchedule
        device:                 torch.device
        gpu_fraction:           0–1, fraction of time GPU is active (default 0.3)
        ema_decay:              EMA decay for target network
        checkpoint_every_steps: save frequency
        checkpoint_dir:         where to write checkpoints
        on_step_end:            optional callback(step, metrics)
    """

    def __init__(
        self,
        model: SambaGNN,
        optimizer: torch.optim.Optimizer,
        buffer: ReplayBuffer,
        coh_schedule: CoherenceWeightSchedule,
        device: torch.device,
        gpu_fraction: float = 0.30,
        ema_decay: float = 0.999,
        checkpoint_every_steps: int = 100,
        checkpoint_dir: str = "checkpoints/",
        on_step_end: Optional[Callable[[int, Dict], None]] = None,
    ) -> None:
        super().__init__(daemon=True, name="PerpetualTrainer")
        self.model = model
        self.optimizer = optimizer
        self.buffer = buffer
        self.coh_schedule = coh_schedule
        self.device = device
        self.gpu_fraction = max(0.05, min(gpu_fraction, 1.0))
        self.checkpoint_every = checkpoint_every_steps
        self.checkpoint_dir = checkpoint_dir
        self.on_step_end = on_step_end

        self.ema_model = EMAModel(model, decay=ema_decay)

        self._stop_event = threading.Event()
        self._vault_queue: List[GraphSnapshot] = []
        self._lock = threading.Lock()
        self._step = 0
        self._total_loss = 0.0

        os.makedirs(checkpoint_dir, exist_ok=True)

    def notify_vault_change(self, snapshot: GraphSnapshot) -> None:
        """Inject a high-priority new snapshot from vault change detection."""
        snapshot.priority = 3.0   # elevated to be sampled first
        with self._lock:
            self._vault_queue.append(snapshot)
            self.buffer.add(snapshot)
        logger.info(f"PerpetualTrainer: vault change notified ({snapshot.num_nodes} nodes)")

    def stop(self) -> None:
        self._stop_event.set()
        logger.info("PerpetualTrainer: stop requested")

    def run(self) -> None:
        logger.info(
            f"PerpetualTrainer started | device={self.device} | "
            f"gpu_fraction={self.gpu_fraction:.0%} | "
            f"buffer={len(self.buffer)} snapshots"
        )

        while not self._stop_event.is_set():
            if len(self.buffer) == 0:
                logger.warning("Buffer empty — waiting 5s")
                time.sleep(5.0)
                continue

            # prefer queued vault-change snapshots
            with self._lock:
                if self._vault_queue:
                    snapshot = self._vault_queue.pop(0)
                else:
                    snapshot = self.buffer.sample(1)[0]

            t_start = time.time()

            try:
                metrics = micro_step(
                    model=self.model,
                    ema_model=self.ema_model,
                    optimizer=self.optimizer,
                    snapshot=snapshot,
                    coh_schedule=self.coh_schedule,
                    device=self.device,
                )
                self._step += 1
                self._total_loss += metrics["loss"]

                if self._step % 10 == 0:
                    avg = self._total_loss / self._step
                    logger.info(
                        f"[Perpetual] step={self._step} | "
                        f"loss={metrics['loss']:.4f} | avg={avg:.4f} | "
                        f"coh={metrics.get('coh/total', 0.0):.4f} | "
                        f"α={metrics.get('coh/alpha', 0.0):.3f} | "
                        f"source={snapshot.source}"
                    )

                if self.on_step_end:
                    self.on_step_end(self._step, metrics)

                if self._step % self.checkpoint_every == 0:
                    self._save_checkpoint(metrics["loss"])

            except Exception as e:
                logger.error(f"PerpetualTrainer step error: {e}", exc_info=True)
                time.sleep(1.0)
                continue

            # throttle to respect gpu_fraction
            active_time = time.time() - t_start
            sleep_time = active_time * (1 - self.gpu_fraction) / self.gpu_fraction
            if sleep_time > 0:
                time.sleep(sleep_time)

        logger.info(f"PerpetualTrainer stopped after {self._step} steps")

    def _save_checkpoint(self, loss: float) -> None:
        path = os.path.join(self.checkpoint_dir, f"perpetual_step_{self._step:06d}.pt")
        torch.save({
            "step": self._step,
            "model_state_dict": self.model.state_dict(),
            "ema_state_dict": self.ema_model.shadow.state_dict(),
            "optimizer_state_dict": self.optimizer.state_dict(),
            "coh_schedule_step": self.coh_schedule._step,
            "loss": loss,
        }, path)
        logger.info(f"[Perpetual] checkpoint → {path}")
