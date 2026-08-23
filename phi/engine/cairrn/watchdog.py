# -*- coding: utf-8 -*-
"""phi.engine.cairrn.watchdog — Pericles-pattern watchdog for CAIRRN worker health.

Mirrors PhiRaceWatcher (phi.core.race_watcher) but enforces the CAIRRN
computation substrate instead of the playback engine.

Five conditions monitored
─────────────────────────
    COHERENCE_HANG    hub coherence below the Euler floor |x*| ≈ 0.5671 for
                      more than hang_ticks_max consecutive poll_tick() calls
                      without a reset firing.
                      Escalation: force synthetic bridge.step(hub, 0.0) to
                      re-trigger Layer 3 reroute reset.

    Z_STORM           hub |z_awareness| ≥ z_threshold for N consecutive
                      on_route() calls without decaying back below threshold.
                      Escalation: log warning; caller may flush handler queue.

    REROUTE_STORM     same hub HOME-rerouted on N consecutive on_route() calls.
                      τ may be too short for the current request rate.
                      Escalation: log warning only.

    PROPAGATION_STALL ring total energy has not changed by more than ε across
                      stall_ticks_max consecutive poll_tick() calls.
                      Escalation: inject one synthetic bridge.propagate(1).

    DOUBLE_ROUTE      same RequestKind routed twice within poll_ms × 3 ms.
                      Mirrors DOUBLE_ADVANCE in PhiRaceWatcher.
                      Escalation: return True to suppress the second call.

Euler floor
───────────
The fixed point x* = −W(1) ≈ −0.5671 defines a second, tighter coherence
bound.  Its magnitude |x*| ≈ 0.5671 > 0.50 (soft floor).  A hub in the
Euler-bound zone (coherence < 0.50 AND trending toward 0) is in critical
degradation — the reroute that fired isn't clearing the hang.

Usage
─────
    watchdog = CairrnWorkerWatchdog(bridge=bridge)

    # In route() — at the top (before pipeline):
    if watchdog.on_double_route(kind):
        return cached_result

    # In route() — after pipeline + dispatch:
    watchdog.on_route(kind, result)

    # In _poll() heartbeat (decimated):
    watchdog.poll_tick(bridge)
"""
from __future__ import annotations

import logging
import threading
import time
from typing import TYPE_CHECKING, Dict, Optional

if TYPE_CHECKING:
    from phi.engine.cairrn.bridge import CairnBridge
    from phi.engine.cairrn.router import DispatchResult, RequestKind

from phi.engine.cairrn._constants import EULER_FLOOR

_log = logging.getLogger("phi.cairrn.watchdog")


class CairrnWorkerWatchdog:
    """
    Pericles-pattern watchdog for CAIRRN worker race conditions.

    Tracks five health signals across route() calls and poll ticks.
    Escalates through: warn → auto-recover → log-only.

    Args
    ----
    bridge               : the CairnBridge instance to monitor and recover
    max_coherence_hang   : poll ticks below Euler floor before forced reset
    max_z_storm_ticks    : consecutive on_route ticks with |z| ≥ z_threshold
    max_reroute_streak   : consecutive HOME-reroutes before REROUTE_STORM
    max_stall_ticks      : poll ticks with ring energy Δ < stall_eps before nudge
    stall_eps            : minimum ring energy change to count as alive
    poll_ms              : poll interval in ms (for DOUBLE_ROUTE window)
    z_threshold          : z-awareness threshold for Z_STORM
    """

    def __init__(
        self,
        bridge: "CairnBridge",
        max_coherence_hang:  int   = 5,
        max_z_storm_ticks:   int   = 8,
        max_reroute_streak:  int   = 3,
        max_stall_ticks:     int   = 20,
        stall_eps:           float = 1e-4,
        poll_ms:             float = 150.0,
        z_threshold:         float = 2.5,
    ) -> None:
        self._bridge      = bridge
        self._poll_ms     = poll_ms
        self._z_threshold = z_threshold
        self._stall_eps   = stall_eps

        self._hang_max    = max_coherence_hang
        self._z_storm_max = max_z_storm_ticks
        self._reroute_max = max_reroute_streak
        self._stall_max   = max_stall_ticks

        # Per-hub streak counters
        self._hang_streak:    Dict[str, int] = {}
        self._z_storm_streak: Dict[str, int] = {}
        self._reroute_streak: Dict[str, int] = {}

        # Propagation stall
        self._stall_ticks:     int   = 0
        self._last_ring_energy: float = 0.0

        # DOUBLE_ROUTE dedup — _dr_lock serialises the TOCTOU read-check-write
        self._last_route_ts: Dict[str, float] = {}
        self._dr_lock = threading.Lock()
        self._dr_warmup_active: bool = False  # suppresses DOUBLE_ROUTE during batch warmup

        # Lifetime totals
        self._total_coherence_hang:    int = 0
        self._total_z_storm:           int = 0
        self._total_reroute_storm:     int = 0
        self._total_propagation_stall: int = 0
        self._total_double_route:      int = 0
        self._total_ticks:             int = 0

    # ── Poll-tick (passive scan) ──────────────────────────────────────────────

    def poll_tick(self, bridge: Optional["CairnBridge"] = None) -> None:
        """
        Passive scan: PROPAGATION_STALL + Euler-floor hang detection.

        Call every ~10 raw poll ticks (once per decimated heartbeat).
        """
        b = bridge or self._bridge
        self._total_ticks += 1

        # PROPAGATION_STALL
        ring   = b.index_state()
        energy = sum(abs(v) for v in ring)
        delta  = abs(energy - self._last_ring_energy)

        if delta < self._stall_eps:
            self._stall_ticks += 1
            if self._stall_ticks >= self._stall_max:
                _log.warning(
                    "CairrnWatchdog [PROPAGATION_STALL] ring energy frozen "
                    "for %d ticks (Δ=%.2e < eps=%.2e)  energy=%.4f — nudging",
                    self._stall_ticks, delta, self._stall_eps, energy,
                )
                b.propagate(steps=1)
                self._total_propagation_stall += 1
                self._stall_ticks = 0
        else:
            self._stall_ticks = 0
        self._last_ring_energy = energy

        # Euler-floor hang check
        for hub_name, hub_state in b._hubs.items():
            coh = hub_state.coherence
            if coh < EULER_FLOOR and coh < b.coherence_floor and hub_state.steps > 0:
                streak = self._hang_streak.get(hub_name, 0) + 1
                self._hang_streak[hub_name] = streak
                _log.debug(
                    "CairrnWatchdog [COHERENCE_HANG] hub=%s  coh=%.4f < euler=%.4f"
                    "  streak=%d/%d",
                    hub_name, coh, EULER_FLOOR, streak, self._hang_max,
                )
                if streak >= self._hang_max:
                    _log.warning(
                        "CairrnWatchdog [COHERENCE_HANG] hub=%s stuck below "
                        "Euler floor for %d ticks (coh=%.4f) — forcing reset",
                        hub_name, streak, coh,
                    )
                    b.step(hub_name, 0.0)
                    self._total_coherence_hang += 1
                    self._hang_streak[hub_name] = 0
            else:
                self._hang_streak[hub_name] = 0

    # ── Event hooks ───────────────────────────────────────────────────────────

    def on_route(self, kind: "RequestKind", result: "DispatchResult") -> None:
        """
        Z_STORM + REROUTE_STORM: call after every PhiCairrnRouter.route().

        Tracks per-hub z-awareness streaks and HOME-reroute streaks.
        Does NOT suppress anything — use on_double_route() for suppression.
        """
        hub = result.hub

        # Z_STORM
        z = abs(result.z_awareness)
        if z >= self._z_threshold:
            streak = self._z_storm_streak.get(hub, 0) + 1
            self._z_storm_streak[hub] = streak
            if streak >= self._z_storm_max:
                _log.warning(
                    "CairrnWatchdog [Z_STORM] hub=%s |z|=%.2f for %d consecutive "
                    "routes — shard handlers may not be draining the spike",
                    hub, z, streak,
                )
                self._total_z_storm += 1
                self._z_storm_streak[hub] = 0
        else:
            self._z_storm_streak[hub] = 0

        # REROUTE_STORM
        if result.rerouted:
            streak = self._reroute_streak.get(hub, 0) + 1
            self._reroute_streak[hub] = streak
            if streak >= self._reroute_max:
                tau = self._bridge._hubs[hub].tau if hub in self._bridge._hubs else -1.0
                _log.warning(
                    "CairrnWatchdog [REROUTE_STORM] hub=%s rerouted HOME "
                    "%d consecutive times — τ=%.1f may be too short",
                    hub, streak, tau,
                )
                self._total_reroute_storm += 1
                self._reroute_streak[hub] = 0
        else:
            self._reroute_streak[hub] = 0

    def on_double_route(self, kind: "RequestKind") -> bool:
        """
        DOUBLE_ROUTE: call at the TOP of route() before the pipeline runs.

        Returns True if the call should be suppressed (same RequestKind fired
        twice within poll_ms × 3 ms).

        Thread-safe: _dr_lock serialises the read-check-write to prevent
        two concurrent threads from both seeing last=0.0 and both proceeding.

        During batch warmup (begin_batch_warmup / end_batch_warmup) the check
        is bypassed entirely so rapid history replay does not flood the log.
        """
        now = time.monotonic()
        key = kind.value if hasattr(kind, "value") else str(kind)

        with self._dr_lock:
            if self._dr_warmup_active:
                self._last_route_ts[key] = now
                return False
            last  = self._last_route_ts.get(key, 0.0)
            rapid = (now - last) < (self._poll_ms * 3 / 1000.0)
            if rapid and last > 0.0:
                self._total_double_route += 1
                count     = self._total_double_route
                window_ms = self._poll_ms * 3
            else:
                self._last_route_ts[key] = now
                return False

        _log.warning(
            "CairrnWatchdog [DOUBLE_ROUTE] %s fired twice within %.0fms  total=%d",
            key, window_ms, count,
        )
        return True

    def begin_batch_warmup(self) -> None:
        """
        Suspend DOUBLE_ROUTE detection for bulk warmup replay.

        Call before warm_from_history() / session-restore loops to prevent
        rapid legitimate re-routes from flooding the warning log.
        Clears the timestamp table on entry so stale keys don't trip the
        detector immediately after end_batch_warmup() is called.
        """
        with self._dr_lock:
            self._dr_warmup_active = True
            self._last_route_ts.clear()

    def end_batch_warmup(self) -> None:
        """
        Resume DOUBLE_ROUTE detection after bulk warmup replay.

        Clears timestamps again so the first real-time route after warmup
        gets a clean slate (no false positive from the last warmup event).
        """
        with self._dr_lock:
            self._dr_warmup_active = False
            self._last_route_ts.clear()

    def on_reroute(self, hub_name: str) -> None:
        """Explicit reroute notification (convenience wrapper for on_route)."""
        streak = self._reroute_streak.get(hub_name, 0) + 1
        self._reroute_streak[hub_name] = streak
        if streak >= self._reroute_max:
            _log.warning(
                "CairrnWatchdog [REROUTE_STORM] hub=%s rerouted HOME %d times",
                hub_name, streak,
            )
            self._total_reroute_storm += 1
            self._reroute_streak[hub_name] = 0

    # ── Status ────────────────────────────────────────────────────────────────

    def status_line(self) -> str:
        """One-line health summary.  Mirrors PhiRaceWatcher.status_line()."""
        return (
            f"CairrnWatch  ticks={self._total_ticks}"
            f"  coh_hang={self._total_coherence_hang}"
            f"  z_storm={self._total_z_storm}"
            f"  reroute_storm={self._total_reroute_storm}"
            f"  prop_stall={self._total_propagation_stall}"
            f"  double_route={self._total_double_route}"
        )

    def per_hub_status(self) -> Dict[str, dict]:
        """Per-hub streak snapshot for diagnostics."""
        hubs = set(self._hang_streak) | set(self._z_storm_streak) | set(self._reroute_streak)
        return {
            hub: {
                "hang_streak":    self._hang_streak.get(hub, 0),
                "z_storm_streak": self._z_storm_streak.get(hub, 0),
                "reroute_streak": self._reroute_streak.get(hub, 0),
            }
            for hub in sorted(hubs)
        }
