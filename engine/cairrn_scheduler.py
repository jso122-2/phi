"""
CAIRRNScheduler — CAIRRN-bound tick gate for PhiTracerSession.

Architecture
------------
The scheduler sits between the caller and PhiTracerSession.  Every `step()`
call goes through a coherence gate derived from the CODE hub's harmonic
shard activations (shards 3 and 4 — RANK and TAG arms).

Gate formula (mirrors engine/gate.py and the CAIRRN SKILL contract):

    code_activation = mean(shard[3].activation, shard[4].activation)
    coherence       = 1 − exp(−steps_since_tick / tau)
    gate_open       = coherence ≥ COHERENCE_THRESHOLD  (≈ 0.5671)

When the gate is open → tick (or refresh_and_tick) runs and steps resets.
When the gate is closed → tick is skipped; steps_since_tick increments.

The CODE hub is the scheduling signal because RANK (shard 3) and TAG (shard 4)
measure the quality of the current graph clustering and annotation state.
Low CODE activation means the system hasn't fully settled after the last
topology change — ticking too early would amplify noise.

Refresh policy
--------------
`refresh_every` controls how many successful (gated) ticks trigger a full
`refresh_and_tick()` instead of a plain `tick()`.  Set to 0 to never
auto-refresh (caller triggers refresh manually via `step(force_refresh=True)`).

SchedulerResult
---------------
Every `step()` returns a SchedulerResult regardless of gate outcome:

    gated           : True if a tick actually ran
    skipped         : True if coherence was below threshold
    coherence       : float in (0, 1] — the gate coherence at step time
    code_activation : mean CODE hub shard activation (gate signal)
    steps_since_tick: steps elapsed since the last successful tick
    refresh_ran     : True if this tick was a full refresh_and_tick()
    summary         : TracerSummary if gated else None
"""

from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass
from typing import Optional

from engine.gate import COHERENCE_THRESHOLD
from engine.phi_session import PhiTracerSession
from engine.tracer_daemon import TracerSummary


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------


@dataclass
class SchedulerResult:
    """Outcome of one CAIRRNScheduler.step() call."""

    gated: bool                     # True → tick ran
    skipped: bool                   # True → coherence gate blocked the tick
    coherence: float                # 1 − exp(−steps_since_tick / tau) at gate time
    code_activation: float          # mean(shard[3], shard[4]) activation
    steps_since_tick: int           # steps elapsed before this call
    refresh_ran: bool               # True → refresh_and_tick() was used
    summary: Optional[TracerSummary]  # TracerSummary if gated else None

    def as_dict(self) -> dict:
        d = {
            "gated":            self.gated,
            "skipped":          self.skipped,
            "coherence":        round(self.coherence, 6),
            "code_activation":  round(self.code_activation, 6),
            "steps_since_tick": self.steps_since_tick,
            "refresh_ran":      self.refresh_ran,
        }
        if self.summary is not None:
            d["summary"] = self.summary.as_dict()
        return d


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------


class CAIRRNScheduler:
    """
    CAIRRN-bound tick gate for PhiTracerSession.

    Parameters
    ----------
    session        : PhiTracerSession — must have build() already called.
    tau            : coherence time constant in steps (default 10.0).
                     Mirrors TracerDaemon.coherence_tau.
    threshold      : gate threshold (default COHERENCE_THRESHOLD ≈ 0.5671).
                     A tick fires when coherence ≥ threshold.
    refresh_every  : auto-refresh every N successful ticks (0 = disabled).
    """

    # CODE hub shard indices (fixed by CAIRRN hub geometry)
    _CODE_SHARDS: tuple[int, int] = (3, 4)  # RANK, TAG

    def __init__(
        self,
        session: PhiTracerSession,
        tau: float = 10.0,
        threshold: float = COHERENCE_THRESHOLD,
        refresh_every: int = 0,
    ) -> None:
        self._session = session
        self._tau = max(float(tau), 1e-9)
        self._threshold = float(threshold)
        self._refresh_every = max(0, int(refresh_every))

        self._steps_since_tick: int = 0   # increments every skipped step
        self._ticks_run: int = 0          # successful tick counter

    # ------------------------------------------------------------------
    # Step
    # ------------------------------------------------------------------

    def step(self, force_refresh: bool = False) -> SchedulerResult:
        """
        Attempt one scheduler step.

        Reads the CODE hub activation from the harmonic index, computes
        the coherence gate, and either fires a tick or skips.

        Parameters
        ----------
        force_refresh : bypass the refresh_every counter and run a full
                        refresh_and_tick() this step (still subject to the
                        coherence gate unless you also pass force_gate=True).

        Returns
        -------
        SchedulerResult
        """
        code_act = self._read_code_activation()
        coherence = 1.0 - math.exp(-self._steps_since_tick / self._tau)

        if coherence < self._threshold:
            self._steps_since_tick += 1
            return SchedulerResult(
                gated=False,
                skipped=True,
                coherence=coherence,
                code_activation=code_act,
                steps_since_tick=self._steps_since_tick - 1,
                refresh_ran=False,
                summary=None,
            )

        # Gate open — run the tick
        do_refresh = force_refresh or (
            self._refresh_every > 0
            and self._ticks_run > 0
            and self._ticks_run % self._refresh_every == 0
        )

        if do_refresh:
            summary = self._session.refresh_and_tick()
        else:
            summary = self._session.tick()

        steps_snapshot = self._steps_since_tick
        self._steps_since_tick = 0
        self._ticks_run += 1

        return SchedulerResult(
            gated=True,
            skipped=False,
            coherence=coherence,
            code_activation=code_act,
            steps_since_tick=steps_snapshot,
            refresh_ran=do_refresh,
            summary=summary,
        )

    # ------------------------------------------------------------------
    # Forced tick (bypass gate — for explicit caller control)
    # ------------------------------------------------------------------

    def force_tick(self, refresh: bool = False) -> SchedulerResult:
        """
        Run a tick unconditionally, ignoring the coherence gate.

        Use for explicit caller-controlled steps (e.g. after a library
        change that must propagate immediately regardless of coherence).
        """
        code_act = self._read_code_activation()
        coherence = 1.0 - math.exp(-self._steps_since_tick / self._tau)

        if refresh:
            summary = self._session.refresh_and_tick()
        else:
            summary = self._session.tick()

        steps_snapshot = self._steps_since_tick
        self._steps_since_tick = 0
        self._ticks_run += 1

        return SchedulerResult(
            gated=True,
            skipped=False,
            coherence=coherence,
            code_activation=code_act,
            steps_since_tick=steps_snapshot,
            refresh_ran=refresh,
            summary=summary,
        )

    # ------------------------------------------------------------------
    # Async variants (awaitable from async event loops)
    # ------------------------------------------------------------------

    async def astep(self, force_refresh: bool = False) -> SchedulerResult:
        """
        Async variant of step().

        Runs step(force_refresh) in a thread-pool executor so the calling
        coroutine yields the event loop during the session tick.
        """
        return await asyncio.to_thread(self.step, force_refresh)

    async def aforce_tick(self, refresh: bool = False) -> SchedulerResult:
        """
        Async variant of force_tick().

        Runs force_tick(refresh) in a thread-pool executor.
        """
        return await asyncio.to_thread(self.force_tick, refresh)

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    @property
    def steps_since_tick(self) -> int:
        return self._steps_since_tick

    @property
    def ticks_run(self) -> int:
        return self._ticks_run

    @property
    def coherence(self) -> float:
        """Current coherence value (not yet gated — live read)."""
        return 1.0 - math.exp(-self._steps_since_tick / self._tau)

    def reset_steps(self) -> None:
        """Reset steps_since_tick to 0 (coherence drops to 0 — gate closes immediately)."""
        self._steps_since_tick = 0

    def state(self) -> dict:
        """Serialisable scheduler state snapshot."""
        return {
            "steps_since_tick": self._steps_since_tick,
            "ticks_run":        self._ticks_run,
            "coherence":        round(self.coherence, 6),
            "threshold":        round(self._threshold, 6),
            "tau":              self._tau,
            "refresh_every":    self._refresh_every,
            "code_activation":  round(self._read_code_activation(), 6),
            "gate_open":        self.coherence >= self._threshold,
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _read_code_activation(self) -> float:
        """
        Read the mean activation of CODE hub shards (3 and 4) from the
        harmonic index.  Returns 0.0 before the first build().
        """
        try:
            idx = self._session.harmonic_index
            shards = idx.shards
            vals = [shards[i].activation for i in self._CODE_SHARDS if i < len(shards)]
            return float(sum(vals) / len(vals)) if vals else 0.0
        except Exception:
            return 0.0

    def __repr__(self) -> str:
        return (
            f"<CAIRRNScheduler "
            f"ticks={self._ticks_run} "
            f"steps_since={self._steps_since_tick} "
            f"coherence={self.coherence:.4f} "
            f"gate={'open' if self.coherence >= self._threshold else 'closed'}>"
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_cairrn_scheduler(
    session: PhiTracerSession,
    tau: float = 10.0,
    threshold: float = COHERENCE_THRESHOLD,
    refresh_every: int = 0,
) -> CAIRRNScheduler:
    """
    Construct a CAIRRNScheduler bound to *session*.

    Parameters
    ----------
    session       : must have build() already called before step() is used.
    tau           : coherence decay constant in steps (default 10.0).
    threshold     : gate open when coherence ≥ threshold (default ≈ 0.5671).
    refresh_every : auto-refresh every N ticks (0 = manual only).

    Returns
    -------
    CAIRRNScheduler
    """
    return CAIRRNScheduler(
        session=session,
        tau=tau,
        threshold=threshold,
        refresh_every=refresh_every,
    )
