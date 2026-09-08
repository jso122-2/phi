"""
CAIRRNDispatcher — central CAIRRN-bound action dispatcher for all phi operations.

Architecture
------------
Every phi operation is a PhiAction that enters a priority queue.
The dispatcher owns the coherence gate.  On each step():

    coherence = exp(−steps_since_tick / τ)

    GATE CLOSED (coherence < 0.5671)          GATE OPEN (coherence ≥ 0.5671)
         │                                           │
         ▼                                           ▼
    prefeed(head)                           dequeue by priority
    compute result silently                 execute → may use prefeed
    queue unchanged                         CAIRRN CODE pipeline fires
    steps_since_tick += 1                   steps_since_tick = 0

Prefeedable actions (computed silently while gate builds):
    CLIP        → GeminiClipper runs in background; result cached
    SHUFFLE_NEXT → PrefeedShuffle.prefeed() stages next order

All other actions execute only at gate-open time — no prefeed.

Priority system
---------------
    priority < 0  : urgent  — sorted to front of queue
    priority = 0  : normal  — FIFO within the 0-band
    priority > 0  : deferred — sorted behind normal items

This is the CAIRRN control plane.  All button presses go here.

    Action kinds
    ------------
    CLIP          — query → tracks via GeminiClipper
    SHUFFLE_NEXT  — advance the prefeed shuffle cursor
    SHUFFLE_SEED  — bootstrap / force-commit the shuffle
    HUB_INJECT    — inject activation into a named station hub
    SHARD_INJECT  — inject activation into a specific shard index
    PROPAGATE     — run N harmonic propagation steps
    CAIRRN_RUN    — full 4-layer CAIRRN pipeline for one hub
    TEMPORAL_REC  — record a value to the temporal shard index
    MYCELIAL_TICK — run one mycelial metabolic tick on the substrate
    LOAD_TRACK    — hot-load a track's .npy embedding into the hot cache
    HOVER_PREFETCH— precompute any inner action on cursor-hover signal

    Payload keys per kind
    ---------------------
    CLIP:          query: str, top_k: int = 5, alpha: float = 0.5
    SHUFFLE_NEXT:  (no payload required)
    SHUFFLE_SEED:  (no payload required)
    HUB_INJECT:    hub_name: str, value: float = 1.0
    SHARD_INJECT:  shard_index: int, value: float = 1.0
    PROPAGATE:     steps: int = 1, mode: str = "local"
    CAIRRN_RUN:    hub_name: str, metric: float = 1.0
    TEMPORAL_REC:  hub_name: str, value: float
    MYCELIAL_TICK: budget: float = None (default = scale×N×code_act)
    LOAD_TRACK:    track_path: str (audio path), npy_path: str (.npy path)
    HOVER_PREFETCH:name: str (hot_loader key), kind: str, payload: dict

Usage
-----
    dispatcher = CAIRRNDispatcher(session, shuffle, harmonic_index)

    # Enqueue from any tool / button handler
    dispatcher.enqueue(PhiAction(PhiActionKind.CLIP, {"query": "dark ambient"}))
    dispatcher.enqueue(PhiAction(PhiActionKind.HUB_INJECT, {"hub_name": "CODE", "value": 0.8}))

    # Clock tick (call from a loop or on-demand)
    result = dispatcher.step()

    # Inspect
    state = dispatcher.state()
"""

from __future__ import annotations

import asyncio
import bisect
import math
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Deque, Optional

from engine.gate import COHERENCE_THRESHOLD
from engine.hot_loader import CAIRRNHotLoader
from workers.cairrn._constants import _HUB_PRIMARY_SHARD
from workers.cairrn.formulas import f_css, f_m3, f_composite_health_horizon


# ---------------------------------------------------------------------------
# Prefeed quality gate
# ---------------------------------------------------------------------------

# M3 ≤ threshold → pending shuffle order accepted; M3 > threshold → discard + retry.
# Lower = stricter.  1.0 is the calibrated default; raise during exploration phases.
M3_THRESHOLD: float = 1.0

# Ψ′ composite health horizon — number of tick windows in the summation.
# Matches the harmonic ring width (8 shards) so the composite memory horizon
# equals the ring propagation diameter.
_N_WINDOWS: int = 8

# Shard indices derived from hub → primary shard map (Ana-Chi basis).
# HOME→0  MATH→1  CODE→3  COMMANDS→5  agent-context→6
_SHARD_MATH     = _HUB_PRIMARY_SHARD["MATH"]       # 1 — basin 3.92
_SHARD_MATH_SEC = _SHARD_MATH + 1                  # 2 — basin 5.88 (MATH secondary, h2 proxy)
_SHARD_CODE     = _HUB_PRIMARY_SHARD["CODE"]       # 3 — basin 7.84
_SHARD_COMMANDS = _HUB_PRIMARY_SHARD["COMMANDS"]   # 5 — basin 11.76


def _compute_m3(
    pfs_score: float,
    n: int,
    activations: list[float],
) -> float:
    """
    M3 = |CSS| · N · |FastFormula − SHI|

    Proxy evaluation of the prefeed quality gate using harmonic shard
    activations as stand-ins for full DAWN state variables.

    Shard indices are sourced from _HUB_PRIMARY_SHARD — not hardcoded:
        e2  = activations[MATH primary]     basin 3.92
        h2  = activations[MATH secondary]²  basin 5.88 — height-squared proxy
        e1  = activations[CODE primary]     basin 7.84 — normalization floor
        e5  = activations[COMMANDS primary] basin 11.76
        SHI = mean(activations)             all-shard health proxy

    Parameters
    ----------
    pfs_score : mean harmonic resonance score from prefeed() (FastFormula)
    n         : track count from prefeed()
    activations : list of 8 shard activation values from HarmonicIndex
    """
    n_shards = len(activations)
    e2 = activations[_SHARD_MATH]     if n_shards > _SHARD_MATH     else 0.0
    h2 = activations[_SHARD_MATH_SEC] ** 2 if n_shards > _SHARD_MATH_SEC else 0.0
    e1 = activations[_SHARD_CODE]     if n_shards > _SHARD_CODE     else 1.0
    e5 = activations[_SHARD_COMMANDS] if n_shards > _SHARD_COMMANDS else 0.0
    shi = sum(activations) / max(n_shards, 1)

    # CSS proxy: a_nw=1.0, delta=pfs_score, cc=pfs_score, z_prev=1.0, z=1.0,
    # tcv=1.0, scop=1.0 — all set to neutral when session state is unavailable.
    css = f_css(
        a_nw=1.0,
        delta=pfs_score,
        cc=pfs_score,
        z_prev=1.0,
        z=1.0,
        tcv=1.0,
        scop=1.0,
        e2=e2,
        h2=h2,
        e5=e5,
        e1=e1,
    )
    return f_m3(css=css, n=n, fast_formula=pfs_score, shi=shi)


# ---------------------------------------------------------------------------
# Action kinds
# ---------------------------------------------------------------------------


class PhiActionKind(str, Enum):
    CLIP           = "CLIP"
    SHUFFLE_NEXT   = "SHUFFLE_NEXT"
    SHUFFLE_SEED   = "SHUFFLE_SEED"
    HUB_INJECT     = "HUB_INJECT"
    SHARD_INJECT   = "SHARD_INJECT"
    PROPAGATE      = "PROPAGATE"
    CAIRRN_RUN     = "CAIRRN_RUN"
    TEMPORAL_REC   = "TEMPORAL_REC"
    MYCELIAL_TICK  = "MYCELIAL_TICK"
    # Hot-load kinds — results precomputed in background before the action fires
    LOAD_TRACK     = "LOAD_TRACK"     # preload .npy embedding into hot cache
    HOVER_PREFETCH = "HOVER_PREFETCH" # precompute any inner action on hover signal


# Actions prefeed-computable while gate is building
_PREFEEDABLE: frozenset[PhiActionKind] = frozenset({
    PhiActionKind.CLIP,
    PhiActionKind.SHUFFLE_NEXT,
    PhiActionKind.LOAD_TRACK,
    PhiActionKind.HOVER_PREFETCH,
})


# ---------------------------------------------------------------------------
# PhiAction
# ---------------------------------------------------------------------------


@dataclass
class PhiAction:
    """
    One phi operation enqueued in the CAIRRN dispatcher.

    Parameters
    ----------
    kind     : which operation this is
    payload  : key-value args for the operation (see module docstring)
    priority : sort key — negative = urgent, 0 = normal, positive = deferred

    Internal (managed by dispatcher — do not set):
    action_id      : unique identifier
    enqueued_at    : monotonic timestamp at enqueue time
    """

    kind: PhiActionKind
    payload: dict[str, Any] = field(default_factory=dict)
    priority: int = 0

    # Dispatcher-managed — set at enqueue time
    action_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    enqueued_at: float = field(default_factory=time.monotonic)

    def as_dict(self) -> dict:
        return {
            "action_id":   self.action_id,
            "kind":        self.kind.value,
            "priority":    self.priority,
            "payload":     self.payload,
            "enqueued_at": round(self.enqueued_at, 4),
        }


# ---------------------------------------------------------------------------
# DispatchResult
# ---------------------------------------------------------------------------


@dataclass
class DispatchResult:
    """
    Outcome of one CAIRRNDispatcher.step() call.

    gated           : True if gate was open and an action was executed
    skipped         : True if gate was closed (prefeed may have run)
    coherence       : gate coherence value at step time
    code_act        : mean CODE hub (shard 3 + 4) activation — gate signal
    steps_waiting   : steps_since_tick before this call
    action          : the action that was dispatched (None if queue was empty)
    result          : execution result — kind-specific (dict for most, int for SHUFFLE_NEXT)
    prefeed_was_ready: True if result came from the prefeed cache (zero-latency)
    prefeeding      : True if a prefeed computation ran this step (gate was closed)
    queue_depth     : queue depth after this step
    """

    gated: bool
    skipped: bool
    coherence: float
    code_act: float
    steps_waiting: int
    action: Optional[PhiAction]
    result: Optional[Any]
    prefeed_was_ready: bool
    prefeeding: bool
    queue_depth: int

    def as_dict(self) -> dict:
        d = {
            "gated":            self.gated,
            "skipped":          self.skipped,
            "coherence":        round(self.coherence, 6),
            "code_act":         round(self.code_act, 6),
            "steps_waiting":    self.steps_waiting,
            "prefeed_was_ready":self.prefeed_was_ready,
            "prefeeding":       self.prefeeding,
            "queue_depth":      self.queue_depth,
        }
        if self.action is not None:
            d["action"] = self.action.as_dict()
        if self.result is not None:
            d["result"] = self.result if isinstance(self.result, (dict, list, str, int, float, bool)) else str(self.result)
        return d


# ---------------------------------------------------------------------------
# Pericles-bound Euler watchdog — double-route event detector
# ---------------------------------------------------------------------------


@dataclass
class DoubleRouteEvent:
    """
    Immutable record of one DOUBLE_ROUTE detection.

    Fields
    ------
    kind        : PhiActionKind value that fired twice
    dt_ms       : milliseconds between the two fires
    coherence   : dispatcher coherence at time of second fire
    euler_bound : True when coherence < W(1) — fired inside the Euler boundary
    per         : Pericles score — lower = events more suspiciously close
    k           : Pericles k  (coherence at dispatch)
    N_j         : Pericles N_j (queue depth)
    D           : Pericles D  (steps_waiting — attractor distance proxy)
    x           : Pericles denominator floor  max(|k·N_j|, D, ε)
    at          : monotonic timestamp of second fire
    total       : running count of all double-route events ever seen
    """
    kind:        str
    dt_ms:       float
    coherence:   float
    euler_bound: bool
    per:         float
    k:           float
    N_j:         float
    D:           float
    x:           float
    at:          float
    total:       int

    def as_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items()}


class DoubleRouteWatchdog:
    """
    Pericles-bound, Euler-gated race-condition watchdog for CAIRRNDispatcher.

    Detects when the same PhiActionKind is dispatched twice within
    ``window_ms`` milliseconds (a DOUBLE_ROUTE event) and scores each
    detection using the Pericles formula.

    Pericles score
    --------------
        per = dt · k / x
        x   = max(|k · N_j|, D, 1e-12)

    Where:
        dt  — elapsed seconds between the two fires (smaller = more suspicious)
        k   — coherence at moment of second fire  (TF-IDF weight analogue)
        N_j — queue depth at dispatch time          (document-length proxy)
        D   — steps_waiting                         (attractor-distance proxy)

    A low ``per`` score means the events are suspiciously close relative to
    the system's current coherence and queue state — a confirmed DOUBLE_ROUTE.

    Euler bound
    -----------
    ``event.euler_bound = True`` when ``coherence < W(1)`` at dispatch time.
    Events inside the Euler boundary fired while the gate was closed;
    these are the highest-priority race conditions to resolve.

    Usage
    -----
        watchdog = DoubleRouteWatchdog(dispatcher, window_ms=450.0)
        dispatcher.attach_double_route_watchdog(watchdog)
        # … run dispatcher …
        state = watchdog.state()   # or import into DAWN as phi.cairrn.watchdog
    """

    def __init__(
        self,
        dispatcher: "CAIRRNDispatcher",
        *,
        window_ms: float = 450.0,
        max_events: int = 200,
    ) -> None:
        self._dispatcher = dispatcher
        self._window     = window_ms / 1000.0
        self._max_events = max_events

        self._last_exec: dict[str, float] = {}        # kind.value → monotonic ts
        self._events: list[DoubleRouteEvent] = []
        self._lock = threading.Lock()

    # ------------------------------------------------------------------

    def observe(self, result: "DispatchResult") -> None:
        """
        Inspect one DispatchResult.

        Called by the dispatcher *after* each step() / force_dispatch()
        completes and outside the dispatcher's internal RLock — no lock
        contention introduced.
        """
        if result.action is None:
            return

        kind_str = result.action.kind.value
        now = time.monotonic()

        with self._lock:
            last = self._last_exec.get(kind_str)
            self._last_exec[kind_str] = now

            if last is None:
                return

            dt = now - last
            if dt > self._window:
                return

            # Pericles formula
            k   = result.coherence
            N_j = float(max(result.queue_depth, 1))
            D   = float(max(result.steps_waiting, 1))
            x   = max(abs(k * N_j), D, 1e-12)
            per = dt * k / x

            total = len(self._events) + 1
            event = DoubleRouteEvent(
                kind        = kind_str,
                dt_ms       = round(dt * 1000, 1),
                coherence   = round(k, 6),
                euler_bound = k < COHERENCE_THRESHOLD,
                per         = round(per, 6),
                k           = round(k, 6),
                N_j         = N_j,
                D           = D,
                x           = round(x, 6),
                at          = round(now, 6),
                total       = total,
            )
            self._events.append(event)
            if len(self._events) > self._max_events:
                self._events = self._events[-self._max_events:]

    def state(self) -> dict[str, Any]:
        """Serialisable snapshot — safe to call from any thread."""
        with self._lock:
            return {
                "window_ms":         round(self._window * 1000, 1),
                "total_events":      len(self._events),
                "euler_bound_count": sum(1 for e in self._events if e.euler_bound),
                "recent":            [e.as_dict() for e in self._events[-10:]],
            }

    def observe_song_transition(
        self,
        queue_pos: int,
        dt_ms: float,
        coherence: float = 0.0,
        steps_waiting: int = 1,
        queue_depth: int = 0,
    ) -> None:
        """
        Record a DOUBLE_ADVANCE song-transition race event.

        Call from PhiRaceWatcher.on_advance() whenever DOUBLE_ADVANCE fires.
        Scores the event with the Pericles formula so song-transition races
        appear alongside dispatcher races in watchdog state().

        Parameters
        ----------
        queue_pos    : queue position that fired twice
        dt_ms        : elapsed ms between the two advance calls
        coherence    : CAIRRN dispatcher coherence at detection time (0.0 if unknown)
        steps_waiting: dispatcher steps_since_tick (1 if unknown)
        queue_depth  : dispatcher queue depth (0 if unknown)
        """
        kind_str = f"SONG_ADVANCE@{queue_pos}"
        now = time.monotonic()

        with self._lock:
            dt  = dt_ms / 1000.0
            k   = max(coherence, 1e-9)
            N_j = float(max(queue_depth, 1))
            D   = float(max(steps_waiting, 1))
            x   = max(abs(k * N_j), D, 1e-12)
            per = dt * k / x

            total = len(self._events) + 1
            event = DoubleRouteEvent(
                kind        = kind_str,
                dt_ms       = round(dt_ms, 1),
                coherence   = round(coherence, 6),
                euler_bound = coherence < COHERENCE_THRESHOLD,
                per         = round(per, 6),
                k           = round(k, 6),
                N_j         = N_j,
                D           = D,
                x           = round(x, 6),
                at          = round(now, 6),
                total       = total,
            )
            self._events.append(event)
            if len(self._events) > self._max_events:
                self._events = self._events[-self._max_events:]

    def clear(self) -> None:
        """Reset all recorded events and per-kind last-exec timestamps."""
        with self._lock:
            self._events.clear()
            self._last_exec.clear()


# ---------------------------------------------------------------------------
# CAIRRNDispatcher
# ---------------------------------------------------------------------------


class CAIRRNDispatcher:
    """
    Central CAIRRN-bound action dispatcher for all phi operations.

    Parameters
    ----------
    harmonic_index  : live HarmonicIndex — used to read CODE hub activation
                      and to execute SHARD_INJECT / HUB_INJECT / PROPAGATE
    session         : optional PhiTracerSession — required for CLIP, SHUFFLE_*
    shuffle         : optional CAIRRNPrefeedShuffle — required for SHUFFLE_*
    temporal_index  : optional TemporalShardIndex — required for TEMPORAL_REC
    tau             : CAIRRN coherence time constant in steps (default 10.0)
    threshold       : gate-open threshold (default COHERENCE_THRESHOLD ≈ 0.5671)
    max_history     : bounded ring for dispatch history (default 100)
    """

    _CODE_SHARDS: tuple[int, int] = (3, 4)

    def __init__(
        self,
        harmonic_index: Any,
        session: Optional[Any] = None,
        shuffle: Optional[Any] = None,
        temporal_index: Optional[Any] = None,
        substrate: Optional[Any] = None,
        hot_loader: Optional[CAIRRNHotLoader] = None,
        forest_floor: Optional[Any] = None,
        tau: float = 10.0,
        threshold: float = COHERENCE_THRESHOLD,
        max_history: int = 100,
    ) -> None:
        self._index = harmonic_index
        self._session = session
        self._shuffle = shuffle
        self._temporal = temporal_index
        self._substrate = substrate      # MycelialSubstrate — attached after construction
        self._hot_loader = hot_loader    # CAIRRNHotLoader — hot cache for all prefetchable actions
        self._forest_floor = forest_floor  # ForestFloor — attached after construction (or via attach_forest_floor)
        self._player: Optional[Any] = None  # PhiPlayer — attached after construction
        self._dr_watchdog: Optional[DoubleRouteWatchdog] = None  # attached after construction
        self._tau = max(float(tau), 1e-9)
        self._threshold = float(threshold)
        self._max_history = max_history

        # Priority queue: list kept sorted by (priority, enqueued_at) on insert
        self._queue: list[PhiAction] = []
        # Prefeed cache: action_id → precomputed result
        self._prefeed_cache: dict[str, Any] = {}

        self._steps_since_tick: int = 0
        self._ticks_run: int = 0
        self._total_enqueued: int = 0
        self._history: Deque[DispatchResult] = deque(maxlen=max_history)
        self._last_health_horizon: float = float("inf")  # Ti* — updated by _prefeed_shuffle_next

        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # Enqueue
    # ------------------------------------------------------------------

    def enqueue(self, action: PhiAction) -> int:
        """
        Add an action to the priority queue.

        Maintains sort order: lower priority number = dispatched sooner.
        Within the same priority, FIFO order is preserved via enqueued_at.

        Uses bisect.insort (O(log n) search + O(n) shift) instead of
        full sort (O(n log n)) on every call — faster for small queues
        and avoids O(n log n) overhead at larger depths.

        Returns the new queue depth.
        """
        with self._lock:
            bisect.insort(
                self._queue,
                action,
                key=lambda a: (a.priority, a.enqueued_at),
            )
            self._total_enqueued += 1
            return len(self._queue)

    # ------------------------------------------------------------------
    # Step
    # ------------------------------------------------------------------

    def step(self) -> DispatchResult:
        """
        One dispatcher clock tick.

        Checks coherence → prefeed or dispatch → return DispatchResult.
        Thread-safe: the RLock is held only for the core tick logic.
        The double-route watchdog observe() is called *after* releasing
        the lock so it introduces zero contention on the critical path.
        """
        with self._lock:
            # Hot loader runs every step — gate state does not matter.
            if self._hot_loader is not None:
                self._hot_loader.step()

            code_act  = self._read_code_activation()
            coherence = 1.0 - math.exp(-self._steps_since_tick / self._tau)

            if coherence < self._threshold:
                # Gate closed — prefeed the head of queue if possible
                prefeeding = False
                if self._queue:
                    head = self._queue[0]
                    if head.kind in _PREFEEDABLE and head.action_id not in self._prefeed_cache:
                        self._prefeed(head)
                        prefeeding = True

                self._steps_since_tick += 1
                result = DispatchResult(
                    gated=False, skipped=True,
                    coherence=coherence, code_act=code_act,
                    steps_waiting=self._steps_since_tick - 1,
                    action=None, result=None,
                    prefeed_was_ready=False, prefeeding=prefeeding,
                    queue_depth=len(self._queue),
                )
            else:
                # Gate open — dequeue next action (if any) and execute
                action: Optional[PhiAction] = None
                exec_result: Optional[Any] = None
                prefeed_was_ready = False

                if self._queue:
                    action = self._queue.pop(0)
                    prefeed_was_ready = action.action_id in self._prefeed_cache
                    exec_result = self._execute(action)
                    self._prefeed_cache.pop(action.action_id, None)

                # Always run the CAIRRN CODE hub step on gate-open to update shards
                self._run_cairrn_code_tick()

                self._steps_since_tick = 0
                self._ticks_run += 1

                result = DispatchResult(
                    gated=True, skipped=False,
                    coherence=coherence, code_act=code_act,
                    steps_waiting=0,
                    action=action, result=exec_result,
                    prefeed_was_ready=prefeed_was_ready, prefeeding=False,
                    queue_depth=len(self._queue),
                )

            self._history.append(result)

        # Watchdog observe runs outside the RLock — zero contention
        if self._dr_watchdog is not None:
            self._dr_watchdog.observe(result)

        return result

    # ------------------------------------------------------------------
    # Force dispatch (bypass gate)
    # ------------------------------------------------------------------

    def force_dispatch(self, action: PhiAction) -> DispatchResult:
        """
        Execute an action immediately, bypassing the coherence gate.

        Use for urgent operations where latency matters more than coherence.
        Does NOT update steps_since_tick or run the CAIRRN CODE tick.
        The double-route watchdog observe() runs after releasing the lock.
        """
        with self._lock:
            code_act = self._read_code_activation()
            coherence = 1.0 - math.exp(-self._steps_since_tick / self._tau)
            exec_result = self._execute(action)
            result = DispatchResult(
                gated=True, skipped=False,
                coherence=coherence, code_act=code_act,
                steps_waiting=self._steps_since_tick,
                action=action, result=exec_result,
                prefeed_was_ready=False, prefeeding=False,
                queue_depth=len(self._queue),
            )
            self._history.append(result)

        if self._dr_watchdog is not None:
            self._dr_watchdog.observe(result)

        return result

    # ------------------------------------------------------------------
    # App-resume credit
    # ------------------------------------------------------------------

    def on_resume(
        self,
        idle_s: float = 0.0,
        tick_interval_s: float = 1.0,
    ) -> None:
        """
        Credit idle time back to the dispatcher on app activation or page navigation.

        Two effects:
          1. Step credit  — converts elapsed idle seconds to equivalent step count
             so coherence appears "warm" when the user returns.  Capped at τ×5
             (coherence ≈ 1 − e⁻⁵ ≈ 0.993) to avoid overshooting.  Pass
             idle_s=0 to skip step credit (useful when only the soot-ash
             reset matters on a navigation-triggered call).
          2. Soot-ash reset — clears any stale volatility bookkeeping so the
             first user action after idle does not inherit a penalising state
             from background ring activity.

        Parameters
        ----------
        idle_s          : seconds the app was in the background / inactive.
        tick_interval_s : expected seconds between dispatcher ticks.
                          Qt  default = 1.0 s (CairnTick fires every 10 × POLL_MS)
                          pygame default = 0.15 s (run_tick_loop interval_s)
        """
        with self._lock:
            if idle_s > 0.0:
                interval   = max(tick_interval_s, 1e-3)
                idle_steps = int(idle_s / interval)
                cap        = int(self._tau * 5)   # coherence ≈ 0.993 at τ×5
                self._steps_since_tick = min(
                    self._steps_since_tick + idle_steps,
                    cap,
                )
            # Nothing to reset in this build (no tau-stretch / shimmer machinery).
            # Subclasses or future builds that carry those fields should clear
            # them here.

    # ------------------------------------------------------------------
    # Async variants (awaitable from async event loops)
    # ------------------------------------------------------------------

    async def astep(self) -> DispatchResult:
        """
        Async variant of step().

        Runs step() in a thread-pool executor so the calling coroutine
        yields the event loop while the dispatcher tick executes.
        Thread-safe: step() still holds the internal RLock.
        """
        return await asyncio.to_thread(self.step)

    async def aforce_dispatch(self, action: PhiAction) -> DispatchResult:
        """
        Async variant of force_dispatch().

        Runs force_dispatch(action) in a thread-pool executor.
        """
        return await asyncio.to_thread(self.force_dispatch, action)

    async def aenqueue(self, action: PhiAction) -> int:
        """
        Async variant of enqueue().

        enqueue() is fast (list sort only) but provided as a coroutine
        for callers that want a uniform async API.
        """
        return await asyncio.to_thread(self.enqueue, action)

    async def run_tick_loop(
        self,
        interval_s: float = 0.25,
        stop_event: Optional[asyncio.Event] = None,
    ) -> None:
        """
        Drive the dispatcher at a fixed cadence from an async context.

        Spawn this as a background task once; it owns all step() calls.
        The render loop must NOT call step() directly — that is the source
        of render/CAIRRN lock contention.

        Parameters
        ----------
        interval_s : seconds between ticks (default 0.25 → 4 Hz)
        stop_event : asyncio.Event — set externally to terminate cleanly

        Example
        -------
            stop = asyncio.Event()
            tick_task = asyncio.create_task(
                dispatcher.run_tick_loop(interval_s=0.25, stop_event=stop)
            )
            # ... run your render loop ...
            stop.set()
            await tick_task
        """
        while stop_event is None or not stop_event.is_set():
            await self.astep()
            await asyncio.sleep(interval_s)

    # ------------------------------------------------------------------
    # State inspection
    # ------------------------------------------------------------------

    @property
    def coherence(self) -> float:
        """
        Joint CAIRRN gate coherence — Euler-bound.

        Returns min(exp_decay, temporal_euler_coherence) when a temporal index
        is attached.  This binds the dispatcher gate to both:
          • Temporal relaxation  — exp(−steps_since_tick / τ)  rebuilds after
            each gate-open event.
          • Euler coherence       — temporal.ana_chi_coherence() tracks whether
            hub activation is centred on HOME (true_center, χ=1.5414).

        The gate only opens when BOTH signals are above COHERENCE_THRESHOLD
        (≈ 0.5671 = |−W(1)|).  A burst into COMMANDS or MATH drops Euler
        coherence below the floor and closes the gate until the activity
        decays back toward HOME — preventing spurious SHUFFLE_NEXT /
        SONG_ADVANCE dispatches during high-load song transitions.

        Falls back to pure exp_decay when no temporal index is attached.
        """
        exp_coh = 1.0 - math.exp(-self._steps_since_tick / self._tau)
        if self._temporal is not None:
            try:
                euler_coh = self._temporal.ana_chi_coherence()
                return min(exp_coh, euler_coh)
            except Exception:
                pass
        return exp_coh

    @property
    def gate_open(self) -> bool:
        """Open only when Euler-coherence is above W(1) and Ψ′ horizon is intact.

        ``f_composite_health_horizon`` (Ti*) is the desktop composite's safe
        tick ceiling. Past that boundary the gate stays closed and prefeed
        keeps running — same house as M3 discarding a bad shuffle.
        """
        if self.coherence < self._threshold:
            return False
        ti_star = self._last_health_horizon
        if ti_star != float("inf") and self._steps_since_tick > ti_star:
            return False
        return True

    @property
    def queue_depth(self) -> int:
        with self._lock:
            return len(self._queue)

    @property
    def ticks_run(self) -> int:
        return self._ticks_run

    @property
    def steps_since_tick(self) -> int:
        return self._steps_since_tick

    def queue_snapshot(self) -> list[dict]:
        """Serialisable snapshot of the current queue (ordered)."""
        with self._lock:
            return [a.as_dict() for a in self._queue]

    def history_snapshot(self, n: int = 10) -> list[dict]:
        """Last *n* dispatch results."""
        with self._lock:
            recent = list(self._history)[-n:]
        return [r.as_dict() for r in recent]

    def attach_forest_floor(self, floor: Any) -> None:
        """
        Attach a live ForestFloor to this dispatcher.

        When attached, every gate-open CODE tick echoes into the floor's
        CairnBridge so the two CAIRRN planes stay in sync.  Also enables
        IPC-independent coherence reading in ``_read_code_activation()``.

        Can be called after construction — e.g. once PhiApp finishes init.
        Thread-safe: acquires the internal lock.
        """
        with self._lock:
            self._forest_floor = floor

    def attach_substrate(self, substrate: Any) -> None:
        """
        Attach a MycelialSubstrate to this dispatcher.

        Can be called after construction (e.g. once PhiGraph.build() completes).
        Thread-safe: acquires the internal lock.
        """
        with self._lock:
            self._substrate = substrate

    def attach_player(self, player: Any) -> None:
        """
        Attach a PhiPlayer so SHUFFLE_NEXT / SHUFFLE_SEED write back player state.

        Once attached, bus-driven shuffle advances update player._current_track,
        player._current_idx, player._current_start, and player._in_play directly.
        The UI poll loop then reads current_track with zero extra latency.

        Call this after both dispatcher and player are constructed — see
        make_phi_pipeline() in phi_player.py.
        Thread-safe: acquires the internal lock.
        """
        with self._lock:
            self._player = player

    def attach_double_route_watchdog(self, watchdog: DoubleRouteWatchdog) -> None:
        """
        Attach a DoubleRouteWatchdog to monitor this dispatcher for race conditions.

        The watchdog's observe() is called after every step() and force_dispatch(),
        outside the internal RLock — no added contention.

        Example
        -------
            watchdog = DoubleRouteWatchdog(dispatcher, window_ms=450.0)
            dispatcher.attach_double_route_watchdog(watchdog)
        """
        with self._lock:
            self._dr_watchdog = watchdog

    def attach_hot_loader(self, hot_loader: CAIRRNHotLoader) -> None:
        """
        Attach a CAIRRNHotLoader.

        All hot-loadable actions (LOAD_TRACK, HOVER_PREFETCH) use this loader
        for speculative prefetch.  Can be called after construction.
        Thread-safe.
        """
        with self._lock:
            self._hot_loader = hot_loader

    def signal_hover(self, name: str, load_fn: Any = None) -> bool:
        """
        Signal that the cursor is hovering over a named action (e.g. a button).

        If the hot loader has an entry for *name*, it is marked pending and
        its load_fn fires on the next step() — zero-latency result by click time.

        If there is no entry yet and *load_fn* is provided, the entry is
        registered + signaled immediately (one-shot hover prefetch).

        Parameters
        ----------
        name    : hot_loader key — convention "hover:<button_id>"
        load_fn : optional Callable[[], Any] — required if entry not yet registered

        Returns
        -------
        True  : signal accepted (entry exists or was just registered)
        False : no hot_loader attached, or no load_fn provided for unknown entry
        """
        with self._lock:
            hl = self._hot_loader
        if hl is None:
            return False
        if hl.signal(name):
            return True
        if load_fn is not None:
            hl.register_and_signal(name, load_fn)
            return True
        return False

    def state(self) -> dict:
        with self._lock:
            _ti_star = self._last_health_horizon
            d: dict = {
                "coherence":        round(self.coherence, 6),
                "gate_open":        self.gate_open,
                "threshold":        round(self._threshold, 6),
                "tau":              self._tau,
                "steps_since_tick": self._steps_since_tick,
                "ticks_run":        self._ticks_run,
                "total_enqueued":   self._total_enqueued,
                "queue_depth":      len(self._queue),
                "prefeed_cached":   len(self._prefeed_cache),
                "code_activation":  round(self._read_code_activation(), 6),
                # Ti* — Ψ′ health horizon.  Compare against steps_since_tick:
                # if steps_since_tick > health_horizon, the composite has gone negative
                # and the system is past its safe tick-interval boundary.
                "health_horizon":   round(_ti_star, 4) if _ti_star != float("inf") else "inf",
                "past_health_boundary": (
                    False if _ti_star == float("inf")
                    else self._steps_since_tick > _ti_star
                ),
                "queue":            [a.as_dict() for a in self._queue],
            }
            if self._substrate is not None:
                d["mycelial"] = self._substrate.state()
            if self._hot_loader is not None:
                d["hot_loader"] = self._hot_loader.summary()
            return d

    # ------------------------------------------------------------------
    # Internal: prefeed
    # ------------------------------------------------------------------

    def _prefeed(self, action: PhiAction) -> None:
        """
        Precompute the result for an action while the gate is building.

        Writes to self._prefeed_cache[action.action_id].
        Silently no-ops if the required subsystem is not available.
        """
        try:
            if action.kind == PhiActionKind.CLIP:
                self._prefeed_clip(action)
            elif action.kind == PhiActionKind.SHUFFLE_NEXT:
                self._prefeed_shuffle_next(action)
            elif action.kind == PhiActionKind.LOAD_TRACK:
                self._prefeed_load_track(action)
            elif action.kind == PhiActionKind.HOVER_PREFETCH:
                self._prefeed_hover(action)
        except Exception:
            pass  # prefeed failures are non-fatal — execute will recompute

    def _prefeed_clip(self, action: PhiAction) -> None:
        if self._session is None:
            return
        snap = self._session.snapshot
        if snap is None:
            return

        # Capture all inputs under the lock before releasing
        query     = action.payload.get("query", "")
        top_k     = int(action.payload.get("top_k", 5))
        alpha     = float(action.payload.get("alpha", 0.5))
        proj      = self._session.phi_graph._proj
        encoder   = self._session.phi_graph._encoder
        action_id = action.action_id

        # Release the RLock during neural inference — clipper.clip() can take
        # hundreds of milliseconds and must not hold the dispatcher lock.
        self._lock.release()
        try:
            from phi.models.gemini_clipper import GeminiClipper
            clipper = GeminiClipper(proj=proj, encoder=encoder, top_k=top_k, alpha=alpha)
            result = clipper.clip(query, snap)
        finally:
            self._lock.acquire()

        self._prefeed_cache[action_id] = result

    def _prefeed_shuffle_next(self, action: PhiAction) -> None:
        if self._shuffle is None:
            return
        snap = self._shuffle._session.snapshot if hasattr(self._shuffle, "_session") else None
        if snap is None:
            return

        # Capture locals before releasing — avoids attribute access under the lock
        shuffle   = self._shuffle.shuffle
        index     = self._index
        action_id = action.action_id

        # Release the RLock during O(N) gravity-vector computation so enqueue()
        # and force_dispatch() are never blocked for the duration of prefeed().
        self._lock.release()
        try:
            n, pfs_score = shuffle.prefeed(snap, index)
        finally:
            self._lock.acquire()

        # M3 quality gate — accept only when the pending order is SHI-coherent.
        # High M3 means the harmonic resonance is far from the health baseline;
        # discard and let the next closed-gate step retry with fresher state.
        activations = [s.activation for s in index.shards]
        m3 = _compute_m3(pfs_score, n, activations)

        # Ti* health horizon — max tick interval before the Ψ′ composite goes negative.
        # Uses pfs_score as the confidence proxy (x) and the mean shard activation as
        # energy (e) and global friction (g) proxies.  Stored so callers can inspect
        # whether the current step count has crossed the health boundary.
        shi_proxy    = sum(activations) / max(len(activations), 1)
        e2_val       = activations[_SHARD_MATH] if len(activations) > _SHARD_MATH else 0.0
        g_proxy      = abs(e2_val - shi_proxy)    # |MATH shard energy − mean| as friction gap
        health_ti    = float(self._steps_since_tick) if hasattr(self, "_steps_since_tick") else 0.0
        ti_star      = f_composite_health_horizon(
            z=pfs_score, x=pfs_score, e=shi_proxy,
            g=g_proxy, n_windows=_N_WINDOWS, ti=health_ti,
        )
        self._last_health_horizon = ti_star     # expose for state() inspection

        if m3 <= M3_THRESHOLD:
            self._prefeed_cache[action_id] = "__prefeed_done__"
        # else: action stays at queue head; prefeed retries next step

    def _prefeed_load_track(self, action: PhiAction) -> None:
        """
        Register LOAD_TRACK into the hot loader while gate is building.

        The .npy load runs in a background thread via CAIRRNHotLoader so it
        is ready by the time the gate opens and the action executes.
        """
        if self._hot_loader is None:
            return
        p = action.payload
        npy_path = str(p.get("npy_path", ""))
        track_path = str(p.get("track_path", npy_path))
        if not npy_path:
            return
        hot_key = f"track:{track_path}"
        if not self._hot_loader.is_ready(hot_key):
            import numpy as np
            self._hot_loader.register_and_signal(
                hot_key,
                load_fn=lambda p=npy_path: np.load(p),
            )
        # Sentinel so execute knows prefeed was delegated to hot loader
        self._prefeed_cache[action.action_id] = f"__hot:{hot_key}__"

    def _prefeed_hover(self, action: PhiAction) -> None:
        """
        Precompute a HOVER_PREFETCH inner action while gate is building.

        Registers the inner action result in the hot loader so execute()
        hits the cache at zero latency when the gate opens.
        """
        if self._hot_loader is None:
            return
        p = action.payload
        name = str(p.get("name", ""))
        hot_key = f"hover:{name}"
        if self._hot_loader.is_ready(hot_key):
            self._prefeed_cache[action.action_id] = f"__hot:{hot_key}__"
            return

        inner_kind_str = str(p.get("kind", ""))
        inner_payload = dict(p.get("payload", {}))
        try:
            inner_kind = PhiActionKind(inner_kind_str)
        except ValueError:
            return

        inner_action = PhiAction(kind=inner_kind, payload=inner_payload)

        def _compute(a=inner_action) -> Any:
            return self._execute(a)

        self._hot_loader.register_and_signal(hot_key, load_fn=_compute)
        self._prefeed_cache[action.action_id] = f"__hot:{hot_key}__"

    # ------------------------------------------------------------------
    # Internal: execute
    # ------------------------------------------------------------------

    def _execute(self, action: PhiAction) -> Any:
        """
        Execute one action, using prefeed cache when available.

        Returns the raw result — callers serialise as needed.
        """
        kind = action.kind
        p = action.payload

        if kind == PhiActionKind.CLIP:
            return self._exec_clip(action)

        if kind == PhiActionKind.SHUFFLE_NEXT:
            return self._exec_shuffle_next(action)

        if kind == PhiActionKind.SHUFFLE_SEED:
            return self._exec_shuffle_seed()

        if kind == PhiActionKind.HUB_INJECT:
            return self._exec_hub_inject(p)

        if kind == PhiActionKind.SHARD_INJECT:
            return self._exec_shard_inject(p)

        if kind == PhiActionKind.PROPAGATE:
            return self._exec_propagate(p)

        if kind == PhiActionKind.CAIRRN_RUN:
            return self._exec_cairrn_run(p)

        if kind == PhiActionKind.TEMPORAL_REC:
            return self._exec_temporal_rec(p)

        if kind == PhiActionKind.MYCELIAL_TICK:
            return self._exec_mycelial_tick(p)

        if kind == PhiActionKind.LOAD_TRACK:
            return self._exec_load_track(action)

        if kind == PhiActionKind.HOVER_PREFETCH:
            return self._exec_hover_prefetch(action)

        return {"error": f"unknown_kind: {kind}"}

    def _exec_clip(self, action: PhiAction) -> dict:
        cached = self._prefeed_cache.get(action.action_id)
        p = action.payload

        if cached is not None and cached != "__prefeed_done__":
            # Prefeed result available — return immediately (zero latency)
            result = cached
        else:
            if self._session is None:
                return {"error": "session_not_available"}
            snap = self._session.snapshot
            if snap is None:
                return {"error": "snapshot_not_built"}
            from phi.models.gemini_clipper import GeminiClipper
            clipper = GeminiClipper(
                proj=self._session.phi_graph._proj,
                encoder=self._session.phi_graph._encoder,
                top_k=int(p.get("top_k", 5)),
                alpha=float(p.get("alpha", 0.5)),
            )
            result = clipper.clip(str(p.get("query", "")), snap)

        tracks_out = [
            {
                "rank": ct.rank,
                "name": ct.track.name,
                "artist": ct.track.artist,
                "tags": ct.track.all_tags[:6],
                "p_sps": ct.p_sps,
            }
            for ct in result.top_k
        ]
        return {
            "query": result.query,
            "n_tracks_searched": result.n_tracks_searched,
            "alpha": result.alpha,
            "tracks": tracks_out,
        }

    def _exec_shuffle_next(self, action: PhiAction) -> dict:
        if self._shuffle is None:
            return {"error": "shuffle_not_available"}
        # Commit the pending CAIRRN order if one is available.
        #
        # Normal (gate-open) path: the action sat in the queue while the gate
        # was building; _prefeed_shuffle_next() ran and stored "__prefeed_done__"
        # under this exact action_id — commit is safe and expected.
        #
        # Skip (force_dispatch) path: force_dispatch() creates a brand-new
        # PhiAction with a fresh action_id that has no cache entry, so the
        # prefeed-cache check always misses.  But _prefeed_shuffle_next() may
        # have already populated _pending during gate-build for the *previous*
        # queued action.  Committing that pending order here gives the user the
        # CAIRRN-shaped queue on skip, not the stale _active order.
        if (
            self._prefeed_cache.get(action.action_id) == "__prefeed_done__"
            or self._shuffle.shuffle.has_pending
        ):
            self._shuffle.shuffle.commit()
        try:
            idx = self._shuffle.next()
            snap = self._shuffle._session.snapshot if hasattr(self._shuffle, "_session") else None
            track = snap.tracks[idx] if snap and idx < snap.N else None
            out: dict = {"index": idx, "cursor": self._shuffle.shuffle.cursor}
            if track is not None:
                out.update({"name": track.name or track.stem, "artist": track.artist})

            # Write back to the attached PhiPlayer so _poll() sees the new
            # track immediately without the player needing to call play_next().
            if self._player is not None and track is not None:
                self._player._current_idx   = idx
                self._player._current_track = track
                self._player._current_start = time.monotonic()
                self._player._in_play       = True

            # Trigger hot-loader prefetch for upcoming tracks
            if self._hot_loader is not None and self._player is not None:
                preload_ahead = getattr(self._player, "_preload_ahead", 3)
                self._shuffle.peek_and_preload(self._hot_loader, n=preload_ahead)

            return out
        except RuntimeError as e:
            return {"error": str(e)}

    def _exec_shuffle_seed(self) -> dict:
        if self._shuffle is None:
            return {"error": "shuffle_not_available"}
        self._shuffle.seed()
        # Reset player state so the UI reflects the re-seeded cursor position
        if self._player is not None:
            self._player._current_idx   = None
            self._player._current_track = None
            self._player._in_play       = False
        return {"seeded": True, "active_len": self._shuffle.shuffle.active_len}

    def _exec_hub_inject(self, p: dict) -> dict:
        hub_name = str(p.get("hub_name", "CODE"))
        value = float(p.get("value", 1.0))
        self._index.inject_from_hub(hub_name, value)
        return {"injected_hub": hub_name, "value": value}

    def _exec_shard_inject(self, p: dict) -> dict:
        shard_index = int(p.get("shard_index", 0))
        value = float(p.get("value", 1.0))
        self._index.inject(shard_index, value)
        return {"injected_shard": shard_index, "value": value}

    def _exec_propagate(self, p: dict) -> dict:
        steps = int(p.get("steps", 1))
        mode = str(p.get("mode", "local"))
        self._index.propagate(steps, mode=mode)
        return {"propagated": True, "steps": steps, "mode": mode}

    def _exec_cairrn_run(self, p: dict) -> dict:
        hub_name = str(p.get("hub_name", "CODE"))
        metric = float(p.get("metric", 1.0))
        try:
            from workers.cairrn import spawn_hub_worker
            worker = spawn_hub_worker(hub_name, fn=lambda: metric)
            result = worker.run()
            if result.value and isinstance(result.value, dict):
                return result.value.get("cairrn", {})
            return {"error": str(result.error)}
        except Exception as exc:
            return {"error": str(exc)}

    def _exec_mycelial_tick(self, p: dict) -> dict:
        """
        Run one mycelial metabolic tick on the attached substrate.

        Payload keys
        ------------
        budget : float, optional — override the default CODE-scaled budget.

        Returns tick summary as a dict.  Returns error key if no substrate
        is attached (non-fatal — enqueue MYCELIAL_TICK only when substrate exists).
        """
        if self._substrate is None:
            return {"error": "substrate_not_attached"}
        budget = p.get("budget", None)
        if budget is not None:
            budget = float(budget)
        result = self._substrate.tick(budget=budget)
        return result.as_dict()

    def _exec_temporal_rec(self, p: dict) -> dict:
        if self._temporal is None:
            return {"error": "temporal_index_not_available"}
        hub_name = str(p.get("hub_name", "CODE"))
        value = float(p.get("value", 0.0))
        self._temporal.record(hub_name, value)
        return {"recorded_hub": hub_name, "value": value}

    def _exec_load_track(self, action: PhiAction) -> dict:
        """
        Return a hot-loaded track .npy embedding.

        Checks the hot loader cache first.  If the result is already in cache
        (preloaded in background), return immediately with hot=True.
        If not cached, reads the .npy file synchronously (fallback).

        Payload keys
        ------------
        track_path : str — audio file path (used as display/key only)
        npy_path   : str — path to the .npy CLAP embedding file
        """
        p = action.payload
        npy_path = str(p.get("npy_path", ""))
        track_path = str(p.get("track_path", npy_path))
        hot_key = f"track:{track_path}"

        if self._hot_loader is not None:
            cached = self._hot_loader.get(hot_key)
            if cached is not None:
                return {
                    "hot": True,
                    "track_path": track_path,
                    "npy_path": npy_path,
                    "shape": list(cached.shape) if hasattr(cached, "shape") else None,
                }

        # Fallback: synchronous load
        if not npy_path:
            return {"error": "npy_path_required"}
        try:
            import numpy as np
            arr = np.load(npy_path)
            # Store in hot cache for subsequent get() calls
            if self._hot_loader is not None:
                _arr = arr
                self._hot_loader.register_and_signal(hot_key, load_fn=lambda a=_arr: a)
            return {
                "hot": False,
                "track_path": track_path,
                "npy_path": npy_path,
                "shape": list(arr.shape),
            }
        except Exception as exc:
            return {"error": str(exc)}

    def _exec_hover_prefetch(self, action: PhiAction) -> Any:
        """
        Execute an action whose result was speculatively precomputed on hover.

        The hot loader key is "hover:<name>".  If the result is cached, return
        it immediately.  If not cached, execute the inner action synchronously.

        Payload keys
        ------------
        name    : str — hot_loader key suffix (full key = "hover:<name>")
        kind    : str — PhiActionKind of the inner action to execute
        payload : dict — payload for the inner action
        """
        p = action.payload
        name = str(p.get("name", ""))
        hot_key = f"hover:{name}"

        if self._hot_loader is not None:
            cached = self._hot_loader.get(hot_key)
            if cached is not None:
                return cached

        # Fallback: execute inner action synchronously
        inner_kind_str = str(p.get("kind", ""))
        inner_payload = dict(p.get("payload", {}))
        try:
            inner_kind = PhiActionKind(inner_kind_str)
        except ValueError:
            return {"error": f"unknown_inner_kind: {inner_kind_str}"}

        inner_action = PhiAction(kind=inner_kind, payload=inner_payload)
        return self._execute(inner_action)

    # ------------------------------------------------------------------
    # Internal: CAIRRN CODE tick (fires on every gate-open)
    # ------------------------------------------------------------------

    def _run_cairrn_code_tick(self) -> None:
        """
        Run a lightweight CAIRRN CODE hub step on each gate-open event,
        then run one mycelial metabolic tick if a substrate is attached.

        CAIRRN routing tick — modulates shard weights based on CODE activation.
        Mycelial tick — runs demand→nutrient→metabolise→flow→weight cycle on
                        the phi node graph.

        Forest floor echo — when a ForestFloor is attached, the CODE activation
        is also stepped into the floor's CairnBridge so both CAIRRN planes
        (harmonic index and floor bridge) remain synchronised.
        """
        code_act = self._read_code_activation()
        try:
            from workers.cairrn import spawn_hub_worker
            worker = spawn_hub_worker("CODE", fn=lambda: code_act)
            result = worker.run()
            if result.value and isinstance(result.value, dict):
                cairrn_dict = result.value.get("cairrn", {})
                effective = cairrn_dict.get("hub", "CODE")
                mod_val = cairrn_dict.get("modulated_metric", code_act)
                self._index.inject_from_hub(effective, value=mod_val)
        except Exception:
            pass  # non-fatal — system continues without the CAIRRN routing tick

        # Echo the CODE activation into the attached ForestFloor's CairnBridge.
        # This is the wire that keeps the phi app's floor in sync with the
        # dispatcher's gate-open events.  Uses _bridge.step() directly (the
        # same pattern as _workers.py) to avoid re-driving the full heartbeat.
        if self._forest_floor is not None:
            try:
                self._forest_floor._bridge.step("CODE", code_act)
                self._forest_floor._bridge.propagate(1)
            except Exception:
                pass

        # Mycelial tick — runs silently alongside the routing tick
        if self._substrate is not None:
            try:
                self._substrate.tick()
            except Exception:
                pass  # non-fatal — substrate tick failures do not block dispatch

    # ------------------------------------------------------------------
    # Internal: CODE hub activation
    # ------------------------------------------------------------------

    def _read_code_activation(self) -> float:
        """
        Return the mean activation of the CODE hub (shards 3–4).

        Priority order:
        1. Directly attached ForestFloor bridge — the most up-to-date source
           when the dispatcher runs inside the phi app process.
        2. IPC state file (/tmp/phi_cairrn_state.json) — written by the phi
           app's ForestFloor on every heartbeat when ipc_enabled=True.  Lets
           the MCP-side dispatcher gate on the live phi floor state even when
           running in a different process.
        3. Self-managed HarmonicIndex (self._index.shards) — fallback when
           neither the floor nor the IPC file is available.
        """
        # Source 1: attached floor bridge (in-process, zero-latency)
        if self._forest_floor is not None:
            try:
                idx = self._forest_floor._bridge.index_state()
                vals = [float(idx[i]) for i in self._CODE_SHARDS if i < len(idx)]
                return float(sum(vals) / len(vals)) if vals else 0.0
            except Exception:
                pass

        # Source 2: IPC state file (cross-process, phi app must have ipc_enabled=True)
        try:
            import json as _json
            with open("/tmp/phi_cairrn_state.json") as _f:
                _state = _json.load(_f)
            _idx = _state.get("index", [])
            if len(_idx) >= 5:
                vals = [float(_idx[i]) for i in self._CODE_SHARDS if i < len(_idx)]
                return float(sum(vals) / len(vals)) if vals else 0.0
        except Exception:
            pass

        # Source 3: self-managed HarmonicIndex shards (always available)
        try:
            shards = self._index.shards
            vals = [shards[i].activation for i in self._CODE_SHARDS if i < len(shards)]
            return float(sum(vals) / len(vals)) if vals else 0.0
        except Exception:
            return 0.0

    def __repr__(self) -> str:
        return (
            f"<CAIRRNDispatcher "
            f"ticks={self._ticks_run} "
            f"coherence={self.coherence:.4f} "
            f"gate={'open' if self.gate_open else 'closed'} "
            f"queue={len(self._queue)} "
            f"cached={len(self._prefeed_cache)}>"
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_dispatcher(
    harmonic_index: Any,
    session: Optional[Any] = None,
    shuffle: Optional[Any] = None,
    temporal_index: Optional[Any] = None,
    substrate: Optional[Any] = None,
    hot_loader: Optional[CAIRRNHotLoader] = None,
    forest_floor: Optional[Any] = None,
    tau: float = 10.0,
    threshold: float = COHERENCE_THRESHOLD,
) -> CAIRRNDispatcher:
    """
    Construct a CAIRRNDispatcher with the given subsystem references.

    Parameters
    ----------
    harmonic_index : live HarmonicIndex (required — gate signal + inject target)
    session        : PhiTracerSession — needed for CLIP and SHUFFLE_* actions
    shuffle        : CAIRRNPrefeedShuffle — needed for SHUFFLE_* actions
    temporal_index : TemporalShardIndex — needed for TEMPORAL_REC actions
    substrate      : MycelialSubstrate — runs mycelial tick on every gate-open
    hot_loader     : CAIRRNHotLoader — speculative prefetch cache for LOAD_TRACK
                     and HOVER_PREFETCH (and any registered hot entries)
    forest_floor   : ForestFloor — when attached, CODE ticks echo into the floor
                     bridge and _read_code_activation() reads directly from the
                     floor rather than from harmonic_index shards
    tau            : coherence decay constant (default 10.0)
    threshold      : gate-open threshold (default COHERENCE_THRESHOLD ≈ 0.5671)
    """
    return CAIRRNDispatcher(
        harmonic_index=harmonic_index,
        session=session,
        shuffle=shuffle,
        temporal_index=temporal_index,
        substrate=substrate,
        hot_loader=hot_loader,
        forest_floor=forest_floor,
        tau=tau,
        threshold=threshold,
    )
