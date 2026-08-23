"""
cursor_tracer.py — Mouse cursor movement tracer with CAIRRN scheduling.

Architecture
------------
CursorSample      — one timestamped (x, y, metric, hub, coherence) snapshot
CAIRRNScheduler   — derives next sample interval from CAIRRN coherence output
CursorTracer      — daemon thread: sample OS cursor → metric → CAIRRN → store

OS cursor source
----------------
Quartz.CoreGraphics on macOS (zero extra deps — system framework).
Falls back to (0, 0) if unavailable so the tracer still runs in tests.

Metric encoding
---------------
Euclidean distance from screen centre, normalised to [0, 1] by half-diagonal.
Cursor at centre → metric ≈ 0.0 (stable)
Cursor at corner → metric ≈ 1.0 (maximal activity)

CAIRRN Scheduler intervals
--------------------------
coherence ≥ 0.80  → slow lane  2000 ms  (system coherent, low urgency)
coherence  < 0.50  → fast lane   200 ms  (system in flux, track closely)
else               → base rate   500 ms

Hub routing
-----------
CODE hub (shards 3–4): cursor activity = code navigation pressure.
If CAIRRN re-routes to HOME (incoherent), that is recorded in the sample.

Usage
-----
    tracer = CursorTracer(max_samples=200)
    tracer.start()          # daemon thread — dies with process
    ...
    snap = tracer.snapshot()   # thread-safe dict summary
    tracer.stop()
"""

from __future__ import annotations

import math
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, List, Optional, Tuple

from workers.cairrn import spawn_hub_worker
from workers.cairrn._constants import _COHERENCE_THRESHOLD


# ---------------------------------------------------------------------------
# Quartz cursor sampling
# ---------------------------------------------------------------------------

_HAS_QUARTZ = False
_SCREEN_W: float = 1920.0
_SCREEN_H: float = 1080.0

try:
    from Quartz.CoreGraphics import CGEventCreate, CGEventGetLocation, kCGEventNull  # type: ignore[import]
    _HAS_QUARTZ = True
    try:
        from AppKit import NSScreen  # type: ignore[import]
        _main = NSScreen.mainScreen()
        if _main is not None:
            _f = _main.frame()
            _SCREEN_W = float(_f.size.width) or _SCREEN_W
            _SCREEN_H = float(_f.size.height) or _SCREEN_H
    except Exception:
        pass
except Exception:
    _HAS_QUARTZ = False


def _get_cursor_pos() -> Tuple[float, float]:
    """Return (x, y) in screen pixels. Returns (0, 0) when Quartz is absent."""
    if _HAS_QUARTZ:
        try:
            event = CGEventCreate(None)
            loc = CGEventGetLocation(event)
            return float(loc.x), float(loc.y)
        except Exception:
            pass
    return 0.0, 0.0


def _cursor_metric(x: float, y: float) -> float:
    """
    Normalise screen position to a single float in [0, 1].

    Uses Euclidean distance from screen centre divided by the half-diagonal.
    Centre → 0.0 (resting), corner → 1.0 (maximal displacement).
    """
    cx, cy = _SCREEN_W / 2.0, _SCREEN_H / 2.0
    half_diag = math.hypot(cx, cy)
    if half_diag < 1e-9:
        return 0.5
    dist = math.hypot(x - cx, y - cy)
    return min(dist / half_diag, 1.0)


# ---------------------------------------------------------------------------
# Hover regions
# ---------------------------------------------------------------------------

@dataclass
class HoverRegion:
    """
    Named rectangular screen region that triggers a CAIRRN hover prefetch.

    Parameters
    ----------
    name           : unique key — the dispatcher is called with "hover:<name>"
    x, y           : top-left corner in screen pixels
    w, h           : width and height in screen pixels
    dwell_samples  : consecutive samples inside the region before the signal
                     fires (default 2, ~400ms at base rate).  The signal fires
                     exactly once per dwell entry; re-entry after leaving resets
                     the counter and can fire again.
    """
    name:          str
    x:             float
    y:             float
    w:             float
    h:             float
    dwell_samples: int = 2

    def contains(self, px: float, py: float) -> bool:
        """Return True when screen point (px, py) falls inside this region."""
        return self.x <= px <= self.x + self.w and self.y <= py <= self.y + self.h


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class CursorSample:
    """One cursor observation after CAIRRN pipeline processing."""
    ts: float            # monotonic timestamp (time.monotonic())
    x: float
    y: float
    metric: float        # normalised [0, 1]
    hub: str             # effective hub after coherence gate (may be HOME if re-routed)
    coherence: float     # CAIRRN coherence score for this tick
    re_routed: bool      # True when coherence gate redirected to HOME
    interval_ms: float   # sample interval that produced this observation
    hovered_regions: List[str] = field(default_factory=list)  # region names that fired this tick

    def as_dict(self) -> dict:
        d: dict = {
            "ts":          round(self.ts, 4),
            "x":           round(self.x, 1),
            "y":           round(self.y, 1),
            "metric":      round(self.metric, 6),
            "hub":         self.hub,
            "coherence":   round(self.coherence, 6),
            "re_routed":   self.re_routed,
            "interval_ms": round(self.interval_ms, 1),
        }
        if self.hovered_regions:
            d["hovered_regions"] = list(self.hovered_regions)
        return d


# ---------------------------------------------------------------------------
# CAIRRN Scheduler
# ---------------------------------------------------------------------------

# Interval boundaries (milliseconds)
_INTERVAL_FAST_MS:  float = 200.0
_INTERVAL_BASE_MS:  float = 500.0
_INTERVAL_SLOW_MS:  float = 2000.0

# Coherence thresholds that shift lanes
_COH_SLOW_GATE:  float = 0.80   # ≥ this → slow lane
_COH_FAST_GATE:  float = 0.50   # < this → fast lane (same as CAIRRN re-route threshold)


class CAIRRNScheduler:
    """
    Maps CAIRRN coherence output → next sample interval.

    coherence ≥ _COH_SLOW_GATE  →  slow lane  (_INTERVAL_SLOW_MS)
    coherence  < _COH_FAST_GATE  →  fast lane  (_INTERVAL_FAST_MS)
    else                         →  base rate  (_INTERVAL_BASE_MS)
    """

    def __init__(self) -> None:
        self._current_ms: float = _INTERVAL_BASE_MS
        self._lock = threading.Lock()

    def update(self, coherence: float) -> float:
        """Feed latest coherence score; return next interval in ms."""
        if coherence >= _COH_SLOW_GATE:
            interval = _INTERVAL_SLOW_MS
        elif coherence < _COH_FAST_GATE:
            interval = _INTERVAL_FAST_MS
        else:
            interval = _INTERVAL_BASE_MS
        with self._lock:
            self._current_ms = interval
        return interval

    @property
    def interval_ms(self) -> float:
        with self._lock:
            return self._current_ms

    @property
    def interval_s(self) -> float:
        return self.interval_ms / 1000.0


# ---------------------------------------------------------------------------
# CursorTracer daemon
# ---------------------------------------------------------------------------

class CursorTracer:
    """
    Daemon thread that samples OS cursor position and routes each observation
    through the CAIRRN CODE-hub pipeline.

    Parameters
    ----------
    max_samples  : ring-buffer capacity (default 200)
    hub          : CAIRRN hub to route through (default 'CODE')
    """

    _HUB: str = "CODE"

    def __init__(
        self,
        max_samples: int = 200,
        hub: str = "CODE",
    ) -> None:
        self.hub = hub
        self._samples: Deque[CursorSample] = deque(maxlen=max_samples)
        self._scheduler = CAIRRNScheduler()
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._total_ticks: int = 0
        self._re_route_count: int = 0
        # Hover dwell state — protected by _hover_lock
        self._hover_lock = threading.Lock()
        self._hover_regions: List[HoverRegion] = []
        self._dwell_counters: dict[str, int] = {}  # region.name → consecutive sample count
        self._dispatcher: Optional[Any] = None

    # ------------------------------------------------------------------
    # Hover region API
    # ------------------------------------------------------------------

    def register_hover(self, region: HoverRegion) -> None:
        """
        Register a named screen region for dwell detection.

        When the cursor dwells inside *region* for ``region.dwell_samples``
        consecutive ticks the dispatcher is called with
        ``signal_hover("hover:<region.name>")``.  The signal fires exactly
        once per dwell entry; leaving and re-entering the region resets the
        counter.

        Safe to call before or after ``start()``.
        """
        with self._hover_lock:
            self._hover_regions.append(region)
            self._dwell_counters[region.name] = 0

    def attach_dispatcher(self, dispatcher: Any) -> None:
        """
        Attach a ``CAIRRNDispatcher`` (or any object with ``signal_hover()``)
        to receive hover signals.

        Can be called at any time; thread-safe.
        """
        with self._hover_lock:
            self._dispatcher = dispatcher

    def _check_hover(self, x: float, y: float) -> List[str]:
        """
        Check cursor (x, y) against all registered regions.

        Updates dwell counters.  Returns names of regions whose dwell
        threshold was just reached this tick.  Signals the dispatcher
        for each fired region.

        Called from ``_tick()`` — no ``_lock`` held, only ``_hover_lock``
        acquired transiently.
        """
        with self._hover_lock:
            regions   = list(self._hover_regions)
            counters  = dict(self._dwell_counters)
            dispatcher = self._dispatcher

        fired: List[str] = []
        updates: dict[str, int] = {}

        for region in regions:
            prev = counters.get(region.name, 0)
            if region.contains(x, y):
                new_count = prev + 1
                updates[region.name] = new_count
                # Fire exactly once: when the counter first reaches the threshold
                if new_count == region.dwell_samples:
                    fired.append(region.name)
            else:
                updates[region.name] = 0  # cursor left — reset

        with self._hover_lock:
            self._dwell_counters.update(updates)

        if dispatcher is not None:
            for name in fired:
                try:
                    dispatcher.signal_hover(f"hover:{name}")
                except Exception:
                    pass  # never crash the daemon over a prefetch miss

        return fired

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the tracer daemon thread. No-op if already running."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._loop,
            daemon=True,
            name="cursor-tracer",
        )
        self._thread.start()

    def stop(self) -> None:
        """Signal the tracer to stop after the current sleep expires."""
        self._running = False

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def _loop(self) -> None:
        while self._running:
            interval_ms = self._scheduler.interval_ms
            sample = self._tick(interval_ms)
            with self._lock:
                self._samples.append(sample)
                self._total_ticks += 1
                if sample.re_routed:
                    self._re_route_count += 1
            time.sleep(self._scheduler.interval_s)

    def _tick(self, interval_ms: float) -> CursorSample:
        """One observation: sample cursor, compute metric, run CAIRRN."""
        x, y = _get_cursor_pos()
        metric = _cursor_metric(x, y)
        ts = time.monotonic()

        worker = spawn_hub_worker(
            hub_name=self.hub,
            fn=lambda: metric,
            name=f"cursor-tracer-{self.hub.lower()}",
        )
        result = worker.run()

        cairrn_dict: dict = {}
        if result.value and isinstance(result.value, dict):
            cairrn_dict = result.value.get("cairrn", {})

        coherence  = float(cairrn_dict.get("coherence",  _COHERENCE_THRESHOLD))
        effective_hub = str(cairrn_dict.get("hub", self.hub))
        re_routed  = bool(cairrn_dict.get("re_routed", False))

        self._scheduler.update(coherence)

        hovered = self._check_hover(x, y)

        return CursorSample(
            ts=ts,
            x=x,
            y=y,
            metric=metric,
            hub=effective_hub,
            coherence=coherence,
            re_routed=re_routed,
            interval_ms=interval_ms,
            hovered_regions=hovered,
        )

    # ------------------------------------------------------------------
    # Inspection
    # ------------------------------------------------------------------

    def snapshot(self) -> dict:
        """Thread-safe summary of current tracer state."""
        with self._lock:
            samples = list(self._samples)
            total   = self._total_ticks
            re_rts  = self._re_route_count

        with self._hover_lock:
            hover_regions = [
                {"name": r.name, "dwell_samples": r.dwell_samples,
                 "counter": self._dwell_counters.get(r.name, 0)}
                for r in self._hover_regions
            ]

        last = samples[-1] if samples else None
        coherences = [s.coherence for s in samples]
        metrics    = [s.metric for s in samples]

        return {
            "running":            self._running,
            "hub":                self.hub,
            "total_ticks":        total,
            "re_route_count":     re_rts,
            "buffer_size":        len(samples),
            "current_interval_ms": round(self._scheduler.interval_ms, 1),
            "quartz_available":   _HAS_QUARTZ,
            "screen_w":           _SCREEN_W,
            "screen_h":           _SCREEN_H,
            "last_sample":        last.as_dict() if last else None,
            "mean_coherence":     round(sum(coherences) / len(coherences), 6) if coherences else 0.0,
            "mean_metric":        round(sum(metrics) / len(metrics), 6) if metrics else 0.0,
            "hover_regions":      hover_regions,
            "samples":            [s.as_dict() for s in samples],
        }

    @property
    def samples(self) -> list[CursorSample]:
        with self._lock:
            return list(self._samples)

    @property
    def scheduler(self) -> CAIRRNScheduler:
        return self._scheduler

    def __repr__(self) -> str:
        return (
            f"<CursorTracer hub={self.hub!r} "
            f"running={self._running} "
            f"ticks={self._total_ticks} "
            f"interval={self._scheduler.interval_ms:.0f}ms>"
        )
