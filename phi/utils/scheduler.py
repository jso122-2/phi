"""
Adaptive Topology Scheduler
Manages learning rate and curriculum based on two signals:
  1. Standard training loss plateau (ReduceLROnPlateau-style)
  2. Vault topology changes (new notes / links → boost LR to adapt fast)
"""
import logging
import math
from typing import List, Optional

try:
    import torch.optim as optim
    _TORCH_OK = True
except ImportError:
    optim = None  # type: ignore[assignment]
    _TORCH_OK = False

logger = logging.getLogger(__name__)


class AdaptiveTopologyScheduler:
    """
    Two-signal adaptive LR scheduler for roving-weight SambaGNN.

    Wraps an optimizer and adjusts LR based on:
      - Loss plateau: reduce LR after `patience` epochs of no improvement
      - Topology change: boost LR temporarily when vault graph changes
        (new notes added, existing notes modified)

    Curriculum:
      - Controls `hop_radius` passed to the dataset
      - Expands from `start_hop` to `max_hop` linearly over training

    Args:
        optimizer:           PyTorch optimizer
        base_lr:             starting learning rate
        min_lr:              floor for LR reduction
        patience:            epochs before LR reduction on plateau
        factor:              LR reduction factor on plateau
        warmup_steps:        linear warmup over N optimizer steps
        vault_change_boost:  LR multiplier when topology changes detected
        boost_decay_epochs:  epochs over which the boost decays back to 1.0
        start_hop:           initial curriculum hop radius
        max_hop:             maximum hop radius
        total_finetune_epochs: total finetune epochs (for curriculum timing)
    """

    def __init__(
        self,
        optimizer: optim.Optimizer,
        base_lr: float = 3e-4,
        min_lr: float = 1e-6,
        patience: int = 5,
        factor: float = 0.5,
        warmup_steps: int = 100,
        vault_change_boost: float = 2.0,
        boost_decay_epochs: int = 3,
        start_hop: int = 1,
        max_hop: int = 3,
        total_finetune_epochs: int = 50,
    ) -> None:
        self.optimizer = optimizer
        self.base_lr = base_lr
        self.min_lr = min_lr
        self.patience = patience
        self.factor = factor
        self.warmup_steps = warmup_steps
        self.vault_change_boost = vault_change_boost
        self.boost_decay_epochs = boost_decay_epochs
        self.start_hop = start_hop
        self.max_hop = max_hop
        self.total_finetune_epochs = total_finetune_epochs

        self._step = 0
        self._epoch = 0
        self._best_loss = float("inf")
        self._no_improve = 0
        self._boost_remaining = 0       # epochs of boost left
        self._current_lr = base_lr
        self._history: List[float] = []

    # ──────────────────────────────────────────────────────────────────────────
    # Step interface
    # ──────────────────────────────────────────────────────────────────────────

    def step_optimizer(self) -> None:
        """Call after each optimizer.step() to handle warmup."""
        self._step += 1
        if self._step <= self.warmup_steps:
            warmup_lr = self.base_lr * (self._step / self.warmup_steps)
            self._set_lr(warmup_lr)

    def epoch_end(self, loss: float, topology_changed: bool = False) -> dict:
        """
        Call at end of each training epoch.

        Args:
            loss:              validation/training loss for this epoch
            topology_changed:  True if vault graph changed (new/modified notes)

        Returns:
            dict with current lr, hop_radius, and event log
        """
        self._epoch += 1
        self._history.append(loss)

        events = []
        target_lr = self._current_lr

        # topology change boost — override plateau reduction temporarily
        if topology_changed:
            boosted = min(self._current_lr * self.vault_change_boost, self.base_lr * 3)
            self._boost_remaining = self.boost_decay_epochs
            target_lr = boosted
            events.append(f"topology_boost → lr={boosted:.2e}")
            logger.info(f"Vault topology changed — boosting LR to {boosted:.2e}")

        elif self._boost_remaining > 0:
            # decay boost linearly back to base
            self._boost_remaining -= 1
            decay_frac = self._boost_remaining / self.boost_decay_epochs
            target_lr = self.min_lr + (self._current_lr - self.min_lr) * decay_frac
            events.append(f"boost_decay → lr={target_lr:.2e}")

        else:
            # standard plateau check
            if loss < self._best_loss - 1e-4:
                self._best_loss = loss
                self._no_improve = 0
            else:
                self._no_improve += 1

            if self._no_improve >= self.patience:
                reduced = max(self._current_lr * self.factor, self.min_lr)
                target_lr = reduced
                self._no_improve = 0
                events.append(f"plateau_reduce → lr={reduced:.2e}")
                logger.info(f"Plateau detected — reducing LR to {reduced:.2e}")

        self._set_lr(target_lr)

        return {
            "epoch": self._epoch,
            "lr": self._current_lr,
            "hop_radius": self.hop_radius,
            "no_improve_streak": self._no_improve,
            "boost_remaining": self._boost_remaining,
            "events": events,
        }

    # ──────────────────────────────────────────────────────────────────────────
    # Curriculum
    # ──────────────────────────────────────────────────────────────────────────

    @property
    def hop_radius(self) -> int:
        """Current curriculum hop radius — expand linearly over finetune epochs."""
        if self.total_finetune_epochs <= 1:
            return self.max_hop
        progress = min(self._epoch / self.total_finetune_epochs, 1.0)
        hop = self.start_hop + int(progress * (self.max_hop - self.start_hop))
        return min(hop, self.max_hop)

    # ──────────────────────────────────────────────────────────────────────────
    # Internal
    # ──────────────────────────────────────────────────────────────────────────

    def _set_lr(self, lr: float) -> None:
        lr = max(lr, self.min_lr)
        self._current_lr = lr
        for pg in self.optimizer.param_groups:
            pg["lr"] = lr

    def state_dict(self) -> dict:
        return {
            "step": self._step,
            "epoch": self._epoch,
            "best_loss": self._best_loss,
            "no_improve": self._no_improve,
            "boost_remaining": self._boost_remaining,
            "current_lr": self._current_lr,
            "history": self._history,
        }

    def load_state_dict(self, state: dict) -> None:
        self._step = state["step"]
        self._epoch = state["epoch"]
        self._best_loss = state["best_loss"]
        self._no_improve = state["no_improve"]
        self._boost_remaining = state["boost_remaining"]
        self._current_lr = state["current_lr"]
        self._history = state["history"]
        self._set_lr(self._current_lr)
