# -*- coding: utf-8 -*-
"""phi.engine.cairrn.router — CAIRRN request-routing substrate for phi.

All phi operations flow through this router before any computation runs.
The router wraps a CairnBridge and provides:

  - route(kind, metric, payload) → DispatchResult
  - route_page_nav(page_name)    → DispatchResult
  - subscribe(shard, handler)    — register shard activation handlers
  - unsubscribe(shard, handler)
  - report()                     — formatted hub state table
  - shutdown()                   — clean up the handler executor

FOREST FLOOR TOPOLOGY (formula-derived, phi-specific)
──────────────────────────────────────────────────────

Each RequestKind routes to a hub.  Hub χ values determine natural shards
via the neg_exp formula.  Priority tiers derive from shard position.

    RequestKind        Hub            χ      shard  priority
    ─────────────────────────────────────────────────────────
    ML_INFERENCE    →  agent-context  0.03   0      DEFER
    POLL_TICK       →  CODE           0.99   1      NORMAL
    TRACK_TRANSITION→  CODE           0.99   1      NORMAL
    SKIP_EVENT      →  CODE           0.99   1      NORMAL
    PAGE_NAV        →  HOME           1.54   2      NORMAL
    CLAP_INFERENCE  →  MATH           1.96   3      NORMAL
    SIMILARITY_SEARCH→ MATH           1.96   3      NORMAL
    ENRICH_DISPATCH →  COMMANDS       2.67   7      URGENT

    shards 4–6 are propagation waveguides (no hub assigned).

SUBSCRIBER MODEL
────────────────
Register shard handlers at startup without modifying app.py:

    router.subscribe(shard=3, handler=clap_model.on_activation)
    router.subscribe(shard=7, handler=enrich_daemon.on_urgent)

Handlers are called asynchronously (ThreadPoolExecutor) with signature:
    handler(result: DispatchResult, payload: dict) → None

Keep handlers non-blocking — offload heavy work to a background thread.
"""
from __future__ import annotations

import concurrent.futures
import logging
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from phi.engine.cairrn._constants import (
    PAGE_HUB,
    PROPAGATE_STEPS,
    PRIORITY_LABELS,
    shard_priority,
    LOCAL_FRICTION,
    D_GATE_THRESHOLD,
    _Z_FLOOR,
    COHERENCE_FLOOR,
    N_SHARDS,
)
from workers.cairrn.formulas import f_envelope_min, f_envelope_max
from phi.engine.cairrn.bridge import CairnBridge

if TYPE_CHECKING:
    from phi.engine.cairrn.watchdog import CairrnWorkerWatchdog

_log = logging.getLogger("phi.cairrn.router")


# ── RequestKind ───────────────────────────────────────────────────────────────

class RequestKind(str, Enum):
    """Every phi operation that flows through CAIRRN."""
    POLL_TICK         = "POLL_TICK"          # 150 ms heartbeat (decimated to ~1.5 s)
    PAGE_NAV          = "PAGE_NAV"           # user switches UI page
    TRACK_TRANSITION  = "TRACK_TRANSITION"   # one track ends, next begins
    ML_INFERENCE      = "ML_INFERENCE"       # BPM / mood / key / energy annotation
    CLAP_INFERENCE    = "CLAP_INFERENCE"     # heavy CLAP audio embedding batch
    SIMILARITY_SEARCH = "SIMILARITY_SEARCH"  # cosine search over mood_vec index
    ENRICH_DISPATCH   = "ENRICH_DISPATCH"    # AcoustID + MusicBrainz pipeline
    SKIP_EVENT        = "SKIP_EVENT"         # user skipped a track (burst pressure)
    RIDER_ACTION      = "RIDER_ACTION"       # direct button press — Rider steering impulse
    PLAYLIST_BUILD    = "PLAYLIST_BUILD"     # ML playlist studio batch build


# Kinds that originate from direct user interaction (the Rider's hand on the controls).
# Background signals (POLL_TICK, ML_INFERENCE, CLAP_INFERENCE, ENRICH_DISPATCH) are
# excluded — they are the river flowing on its own, not the Rider steering.
RIDER_KINDS: frozenset = frozenset({
    RequestKind.SKIP_EVENT,
    RequestKind.PAGE_NAV,
    RequestKind.RIDER_ACTION,
})


# ── Hub assignment (RequestKind → hub name) ───────────────────────────────────

REQUEST_HUB: Dict[RequestKind, str] = {
    RequestKind.POLL_TICK:         "CODE",            # shard 1 — playback context
    RequestKind.PAGE_NAV:          "HOME",            # shard 2 — library topology
    RequestKind.TRACK_TRANSITION:  "CODE",            # shard 1 — context shift
    RequestKind.ML_INFERENCE:      "agent-context",   # shard 0 — background writes
    RequestKind.CLAP_INFERENCE:    "MATH",            # shard 3 — embedding space
    RequestKind.SIMILARITY_SEARCH: "MATH",            # shard 3 — embedding space
    RequestKind.ENRICH_DISPATCH:   "COMMANDS",        # shard 7 — high-priority
    RequestKind.SKIP_EVENT:        "CODE",            # shard 1 — burst skip pressure
    RequestKind.RIDER_ACTION:      "CODE",            # shard 1 — Rider button press
    RequestKind.PLAYLIST_BUILD:    "MATH",            # shard 3 — embedding space (batch scan)
}

        # Re-export PAGE_HUB so callers can import it from here
# (avoids knowing the _constants import path)
__all__ = [
    "RequestKind",
    "REQUEST_HUB",
    "RIDER_KINDS",
    "PAGE_HUB",
    "DispatchResult",
    "PhiCairrnRouter",
]


# ── DispatchResult ────────────────────────────────────────────────────────────

@dataclass
class DispatchResult:
    """
    Result of routing one phi request through the CAIRRN pipeline.

    Every call to PhiCairrnRouter.route() returns one of these.
    Subscribers and callers use it to decide whether to compute or defer.
    """
    kind:        RequestKind
    hub:         str
    shard:       int         # neg_exp shard [0–7] — routing address on the ring
    modulated:   float       # Ana-Chi Layer 1 output
    coherent:    bool        # Layer 3: False → cached result is stale
    coherence:   float       # raw coherence score [0, 1] — use for proportional deferral
    rerouted:    bool        # True → was HOME-rerouted due to incoherence
    priority:    int         # 0=DEFER 1=NORMAL 2=HIGH 3=URGENT
    z_awareness: float       # rolling z-score of this hub's activation history
    metric:      float       # raw input metric before modulation
    is_rider:    bool        = False  # True → signal originated from direct user interaction
    payload:     Dict[str, Any] = field(default_factory=dict)
    friction_d:  float       = 0.0   # D friction gate value — action suppressed if > D_GATE_THRESHOLD

    @property
    def should_act(self) -> bool:
        """
        True when a subscriber should execute its work this cycle.

        Acts when ALL of the following hold:
          - Hub is incoherent (cached result genuinely stale) OR z-spike present
          - D friction gate passes (friction delta ≤ D_GATE_THRESHOLD)

        The D gate suppresses over-firing on minor coherence drops when local
        friction variance is high:
            D = |fl − (Ti · |x/Z| + βt)|
        where fl=LOCAL_FRICTION, Ti=propagation steps, x=modulated, Z=|z_awareness|, βt=coherence.
        """
        incoherent_or_spike = not self.coherent or abs(self.z_awareness) >= 2.5
        friction_ok = self.friction_d <= D_GATE_THRESHOLD
        return incoherent_or_spike and friction_ok

    @property
    def priority_label(self) -> str:
        return PRIORITY_LABELS[self.priority]

    def __str__(self) -> str:
        flag     = "⚠ INCOHERENT" if not self.coherent else "✓"
        z_flag   = f" ⚡z={self.z_awareness:+.2f}" if abs(self.z_awareness) >= 2.5 else ""
        r_flag   = " 🎯RIDER" if self.is_rider else ""
        return (
            f"CAIRRN/{self.kind.value}  hub={self.hub}  shard={self.shard}"
            f"  mod={self.modulated:.3f}  pri={self.priority_label}  {flag}{z_flag}{r_flag}"
        )


# ── PhiCairrnRouter ───────────────────────────────────────────────────────────

class PhiCairrnRouter:
    """
    CAIRRN request-routing substrate for phi.

    Wraps a CairnBridge and provides:
      - route(kind, metric, payload) → DispatchResult
      - subscribe(shard, handler)    — register shard activation handlers
      - report()                     — formatted hub state table
      - shutdown()                   — clean up the handler executor

    All phi operations pass through route().  The router runs the full
    three-layer CAIRRN pipeline, propagates the harmonic ring, then calls
    any registered shard handlers before returning the DispatchResult.

    Thread-safe: subscriber list is protected by a lock.
    """

    def __init__(
        self,
        bridge:   CairnBridge,
        watchdog: "CairrnWorkerWatchdog | None" = None,
    ) -> None:
        self._bridge   = bridge
        self._watchdog = watchdog
        self._lock     = threading.Lock()

        # shard → list of handler callables
        self._handlers: Dict[int, List[Callable]] = {i: [] for i in range(8)}

        # Non-blocking handler dispatch — route() returns immediately.
        # max_workers=4 covers concurrent bursts across priority tiers.
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=4,
            thread_name_prefix="cairrn-shard",
        )

        # Propagation steps per kind — loaded from _constants.PROPAGATE_STEPS
        self._propagate_steps: Dict[str, int] = dict(PROPAGATE_STEPS)

    # ── Public API ────────────────────────────────────────────────────────────

    def route(
        self,
        kind:    RequestKind,
        metric:  float,
        payload: Optional[Dict[str, Any]] = None,
    ) -> DispatchResult:
        """
        Route a phi request through the full CAIRRN pipeline.

        1. Look up the request's home hub from REQUEST_HUB
        2. Run bridge.step(hub, metric) — all three CAIRRN layers
        3. Propagate activation through the harmonic ring
        4. Call all handlers registered on the result's shard
        5. Return DispatchResult to the caller

        Args
        ----
        kind    : the type of phi operation being routed
        metric  : normalised [0, 1] signal for this request
        payload : optional dict forwarded verbatim to shard handlers

        Returns
        -------
        DispatchResult with shard, priority, coherence, and z-awareness
        """
        payload = payload or {}

        # DOUBLE_ROUTE guard — suppress rapid re-entrant duplicates
        if self._watchdog is not None and self._watchdog.on_double_route(kind):
            hub_name   = REQUEST_HUB.get(kind, "HOME")
            hub        = self._bridge._hubs.get(hub_name)
            shard      = hub.shard if hub else 0
            dr_priority = shard_priority(shard)
            # Apply cold-start escalation even on suppressed routes so subscribers
            # still see NORMAL priority for annotation-cold tracks.
            if (
                kind is RequestKind.ML_INFERENCE
                and dr_priority == 0
                and payload.get("no_annotations")
            ):
                dr_priority = 1
            return DispatchResult(
                kind=kind, hub=hub_name, shard=shard,
                modulated=0.0, coherent=True, coherence=1.0, rerouted=False,
                priority=dr_priority, z_awareness=0.0,
                metric=float(metric), is_rider=(kind in RIDER_KINDS),
                payload=payload,
            )

        hub_name = REQUEST_HUB.get(kind, "HOME")
        pipe     = self._bridge.step(hub_name, float(metric))

        steps = self._propagate_steps.get(kind.value, 1)
        self._bridge.propagate(steps=steps)
        self._bridge.decay_all()

        # D friction gate — D = |fl − (Ti · |x/Z| + βt)|
        # Ti = propagation steps, x = modulated, Z = |z_awareness|, βt = coherence
        _z = max(abs(pipe.z_awareness), _Z_FLOOR)
        friction_d = abs(LOCAL_FRICTION - (steps * abs(pipe.modulated / _z) + pipe.coherence))

        # Envelope clip (Gap 5) — clamp modulated to [A_xmin, A_xmax]
        # All proxy: a=1.0, w=1.0, k_consensus=1.0, v=gradient, r=shard/ring
        _v = abs(float(metric) - pipe.modulated)          # velocity / gradient proxy
        _r = pipe.shard / max(N_SHARDS - 1, 1)            # normalized ring position
        env_max = f_envelope_max(
            a=1.0, w=1.0,
            z=pipe.z_awareness, c=pipe.modulated,
            k_consensus=1.0, v=_v, i=pipe.shard, beta_t=pipe.coherence,
        )
        env_min = f_envelope_min(
            k=COHERENCE_FLOOR, r=_r, g=LOCAL_FRICTION,
            z=pipe.z_awareness, x=pipe.modulated,
            beta_t=pipe.coherence, beta_h=COHERENCE_FLOOR,
        )
        env_floor   = max(0.0, env_min)
        env_ceiling = max(env_floor, env_max)              # guard against inverted bounds
        modulated   = max(env_floor, min(pipe.modulated, env_ceiling))

        priority = shard_priority(pipe.shard)

        # Cold-start override: when a track has no annotations yet, ML_INFERENCE
        # is elevated from DEFER (0) to NORMAL (1) for that one dispatch so the
        # annotation worker fires ahead of other DEFER-priority background tasks.
        # The flag is set by ForestFloor.leaf_falls(no_annotations=True) and
        # cleared automatically after this dispatch — no persistent state change.
        if (
            kind is RequestKind.ML_INFERENCE
            and priority == 0                      # DEFER — only escalate from bottom
            and payload.get("no_annotations")
        ):
            priority = 1    # NORMAL — same tier as CODE/HOME/MATH

        result   = DispatchResult(
            kind=kind, hub=pipe.hub, shard=pipe.shard,
            modulated=modulated, coherent=pipe.coherent,
            coherence=pipe.coherence, rerouted=pipe.rerouted,
            priority=priority, z_awareness=pipe.z_awareness,
            metric=float(metric), is_rider=(kind in RIDER_KINDS),
            payload=payload,
            friction_d=friction_d,
        )

        _log.debug("%s", result)
        self._dispatch_handlers(result)

        if self._watchdog is not None:
            self._watchdog.on_route(kind, result)

        return result

    def route_key(self, action: str, hub: str, metric: float) -> DispatchResult:
        """
        Route a direct key / button press through the CAIRRN pipeline.

        Called from JimKeyWatcher after the UI callback has already fired.
        The routing is a side-effect — the action always executes regardless
        of the CAIRRN result.

        Args
        ----
        action : Jim action label ("prev", "play_pause", "shuffle", …)
        hub    : target hub from ACTION_CAIRRN (e.g. "CODE", "COMMANDS")
        metric : normalised steering pressure [0, 1]

        Returns
        -------
        DispatchResult with is_rider=True and payload["action"] = action
        """
        pipe  = self._bridge.step(hub, float(metric))
        steps = self._propagate_steps.get("RIDER_ACTION", 2)
        self._bridge.propagate(steps=steps)
        self._bridge.decay_all()

        priority = shard_priority(pipe.shard)
        result   = DispatchResult(
            kind=RequestKind.RIDER_ACTION, hub=pipe.hub, shard=pipe.shard,
            modulated=pipe.modulated, coherent=pipe.coherent,
            coherence=pipe.coherence, rerouted=pipe.rerouted,
            priority=priority, z_awareness=pipe.z_awareness,
            metric=float(metric), is_rider=True,
            payload={"action": action},
        )

        _log.debug("key  action=%s  %s", action, result)
        self._dispatch_handlers(result)

        if self._watchdog is not None:
            self._watchdog.on_route(RequestKind.RIDER_ACTION, result)

        return result

    def route_page_nav(self, page_name: str) -> DispatchResult:
        """
        Route a page-navigation event through the page's actual home hub.

        This is the latency-correct path: opening the genre page fires MATH
        (shard 3), which invalidates a stale similarity index *before* the
        user sees it — not after.

        Args
        ----
        page_name : one of "playing", "library", "genre", "playlist", "mixer"
        """
        hub   = PAGE_HUB.get(page_name, "HOME")
        steps = self._propagate_steps.get("PAGE_NAV", 2)

        pipe = self._bridge.step(hub, 1.0)
        self._bridge.propagate(steps=steps)
        self._bridge.decay_all()

        priority = shard_priority(pipe.shard)
        result   = DispatchResult(
            kind=RequestKind.PAGE_NAV, hub=pipe.hub, shard=pipe.shard,
            modulated=pipe.modulated, coherent=pipe.coherent,
            coherence=pipe.coherence, rerouted=pipe.rerouted,
            priority=priority, z_awareness=pipe.z_awareness,
            metric=1.0, is_rider=True,   # page nav is always a Rider cursor move
            payload={"page": page_name, "hub": hub},
        )

        _log.debug("%s", result)
        self._dispatch_handlers(result)
        return result

    def subscribe(
        self,
        shard:   int,
        handler: Callable[[DispatchResult, Dict[str, Any]], None],
    ) -> None:
        """
        Register a handler for activations on *shard*.

        Handler signature: (result: DispatchResult, payload: dict) → None

        Handlers are dispatched asynchronously in the thread pool.
        Keep them non-blocking — offload heavy work inside the handler.

        Args
        ----
        shard   : ring shard [0–7] to listen on
        handler : callable to invoke on activation
        """
        if not (0 <= shard <= 7):
            raise ValueError(f"shard must be in [0, 7], got {shard}")
        with self._lock:
            self._handlers[shard].append(handler)
        _log.debug("cairrn router: +handler shard=%d  fn=%s",
                   shard, getattr(handler, "__qualname__", repr(handler)))

    def unsubscribe(self, shard: int, handler: Callable) -> None:
        """Remove a previously registered handler from *shard*."""
        with self._lock:
            try:
                self._handlers[shard].remove(handler)
            except ValueError:
                pass

    # ── State inspection ──────────────────────────────────────────────────────

    def hub_state(self) -> Dict[str, dict]:
        return self._bridge.hub_state()

    def index_state(self) -> List[float]:
        return self._bridge.index_state()

    def report(self) -> str:
        """Formatted ASCII table of hub states and the harmonic ring."""
        hubs  = self._bridge.hub_state()
        index = self._bridge.index_state()
        g_coh = self._bridge.global_coherence()
        g_z   = self._bridge.global_z_awareness()
        step  = self._bridge._global_step

        lines = [
            f"\nCAIRRN router  step={step}  global_coh={g_coh:.3f}  global_z={g_z:.3f}",
            "─" * 82,
            f"{'Hub':<16} {'χ':>5} {'τ':>6} {'coh':>6} {'z':>7} {'shard':>5} "
            f"{'steps':>6}  {'basin':<12}  status",
            "─" * 82,
        ]
        for name, state in hubs.items():
            p     = HUB_PARAMS_LOCAL[name]
            coh   = state["coherence"]
            z     = state["z_awareness"]
            shard = state["shard"]
            ok    = "✓" if state["coherent"] else "⚠ INCOHERENT"
            z_tag = f"  ⚡z={z:+.2f}" if abs(z) >= 2.5 else ""
            subs  = len(self._handlers.get(shard, []))
            sub_s = f"  [{subs} sub{'s' if subs != 1 else ''}]" if subs else ""
            lines.append(
                f"{name:<16} {p['chi']:>5.2f} {p['tau']:>6.1f} {coh:>6.3f}"
                f" {z:>+7.3f} {shard:>5d} {state['steps']:>6d}"
                f"  {p['basin']:<12}  {ok}{z_tag}{sub_s}"
            )
        lines.append("─" * 82)
        lines.append(
            "ring:  " + "  ".join(f"[{i}]{v:+.4f}" for i, v in enumerate(index))
        )
        with self._lock:
            sub_map = {i: len(h) for i, h in self._handlers.items() if h}
        if sub_map:
            lines.append(
                "subs:  " + "  ".join(f"shard{i}={n}" for i, n in sorted(sub_map.items()))
            )
        return "\n".join(lines)

    def shutdown(self, wait: bool = True) -> None:
        """Shut down the shard handler executor.  Call on application exit."""
        self._executor.shutdown(wait=wait, cancel_futures=not wait)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _dispatch_handlers(self, result: DispatchResult) -> None:
        with self._lock:
            handlers = list(self._handlers.get(result.shard, []))
        for handler in handlers:
            fut = self._executor.submit(handler, result, result.payload)
            fut.add_done_callback(
                lambda f, h=handler, s=result.shard: self._on_handler_done(f, h, s)
            )

    def _on_handler_done(
        self,
        fut: "concurrent.futures.Future[None]",
        handler: Callable,
        shard: int,
    ) -> None:
        try:
            fut.result()
        except Exception as exc:
            _log.warning(
                "CAIRRN shard-%d handler %s raised: %s",
                shard, getattr(handler, "__qualname__", repr(handler)), exc,
            )


# Local alias so report() can access hub params without a circular import
from phi.engine.cairrn._constants import HUB_PARAMS as HUB_PARAMS_LOCAL
