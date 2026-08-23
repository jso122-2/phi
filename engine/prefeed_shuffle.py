"""
CAIRRN-bound prefeed shuffle — double-buffer soft-queue for track ordering.

Architecture (Instagram analogy)
---------------------------------
Instagram pre-uploads a photo to its CDN while you're still editing it.
When you press "Share", the upload is already done — zero visible latency.

This module does the same for shuffle order:

    COHERENCE BUILDING          COHERENCE THRESHOLD CROSSED
    (gate closed)               (gate opens)
         │                              │
         ▼                              ▼
    prefeed()                      commit()
    compute next order          swap pending → active
    from CAIRRN state           cursor resets to 0
    store in _pending           _pending cleared

While coherence < threshold  →  serve tracks from _active (hysteresis)
When coherence ≥ threshold   →  commit: _pending becomes _active instantly

CAIRRN controls the order
--------------------------
The harmonic index shard activations (8 values) seed a "gravity vector" in
H-space (256-d).  Tracks are scored by their cosine similarity to this
gravity vector, then sorted with calibrated exploration noise.

    g = softmax(activations) @ Q          # (256,) gravity in H-space
    score[i] = H[i] · g + ε · noise[i]   # harmonic resonance + exploration
    order = argsort(-score)               # descending: most resonant first

Q ∈ ℝ^(8×256) is a fixed random orthonormal-ish projection (seed=42) that
maps the 8-shard space into H-space.  Fixed seed → same Q every run →
deterministic gravity for the same shard activations.

When all shard activations are equal → uniform g → exploration noise
dominates → effectively random shuffle.
When CODE shards (3, 4) are hot → tracks most resonant with those shard
directions rise to the top → CAIRRN shapes the queue.

Usage (standalone loop)
-----------------------
    shuffle = PrefeedShuffle(exploration=0.15)

    # Build initial shuffle
    shuffle.prefeed(snap, harmonic_index)
    shuffle.commit()

    for _ in range(100):
        track_idx = shuffle.next()
        track = snap.tracks[track_idx]
        play(track)

        # Meanwhile: coherence builds in background steps
        result = scheduler.step()
        if result.skipped:
            shuffle.prefeed(snap, harmonic_index)   # recompute in background
        elif result.gated:
            shuffle.commit()                        # coherence reached → swap

Usage (integrated CAIRRNPrefeedShuffle)
---------------------------------------
    shuffle = CAIRRNPrefeedShuffle(session, exploration=0.15)
    shuffle.seed()          # initial prefeed + forced commit

    result = shuffle.step() # clock tick: gate check + auto prefeed/commit
    track  = shuffle.peek_active()  # see next N tracks without advancing
    track_idx = shuffle.next()      # advance cursor, get track index
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from engine.gate import COHERENCE_THRESHOLD
from engine.phi_session import PhiTracerSession
from phi.graph._snapshot import PhiGraphSnapshot
from sims.harmonic import HarmonicIndex


# ---------------------------------------------------------------------------
# Fixed projection: shard space (8) → H-space (256)
# ---------------------------------------------------------------------------

_Q_SEED: int = 42
_Q_SHARDS: int = 8
_Q_DIM: int = 256

def _build_Q() -> np.ndarray:
    """
    Fixed (8, 256) projection matrix — deterministic, never changes.

    Rows are L2-normalised random vectors.  Same Q every process start
    so shard activation → gravity mapping is stable across sessions.
    """
    rng = np.random.default_rng(_Q_SEED)
    Q = rng.standard_normal((_Q_SHARDS, _Q_DIM))
    norms = np.linalg.norm(Q, axis=1, keepdims=True)
    return Q / np.where(norms < 1e-12, 1e-12, norms)


_Q: np.ndarray = _build_Q()   # (8, 256) — module-level singleton


# ---------------------------------------------------------------------------
# Core harmonic scoring
# ---------------------------------------------------------------------------


def _harmonic_scores(
    H: np.ndarray,
    activations: list[float],
    exploration: float,
    rng: np.random.Generator,
    w: float = 0.5,
) -> np.ndarray:
    """
    Score N tracks by harmonic resonance with current shard activations.

    Parameters
    ----------
    H           : (N, 256) L2-normalised track embeddings
    activations : list of 8 shard activations (raw, unnormalised)
    exploration : Gaussian noise scale added to break exact ties
    rng         : random Generator for noise
    w           : resource philosophy ∈ [0, 1] (Z_geom parameter).
                  Controls how total shard activation scales exploration noise:

                    w = 0.0  →  divide form   (buffer-capacity):
                                high-resource states reduce exploration noise
                                — stable queue, well-established track order preserved
                    w = 0.5  →  neutral form (default):
                                A_total^0 = 1 → exploration independent of resources
                                — current behaviour
                    w = 1.0  →  multiply form (market-power):
                                high-resource states amplify exploration noise
                                — exploratory queue, dominant shards force more variety

                  Intermediate w tunes continuously between stability and influence.

    Returns
    -------
    scores : (N,) float — higher = more resonant with current CAIRRN state
    """
    N = H.shape[0]
    if N == 0:
        return np.zeros(0, dtype=np.float64)

    a = np.array(activations, dtype=np.float64)

    # Softmax — maps activations to a probability distribution over shards
    a_softmax = a - a.max()    # numerical stability
    a_softmax = np.exp(a_softmax)
    a_softmax = a_softmax / (a_softmax.sum() + 1e-12)  # (8,) probability

    # Gravity vector in H-space: weighted centroid of shard basis vectors
    g = a_softmax @ _Q  # (8,) · (8, 256) = (256,)
    g_norm = np.linalg.norm(g)
    if g_norm > 1e-12:
        g = g / g_norm  # L2-normalise

    # Cosine similarity — H rows already L2-normalised → plain dot product
    scores = H @ g  # (N,)

    # Z_geom-modulated exploration noise.
    # The global exploration scale is: effective_exploration = exploration · A_total^(2w−1)
    # where A_total = Σ activations (total harmonic resources).
    #
    # w=0   (divide): high activation → smaller noise → stable track ordering
    # w=0.5 (neutral): A^0 = 1.0 → same as current behaviour
    # w=1   (multiply): high activation → larger noise → exploratory ordering
    if exploration > 0.0:
        A_total = max(float(np.sum(np.abs(a))), 1e-12)
        resource_scale = A_total ** (2.0 * w - 1.0)
        scores = scores + (exploration * resource_scale) * rng.standard_normal(N)

    return scores


def _shuffle_order(
    H: np.ndarray,
    activations: list[float],
    exploration: float,
    rng: np.random.Generator,
) -> list[int]:
    """
    Return track indices ordered by descending harmonic resonance score.

    Parameters
    ----------
    H           : (N, 256) — snapshot embeddings
    activations : 8 shard activations from HarmonicIndex
    exploration : noise scale (0 = deterministic, 0.15 = moderate variety)
    rng         : Generator

    Returns
    -------
    list[int] of length N — ordered track indices (most resonant first)
    """
    scores = _harmonic_scores(H, activations, exploration, rng)
    return list(np.argsort(-scores).tolist())


# ---------------------------------------------------------------------------
# ShufflePeek — snapshot of the active queue for inspection
# ---------------------------------------------------------------------------


@dataclass
class ShufflePeek:
    """
    A read-only view of the next N tracks in the active shuffle.

    cursor      : current position in the active order
    indices     : next up-to-N track indices (not yet consumed)
    pending_ready: True if a pending order exists and is ready to commit
    """
    cursor: int
    indices: list[int]
    pending_ready: bool

    @property
    def n(self) -> int:
        return len(self.indices)


# ---------------------------------------------------------------------------
# StepResult — outcome of CAIRRNPrefeedShuffle.step()
# ---------------------------------------------------------------------------


@dataclass
class ShuffleStepResult:
    """
    Outcome of one CAIRRNPrefeedShuffle.step() call.

    committed    : True if _pending → _active swap happened this step
    prefeeding   : True if prefeed() was called this step (background compute)
    coherence    : current gate coherence
    code_act     : mean CODE hub (shard 3, 4) activation
    steps_waiting: steps since last commit (= steps_since_tick from scheduler)
    active_len   : length of the current active shuffle
    pending_len  : length of the pending (staged) shuffle
    """
    committed: bool
    prefeeding: bool
    coherence: float
    code_act: float
    steps_waiting: int
    active_len: int
    pending_len: int

    def as_dict(self) -> dict:
        return {
            "committed":    self.committed,
            "prefeeding":   self.prefeeding,
            "coherence":    round(self.coherence, 6),
            "code_act":     round(self.code_act, 6),
            "steps_waiting":self.steps_waiting,
            "active_len":   self.active_len,
            "pending_len":  self.pending_len,
        }


# ---------------------------------------------------------------------------
# PrefeedShuffle — double-buffer core
# ---------------------------------------------------------------------------


class PrefeedShuffle:
    """
    Double-buffer prefeed shuffle.

    _active  — currently serving order (list of track indices)
    _pending — pre-computed next order (staged; not yet committed)
    _cursor  — position in _active

    The caller controls the prefeed/commit lifecycle based on CAIRRN state.
    This class only owns the buffers and the harmonic scoring function.

    Parameters
    ----------
    exploration : noise scale for shuffle variety (default 0.15)
    rng_seed    : seed for the internal Generator (default 7 — resonant prime)
    """

    def __init__(
        self,
        exploration: float = 0.15,
        rng_seed: int = 7,
        w: float = 0.5,
    ) -> None:
        self.exploration = float(exploration)
        self._rng = np.random.default_rng(rng_seed)
        self.w = float(w)   # resource philosophy: 0=buffer/stable, 0.5=neutral, 1=market/exploratory

        self._active: list[int] = []
        self._pending: list[int] = []
        self._cursor: int = 0

    # ------------------------------------------------------------------
    # Prefeed — compute next order in background
    # ------------------------------------------------------------------

    def prefeed(
        self,
        snap: PhiGraphSnapshot,
        harmonic_index: HarmonicIndex,
    ) -> tuple[int, float]:
        """
        Compute the next shuffle order from the current CAIRRN state.

        Stores the result in _pending without touching _active.
        Safe to call repeatedly during the coherence-building phase —
        each call overwrites _pending with a fresher computation.

        Returns
        -------
        tuple[int, float]
            N   — number of tracks in the new pending order
            pfs — mean harmonic resonance score of the pending order
                  (FastFormula / PFS input to the M3 quality gate)
        """
        N = snap.N
        if N == 0:
            self._pending = []
            return 0, 0.0

        activations = [s.activation for s in harmonic_index.shards]
        scores = _harmonic_scores(snap.H, activations, self.exploration, self._rng, w=self.w)
        self._pending = list(np.argsort(-scores).tolist())
        pfs = float(np.mean(scores)) if len(scores) > 0 else 0.0
        return len(self._pending), pfs

    # ------------------------------------------------------------------
    # Commit — swap pending → active
    # ------------------------------------------------------------------

    def commit(self) -> bool:
        """
        Swap _pending into _active and reset the cursor.

        Called when the CAIRRN coherence gate opens.
        If _pending is empty, the commit is a no-op.

        Returns
        -------
        bool — True if the swap happened (pending was non-empty)
        """
        if not self._pending:
            return False
        self._active = self._pending
        self._pending = []
        self._cursor = 0
        return True

    # ------------------------------------------------------------------
    # Serving — consume tracks from active
    # ------------------------------------------------------------------

    def next(self) -> int:
        """
        Return the next track index from the active shuffle and advance cursor.

        Wraps around when the end is reached (continuous play).

        Raises
        ------
        RuntimeError if _active is empty (no shuffle committed yet).
        """
        if not self._active:
            raise RuntimeError(
                "PrefeedShuffle: no active shuffle — call prefeed() + commit() first."
            )
        idx = self._active[self._cursor % len(self._active)]
        self._cursor += 1
        return int(idx)

    def peek(self, n: int = 5) -> ShufflePeek:
        """
        Peek at the next *n* track indices without advancing the cursor.

        Returns
        -------
        ShufflePeek
        """
        if not self._active:
            return ShufflePeek(cursor=self._cursor, indices=[], pending_ready=bool(self._pending))
        start = self._cursor % len(self._active)
        n = min(n, len(self._active))
        indices: list[int] = []
        for i in range(n):
            indices.append(self._active[(start + i) % len(self._active)])
        return ShufflePeek(
            cursor=self._cursor,
            indices=indices,
            pending_ready=bool(self._pending),
        )

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    @property
    def has_active(self) -> bool:
        return bool(self._active)

    @property
    def has_pending(self) -> bool:
        return bool(self._pending)

    @property
    def active_len(self) -> int:
        return len(self._active)

    @property
    def pending_len(self) -> int:
        return len(self._pending)

    @property
    def cursor(self) -> int:
        return self._cursor

    def __repr__(self) -> str:
        return (
            f"<PrefeedShuffle "
            f"active={self.active_len} cursor={self._cursor} "
            f"pending={self.pending_len} "
            f"exploration={self.exploration}>"
        )


# ---------------------------------------------------------------------------
# CAIRRNPrefeedShuffle — integrated scheduler + prefeed
# ---------------------------------------------------------------------------


class CAIRRNPrefeedShuffle:
    """
    CAIRRN-bound prefeed shuffle — CAIRRNScheduler + PrefeedShuffle integrated.

    Owns both the coherence gate and the double-buffer.  The caller only
    needs to call step() on a clock and next() to consume tracks.

    Gate behaviour
    --------------
    step() checks coherence each call:

      coherence < threshold  →  skipped:
          prefeed() is called (background recompute from current shard state)
          _active keeps serving existing tracks — no disruption

      coherence ≥ threshold  →  gated:
          PhiTracerSession.tick() runs (CAIRRN arm scores update harmonic index)
          commit() swaps _pending → _active
          steps_since_tick resets to 0

    Parameters
    ----------
    session      : PhiTracerSession (build() must be called before step())
    exploration  : shuffle variety noise (default 0.15)
    tau          : CAIRRN coherence time constant in steps (default 10.0)
    threshold    : gate threshold — default COHERENCE_THRESHOLD ≈ 0.5671
    refresh_every: auto refresh_and_tick every N successful ticks (0 = off)
    rng_seed     : PrefeedShuffle internal Generator seed (default 7)
    """

    _CODE_SHARDS: tuple[int, int] = (3, 4)

    def __init__(
        self,
        session: PhiTracerSession,
        exploration: float = 0.15,
        tau: float = 10.0,
        threshold: float = COHERENCE_THRESHOLD,
        refresh_every: int = 0,
        rng_seed: int = 7,
    ) -> None:
        self._session = session
        self._tau = max(float(tau), 1e-9)
        self._threshold = float(threshold)
        self._refresh_every = max(0, int(refresh_every))

        self._shuffle = PrefeedShuffle(exploration=exploration, rng_seed=rng_seed)
        self._steps_since_tick: int = 0
        self._ticks_run: int = 0

    # ------------------------------------------------------------------
    # Seed — initial forced prefeed + commit (no coherence gate)
    # ------------------------------------------------------------------

    def seed(self) -> ShufflePeek:
        """
        Bootstrap: force-prefeed and commit immediately.

        Call once after build() to populate the active shuffle before
        the coherence gate has had time to open naturally.

        Returns
        -------
        ShufflePeek of the first 5 active tracks.
        """
        snap = self._session.snapshot
        idx = self._session.harmonic_index
        if snap is None:
            raise RuntimeError(
                "CAIRRNPrefeedShuffle: call session.build() before seed()."
            )
        self._shuffle.prefeed(snap, idx)
        self._shuffle.commit()
        return self._shuffle.peek(5)

    # ------------------------------------------------------------------
    # step — one clock tick
    # ------------------------------------------------------------------

    def step(self) -> ShuffleStepResult:
        """
        One scheduler step.

        Checks coherence, runs prefeed or commit+tick accordingly,
        returns a ShuffleStepResult describing what happened.
        """
        snap = self._session.snapshot
        idx = self._session.harmonic_index
        code_act = self._read_code_activation()
        coherence = 1.0 - math.exp(-self._steps_since_tick / self._tau)

        if coherence < self._threshold:
            # Gate closed — prefeed in background, keep serving _active
            n_prefeeded = self._shuffle.prefeed(snap, idx) if snap else 0
            self._steps_since_tick += 1
            return ShuffleStepResult(
                committed=False,
                prefeeding=True,
                coherence=coherence,
                code_act=code_act,
                steps_waiting=self._steps_since_tick - 1,
                active_len=self._shuffle.active_len,
                pending_len=self._shuffle.pending_len,
            )

        # Gate open — tick the daemon, then commit the prefeeded shuffle
        do_refresh = self._refresh_every > 0 and self._ticks_run > 0 and (
            self._ticks_run % self._refresh_every == 0
        )
        if snap is not None:
            if do_refresh:
                self._session.refresh_and_tick()
            else:
                self._session.tick()
            # Prefeed with fresh shard state post-tick, then commit
            self._shuffle.prefeed(snap, idx)

        committed = self._shuffle.commit()
        self._steps_since_tick = 0
        self._ticks_run += 1

        return ShuffleStepResult(
            committed=committed,
            prefeeding=False,
            coherence=coherence,
            code_act=code_act,
            steps_waiting=0,
            active_len=self._shuffle.active_len,
            pending_len=self._shuffle.pending_len,
        )

    # ------------------------------------------------------------------
    # Consuming tracks
    # ------------------------------------------------------------------

    def next(self) -> int:
        """
        Advance cursor and return the next track index from the active shuffle.

        Call seed() first if no shuffle has been committed yet.
        """
        return self._shuffle.next()

    def peek_active(self, n: int = 5) -> ShufflePeek:
        """
        Peek at the next *n* tracks without consuming them.
        """
        return self._shuffle.peek(n)

    def peek_and_preload(
        self,
        hot_loader: Any,
        n: int = 3,
    ) -> ShufflePeek:
        """
        Peek at the next *n* tracks and register them for hot loading.

        For each upcoming track whose .npy embedding file exists, registers a
        load entry in *hot_loader* and signals it immediately.  By the time
        the shuffle cursor reaches that track, the .npy array is already in RAM.

        This is the CAIRRN-aware "next-song pre-load" contract:
        known outcome (next track) → predetermined load → zero-latency at play.

        Parameters
        ----------
        hot_loader : CAIRRNHotLoader — must be attached to the dispatcher
        n          : number of upcoming tracks to preload (default 3)

        Returns
        -------
        ShufflePeek of the next *n* tracks.
        """
        snap = self._session.snapshot
        if snap is None:
            return ShufflePeek(cursor=0, indices=[], pending_ready=False)

        peek = self._shuffle.peek(n)
        for idx in peek.indices:
            if idx >= snap.N:
                continue
            track = snap.tracks[idx]
            if track.clap_npy is None or not track.clap_npy.exists():
                continue
            hot_key = f"track:{track.path}"
            if hot_loader.is_ready(hot_key):
                continue
            npy_path = track.clap_npy

            import numpy as np
            hot_loader.register_and_signal(
                hot_key,
                load_fn=lambda p=npy_path: np.load(str(p)),
            )
        return peek

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    @property
    def coherence(self) -> float:
        return 1.0 - math.exp(-self._steps_since_tick / self._tau)

    @property
    def gate_open(self) -> bool:
        return self.coherence >= self._threshold

    @property
    def steps_since_commit(self) -> int:
        return self._steps_since_tick

    @property
    def ticks_run(self) -> int:
        return self._ticks_run

    @property
    def shuffle(self) -> PrefeedShuffle:
        """Direct access to the inner PrefeedShuffle buffer."""
        return self._shuffle

    def state(self) -> dict:
        return {
            "coherence":         round(self.coherence, 6),
            "gate_open":         self.gate_open,
            "threshold":         round(self._threshold, 6),
            "tau":               self._tau,
            "steps_since_commit":self._steps_since_tick,
            "ticks_run":         self._ticks_run,
            "active_len":        self._shuffle.active_len,
            "pending_len":       self._shuffle.pending_len,
            "cursor":            self._shuffle.cursor,
            "code_activation":   round(self._read_code_activation(), 6),
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _read_code_activation(self) -> float:
        try:
            shards = self._session.harmonic_index.shards
            vals = [shards[i].activation for i in self._CODE_SHARDS if i < len(shards)]
            return float(sum(vals) / len(vals)) if vals else 0.0
        except Exception:
            return 0.0

    def __repr__(self) -> str:
        return (
            f"<CAIRRNPrefeedShuffle "
            f"ticks={self._ticks_run} "
            f"coherence={self.coherence:.4f} "
            f"gate={'open' if self.gate_open else 'closed'} "
            f"active={self._shuffle.active_len} "
            f"pending={self._shuffle.pending_len}>"
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_prefeed_shuffle(
    session: PhiTracerSession,
    exploration: float = 0.15,
    tau: float = 10.0,
    threshold: float = COHERENCE_THRESHOLD,
    refresh_every: int = 0,
    rng_seed: int = 7,
) -> CAIRRNPrefeedShuffle:
    """
    Construct a CAIRRNPrefeedShuffle bound to *session*.

    Call session.build() before calling seed() or step().

    Parameters
    ----------
    session      : PhiTracerSession
    exploration  : shuffle noise scale (default 0.15 — moderate variety)
    tau          : CAIRRN coherence time constant (default 10.0)
    threshold    : gate open when coherence ≥ threshold (default ≈ 0.5671)
    refresh_every: auto refresh_and_tick every N ticks (0 = manual only)
    rng_seed     : internal rng seed for PrefeedShuffle (default 7)

    Returns
    -------
    CAIRRNPrefeedShuffle
    """
    return CAIRRNPrefeedShuffle(
        session=session,
        exploration=exploration,
        tau=tau,
        threshold=threshold,
        refresh_every=refresh_every,
        rng_seed=rng_seed,
    )
