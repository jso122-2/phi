"""
CAIRRNHotLoader — speculative prefetch engine for phi operations.

Architecture
------------
Every phi action that could block (track load, clip query, hub compute) can be
registered with a signal function and a load function.  On each step() call the
hot loader checks all signals; when a signal fires it kicks off the load in a
background daemon thread so the result is in cache before the action is needed.

Two entry-point patterns
------------------------
1. Signal-driven (predictive)
   The scheduler knows the CAIRRN attractor basin and can predict what will fire
   next.  Register with a signal_fn derived from hub activation thresholds:

       hot_loader.register(
           name="track:/path/T0.npy",
           signal_fn=lambda: code_activation() > 0.7,
           load_fn=lambda: np.load("/path/T0.npy"),
       )

   The load fires automatically when CODE hub heats up — before the shuffle
   cursor reaches that track.

2. Manual signal (hover / explicit prefetch)
   The UI calls signal() when the user hovers a button.  The hot loader
   fires the load_fn immediately on the next step():

       # At app start — register all button actions
       hot_loader.register("hover:next_track", signal_fn=lambda: False, load_fn=compute_next)

       # When hover event fires
       hot_loader.signal("hover:next_track")

       # By the time the click arrives the result is cached
       result = hot_loader.get("hover:next_track")  # instant

Lifecycle
---------
    step() → for each entry: if (pending or signal fires) and not loaded/loading
                 → spawn daemon thread running load_fn
                 → _loading=True until thread completes
                 → _loaded=True + _result set on completion

    get(name) → Optional[Any]   — None if not yet loaded
    invalidate(name)             — clear cache; re-triggers on next signal
    signal(name)                 — set _pending=True (fires on next step())
    register(name, signal_fn, load_fn) — add or overwrite an entry

Thread model
------------
Each load_fn runs in a daemon thread (so it never blocks process exit).
The RLock protects the registry dict itself; individual entries use a per-entry
lock for result assignment so get() is always safe to call from any thread.

HotLoadResult
-------------
Returned by step() — tells the caller which names were triggered this step.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


# ---------------------------------------------------------------------------
# HotLoadMetrics — telemetry for the speculative prefetch layer
# ---------------------------------------------------------------------------


@dataclass
class HotLoadMetrics:
    """
    Prediction telemetry for CAIRRNHotLoader.

    Tracks whether CAIRRN's speculative loads are actually ahead of demand.

    Attributes
    ----------
    hits                : get() returned a cached result (prediction was ready)
    misses              : get() returned None (prediction not ready or not made)
    loads_triggered     : background threads spawned (via try_fire / step)
    loads_completed     : threads that finished successfully
    load_errors         : threads that raised an exception
    sum_load_duration_s : total wall time spent in all completed load_fns
    sum_latency_saved_s : sum of load durations on cache hits
                          (load_fn wall time that was saved because it ran
                          in the background before the caller needed it)
    sum_lead_time_s     : sum of (first_get_ts − load_end_ts) for all cache
                          hits on their first access.  Positive = prediction
                          was ready before the caller arrived.  Negative (or
                          zero) = caller was blocked waiting for the load.
    leads_measured      : number of entries where lead time was recorded
    """

    hits:                 int   = 0
    misses:               int   = 0
    loads_triggered:      int   = 0
    loads_completed:      int   = 0
    load_errors:          int   = 0
    sum_load_duration_s:  float = 0.0
    sum_latency_saved_s:  float = 0.0
    sum_lead_time_s:      float = 0.0
    leads_measured:       int   = 0

    # ------------------------------------------------------------------
    # Derived properties
    # ------------------------------------------------------------------

    @property
    def total_lookups(self) -> int:
        return self.hits + self.misses

    @property
    def hit_rate(self) -> float:
        """Fraction of get() calls that returned a cached result."""
        return self.hits / self.total_lookups if self.total_lookups else 0.0

    @property
    def miss_rate(self) -> float:
        return 1.0 - self.hit_rate if self.total_lookups > 0 else 0.0

    @property
    def avg_load_duration_s(self) -> float:
        """Average wall time of completed load_fns (background thread time)."""
        return (
            self.sum_load_duration_s / self.loads_completed
            if self.loads_completed
            else 0.0
        )

    @property
    def avg_latency_saved_s(self) -> float:
        """
        Average load duration saved per cache hit.

        Interpretation: if this is > 0 and the hit rate is high, the
        speculative layer is meaningfully reducing perceived latency.
        """
        return self.sum_latency_saved_s / self.hits if self.hits else 0.0

    @property
    def avg_lead_time_s(self) -> float:
        """
        Average lead time: how far ahead of demand the prefetch completed.

        Positive  → CAIRRN predictions are ahead of the caller — good.
        Near-zero → predictions are just barely in time.
        Negative  → caller arrived before the load finished — prediction
                     was triggered too late (or load is slow).
        """
        return (
            self.sum_lead_time_s / self.leads_measured
            if self.leads_measured
            else 0.0
        )

    def as_dict(self) -> dict:
        return {
            "hits":                 self.hits,
            "misses":               self.misses,
            "total_lookups":        self.total_lookups,
            "hit_rate":             round(self.hit_rate, 4),
            "miss_rate":            round(self.miss_rate, 4),
            "loads_triggered":      self.loads_triggered,
            "loads_completed":      self.loads_completed,
            "load_errors":          self.load_errors,
            "avg_load_duration_s":  round(self.avg_load_duration_s, 6),
            "avg_latency_saved_s":  round(self.avg_latency_saved_s, 6),
            "avg_lead_time_s":      round(self.avg_lead_time_s, 6),
        }


# ---------------------------------------------------------------------------
# HotEntry — one registered prefetchable item
# ---------------------------------------------------------------------------


class _HotEntry:
    """
    Internal: one named prefetchable item.

    Attributes
    ----------
    name            : unique key
    signal_fn       : returns True when load should fire (re-evaluated each step)
    load_fn         : the actual computation — runs in a daemon thread
    _loaded         : True once load_fn completed successfully
    _loading        : True while daemon thread is running
    _pending        : True when manually signaled via hot_loader.signal(name)
    _result         : cached result (set by the daemon thread)
    _error          : exception if load_fn raised (non-fatal)
    _load_start_ts  : monotonic timestamp when try_fire() spawned the thread
    _load_end_ts    : monotonic timestamp when _run() completed (0.0 = not yet)
    _first_get_ts   : monotonic timestamp of first successful get() (0.0 = never)
    _complete_cb    : optional callback (load_dur_s, error_or_None) → None
                      called by daemon thread on completion; used by the loader
                      to accumulate completion metrics without polling
    """

    __slots__ = (
        "name",
        "signal_fn",
        "load_fn",
        "_loaded",
        "_loading",
        "_pending",
        "_result",
        "_error",
        "_lock",
        "_load_start_ts",
        "_load_end_ts",
        "_first_get_ts",
        "_complete_cb",
    )

    def __init__(
        self,
        name: str,
        signal_fn: Callable[[], bool],
        load_fn: Callable[[], Any],
        complete_cb: Optional[Callable[[float, Optional[Exception]], None]] = None,
    ) -> None:
        self.name = name
        self.signal_fn = signal_fn
        self.load_fn = load_fn
        self._loaded: bool = False
        self._loading: bool = False
        self._pending: bool = False
        self._result: Optional[Any] = None
        self._error: Optional[Exception] = None
        self._lock = threading.Lock()
        self._load_start_ts: float = 0.0
        self._load_end_ts: float = 0.0
        self._first_get_ts: float = 0.0
        self._complete_cb = complete_cb

    # ------------------------------------------------------------------
    # Raw result access (no metrics — callers may call this directly)
    # ------------------------------------------------------------------

    def peek(self) -> Optional[Any]:
        """Return cached result without recording any metrics. Used by is_ready()."""
        with self._lock:
            return self._result if self._loaded else None

    def invalidate(self) -> None:
        with self._lock:
            self._loaded = False
            self._loading = False
            self._pending = False
            self._result = None
            self._error = None
            self._load_start_ts = 0.0
            self._load_end_ts = 0.0
            self._first_get_ts = 0.0

    # ------------------------------------------------------------------
    # Timing helpers (safe to call from any thread after completion)
    # ------------------------------------------------------------------

    @property
    def load_duration_s(self) -> float:
        """Wall time of the completed load_fn (0.0 if not yet complete)."""
        with self._lock:
            if self._load_end_ts > 0.0 and self._load_start_ts > 0.0:
                return max(0.0, self._load_end_ts - self._load_start_ts)
            return 0.0

    @property
    def lead_time_s(self) -> Optional[float]:
        """
        Time between load completion and first get() access.

        Positive  → prefetch was ahead of demand.
        Near-zero → barely in time.
        None      → not yet accessed or not yet completed.
        """
        with self._lock:
            if self._first_get_ts > 0.0 and self._load_end_ts > 0.0:
                return self._first_get_ts - self._load_end_ts
            return None

    # ------------------------------------------------------------------
    # Internal: daemon thread body
    # ------------------------------------------------------------------

    def _run(self) -> None:
        """Daemon thread body — executes load_fn and records timing."""
        start = time.monotonic()
        error: Optional[Exception] = None
        try:
            result = self.load_fn()
            end = time.monotonic()
            with self._lock:
                self._result = result
                self._loaded = True
                self._loading = False
                self._load_end_ts = end
        except Exception as exc:
            end = time.monotonic()
            error = exc
            with self._lock:
                self._error = exc
                self._loading = False
                self._load_end_ts = end

        if self._complete_cb is not None:
            try:
                self._complete_cb(max(0.0, end - start), error)
            except Exception:
                pass  # callback failures must never crash the daemon thread

    def try_fire(self) -> bool:
        """
        Check if this entry should fire a load.

        Returns True if a new thread was spawned this call.
        Records _load_start_ts at spawn time.
        Thread-safe.
        """
        with self._lock:
            if self._loaded or self._loading:
                return False
            should = self._pending
        if not should:
            try:
                should = bool(self.signal_fn())
            except Exception:
                should = False
        if should:
            with self._lock:
                if self._loaded or self._loading:
                    return False
                self._pending = False
                self._loading = True
                self._load_start_ts = time.monotonic()
            t = threading.Thread(target=self._run, daemon=True, name=f"hot:{self.name}")
            t.start()
            return True
        return False

    def state(self) -> dict:
        with self._lock:
            load_dur = (
                max(0.0, self._load_end_ts - self._load_start_ts)
                if self._load_end_ts > 0.0 and self._load_start_ts > 0.0
                else 0.0
            )
            lt: Optional[float] = (
                self._first_get_ts - self._load_end_ts
                if self._first_get_ts > 0.0 and self._load_end_ts > 0.0
                else None
            )
            return {
                "loaded":          self._loaded,
                "loading":         self._loading,
                "pending":         self._pending,
                "error":           str(self._error) if self._error else None,
                "load_duration_s": round(load_dur, 6),
                "lead_time_s":     round(lt, 6) if lt is not None else None,
            }


# ---------------------------------------------------------------------------
# HotLoadResult
# ---------------------------------------------------------------------------


@dataclass
class HotLoadResult:
    """Outcome of one CAIRRNHotLoader.step() call."""

    triggered: list[str]   # names whose load threads were spawned this step
    ready:     list[str]   # names that are loaded and ready (get() != None)
    loading:   list[str]   # names whose threads are still running
    total:     int         # total registered entries

    def as_dict(self) -> dict:
        return {
            "triggered": self.triggered,
            "ready":     self.ready,
            "loading":   self.loading,
            "total":     self.total,
        }


# ---------------------------------------------------------------------------
# CAIRRNHotLoader
# ---------------------------------------------------------------------------


class CAIRRNHotLoader:
    """
    CAIRRN-aware speculative prefetch engine.

    Parameters
    ----------
    max_entries : soft cap on registry size — oldest entries are evicted
                  when exceeded (default 256).  Set to 0 to disable eviction.
    """

    def __init__(self, max_entries: int = 256) -> None:
        self._max = max(0, int(max_entries))
        self._registry: dict[str, _HotEntry] = {}
        self._insertion_order: list[str] = []   # FIFO eviction
        self._lock = threading.RLock()

        # Metrics counters — protected by _metrics_lock (separate from registry)
        self._metrics_lock = threading.Lock()
        self._hits:                 int   = 0
        self._misses:               int   = 0
        self._loads_triggered:      int   = 0
        self._loads_completed:      int   = 0
        self._load_errors:          int   = 0
        self._sum_load_duration_s:  float = 0.0
        self._sum_latency_saved_s:  float = 0.0
        self._sum_lead_time_s:      float = 0.0
        self._leads_measured:       int   = 0

    # ------------------------------------------------------------------
    # Registry management
    # ------------------------------------------------------------------

    def register(
        self,
        name: str,
        signal_fn: Callable[[], bool],
        load_fn: Callable[[], Any],
    ) -> None:
        """
        Register or overwrite a named hot-loadable entry.

        If an entry with the same name already exists:
        - If it is already loaded, the existing result is preserved.
        - If it is loading or unloaded, the entry is replaced.

        Parameters
        ----------
        name      : unique key (e.g. "track:/path/T0.npy", "hover:play_btn")
        signal_fn : predicate — load fires when this returns True
        load_fn   : computation to run in background (must be thread-safe)
        """
        with self._lock:
            existing = self._registry.get(name)
            if existing is not None and existing._loaded:
                # Preserve loaded result — just update the functions
                existing.signal_fn = signal_fn
                existing.load_fn = load_fn
                return
            entry = _HotEntry(
                name=name,
                signal_fn=signal_fn,
                load_fn=load_fn,
                complete_cb=self._make_complete_cb(),
            )
            if name not in self._registry:
                self._insertion_order.append(name)
            self._registry[name] = entry
            self._evict_if_needed()

    def signal(self, name: str) -> bool:
        """
        Manually mark an entry as pending (e.g. on cursor hover).

        The load fires on the next step() call.

        Returns True if the entry is registered and was marked pending.
        Returns False if the entry is not registered — register it first.
        """
        with self._lock:
            entry = self._registry.get(name)
            if entry is None:
                return False
            with entry._lock:
                if not entry._loaded and not entry._loading:
                    entry._pending = True
            return True

    def register_and_signal(
        self,
        name: str,
        load_fn: Callable[[], Any],
    ) -> None:
        """
        Register a one-shot entry and immediately mark it pending.

        Convenience wrapper for the hover-prefetch pattern:
            load fires on the next step() without any signal_fn check.

        If the entry already exists and is loaded, this is a no-op.
        """
        self.register(name, signal_fn=lambda: False, load_fn=load_fn)
        self.signal(name)

    def invalidate(self, name: str) -> None:
        """Clear cached result for *name* so it re-loads on next signal."""
        with self._lock:
            entry = self._registry.get(name)
        if entry is not None:
            entry.invalidate()

    def invalidate_all(self) -> None:
        """Clear all cached results."""
        with self._lock:
            entries = list(self._registry.values())
        for e in entries:
            e.invalidate()

    def unregister(self, name: str) -> bool:
        """Remove an entry from the registry. Returns True if it existed."""
        with self._lock:
            removed = self._registry.pop(name, None) is not None
            if removed and name in self._insertion_order:
                self._insertion_order.remove(name)
            return removed

    # ------------------------------------------------------------------
    # Step — check signals + spawn loads
    # ------------------------------------------------------------------

    def step(self) -> HotLoadResult:
        """
        One hot-loader clock tick.

        Iterates all registered entries:
        - Checks signal_fn / _pending flag
        - Spawns a daemon thread for any entry that should fire and is not
          already loaded or loading

        Returns HotLoadResult describing what happened.
        """
        with self._lock:
            entries = list(self._registry.values())

        triggered: list[str] = []
        ready:     list[str] = []
        loading:   list[str] = []

        for entry in entries:
            fired = entry.try_fire()
            if fired:
                triggered.append(entry.name)
                loading.append(entry.name)
            else:
                with entry._lock:
                    if entry._loaded:
                        ready.append(entry.name)
                    elif entry._loading:
                        loading.append(entry.name)

        if triggered:
            with self._metrics_lock:
                self._loads_triggered += len(triggered)

        return HotLoadResult(
            triggered=triggered,
            ready=ready,
            loading=loading,
            total=len(entries),
        )

    # ------------------------------------------------------------------
    # Get — instrumented cache lookup
    # ------------------------------------------------------------------

    def get(self, name: str) -> Optional[Any]:
        """
        Return the cached result for *name*, or None if not yet loaded.

        Records a hit or miss in the metrics counters.
        On first hit for an entry, also records the lead time
        (time between load completion and this access).

        Never blocks. Safe to call from any thread.
        """
        with self._lock:
            entry = self._registry.get(name)
        if entry is None:
            with self._metrics_lock:
                self._misses += 1
            return None

        now = time.monotonic()
        result = entry.peek()

        if result is not None:
            # Hit — record latency saved and lead time
            with entry._lock:
                load_dur = (
                    max(0.0, entry._load_end_ts - entry._load_start_ts)
                    if entry._load_end_ts > 0.0 and entry._load_start_ts > 0.0
                    else 0.0
                )
                is_first_hit = entry._first_get_ts == 0.0
                if is_first_hit:
                    entry._first_get_ts = now
                load_end = entry._load_end_ts

            lead = now - load_end if load_end > 0.0 and is_first_hit else None

            with self._metrics_lock:
                self._hits += 1
                self._sum_latency_saved_s += load_dur
                if lead is not None:
                    self._sum_lead_time_s += lead
                    self._leads_measured += 1
        else:
            with self._metrics_lock:
                self._misses += 1

        return result

    def _peek(self, name: str) -> Optional[Any]:
        """
        Raw cache lookup — no metrics recorded.

        Used internally by is_ready() to avoid inflating hit/miss counts
        with non-consumer reads.
        """
        with self._lock:
            entry = self._registry.get(name)
        if entry is None:
            return None
        return entry.peek()

    def is_ready(self, name: str) -> bool:
        """True if the result for *name* is loaded and available (no metrics)."""
        return self._peek(name) is not None

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    @property
    def metrics(self) -> HotLoadMetrics:
        """
        Snapshot of prediction telemetry.

        Call this to assess whether CAIRRN's attractor predictions are
        actually ahead of user actions, or the hot loader is warming
        cache at random.

        hit_rate close to 1.0 + avg_lead_time_s > 0  →  CAIRRN is working.
        hit_rate low + avg_lead_time_s < 0             →  predictions are too slow or wrong.
        """
        with self._metrics_lock:
            return HotLoadMetrics(
                hits=self._hits,
                misses=self._misses,
                loads_triggered=self._loads_triggered,
                loads_completed=self._loads_completed,
                load_errors=self._load_errors,
                sum_load_duration_s=self._sum_load_duration_s,
                sum_latency_saved_s=self._sum_latency_saved_s,
                sum_lead_time_s=self._sum_lead_time_s,
                leads_measured=self._leads_measured,
            )

    def reset_metrics(self) -> None:
        """Zero all metric counters (does not affect the cache or registry)."""
        with self._metrics_lock:
            self._hits                = 0
            self._misses              = 0
            self._loads_triggered     = 0
            self._loads_completed     = 0
            self._load_errors         = 0
            self._sum_load_duration_s = 0.0
            self._sum_latency_saved_s = 0.0
            self._sum_lead_time_s     = 0.0
            self._leads_measured      = 0

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    def state(self) -> dict:
        """Serialisable snapshot of all registered entries + metrics."""
        with self._lock:
            entries = {n: e.state() for n, e in self._registry.items()}
        return {
            "total":   len(entries),
            "entries": entries,
            "metrics": self.metrics.as_dict(),
        }

    def summary(self) -> dict:
        """Counts + top-level metrics — no per-entry detail."""
        with self._lock:
            total = len(self._registry)
            entries = list(self._registry.values())
        loaded  = sum(1 for e in entries if e._loaded)
        loading = sum(1 for e in entries if e._loading)
        return {
            "total":    total,
            "loaded":   loaded,
            "loading":  loading,
            "unloaded": total - loaded - loading,
            "metrics":  self.metrics.as_dict(),
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _make_complete_cb(self) -> Callable[[float, Optional[Exception]], None]:
        """
        Return a closure that accumulates load completion metrics.

        Called by the _HotEntry daemon thread when load_fn finishes.
        The closure captures `self` weakly via direct reference — the
        loader outlives any individual daemon thread.
        """
        loader = self

        def _cb(dur_s: float, error: Optional[Exception]) -> None:
            with loader._metrics_lock:
                if error is None:
                    loader._loads_completed += 1
                    loader._sum_load_duration_s += dur_s
                else:
                    loader._load_errors += 1

        return _cb

    def _evict_if_needed(self) -> None:
        """FIFO eviction when registry exceeds max_entries."""
        if self._max <= 0:
            return
        while len(self._registry) > self._max and self._insertion_order:
            oldest = self._insertion_order.pop(0)
            self._registry.pop(oldest, None)

    def __len__(self) -> int:
        with self._lock:
            return len(self._registry)

    def __repr__(self) -> str:
        s = self.summary()
        m = s["metrics"]
        return (
            f"<CAIRRNHotLoader "
            f"total={s['total']} "
            f"loaded={s['loaded']} "
            f"hit_rate={m['hit_rate']:.2f} "
            f"lead={m['avg_lead_time_s']:.3f}s>"
        )
