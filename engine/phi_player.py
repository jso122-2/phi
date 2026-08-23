"""
PhiPlayer — CAIRRN-aware playback controller.

Architecture
------------
PhiPlayer closes the feedback loop between what the user *listens to* and
how CAIRRN shapes the *next* shuffle order.

    play_next()           → advance shuffle cursor
                          → peek_and_preload() upcoming tracks into hot cache
                          → step() the dispatcher (CAIRRN CODE tick + hot loader)
                          → return Track to play

    report_play(fraction) → record PlayEvent
                          → inject play fraction into HOME / CODE hubs
                          → force-propagate harmonic shards (2 steps)
                          → CAIRRN gravity vector shifts for next prefeed()

Play-fraction → injection mapping
----------------------------------
The play fraction (0.0 = immediate skip, 1.0 = listened to end) is the
only feedback signal.  Thresholds are chosen to match listener intent:

    fraction ≥ 0.80  →  loved: HOME + CODE injection at full fraction
    fraction  0.40–0.79  →  heard: HOME injection only (moderate resonance)
    fraction < 0.40  →  skipped: no injection (silence is not negative signal)

HOME injection  → reinforces baseline resonance for this shard region
CODE injection  → directly shifts shuffle gravity toward similar tracks

After injection, a 2-step harmonic propagation spreads the activation
through neighbouring shards.  The next shuffle prefeed() reads the updated
shard activations and reorders the gravity vector accordingly.

PlayEvent
---------
Immutable record of one play session.  Stored in a ring buffer on the player.
External callers can read player.history to feed telemetry, analytics, or
learning loops.

Usage
-----
    # Wire at startup
    session = make_phi_session()
    session.build()
    shuffle = make_prefeed_shuffle(session)
    shuffle.seed()
    hot_loader = CAIRRNHotLoader()
    dispatcher = make_dispatcher(harmonic_index=session.harmonic_index,
                                 shuffle=shuffle, hot_loader=hot_loader)
    player = PhiPlayer(shuffle=shuffle, dispatcher=dispatcher,
                       hot_loader=hot_loader)

    # Player loop (called from audio thread)
    track = player.play_next()
    # ... audio plays ...
    event = player.report_play(play_fraction=0.95)
    print(event.track.display_name, "→ HOME+CODE injected")
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, List, Optional

from engine.cairrn_dispatch import CAIRRNDispatcher, PhiAction, PhiActionKind, make_dispatcher
from engine.hot_loader import CAIRRNHotLoader
from engine.prefeed_shuffle import CAIRRNPrefeedShuffle, make_prefeed_shuffle
from phi._track import Track


# ---------------------------------------------------------------------------
# Play-fraction thresholds (public — callers may inspect)
# ---------------------------------------------------------------------------

FRAC_LOVED: float = 0.80   # HOME + CODE injection
FRAC_HEARD: float = 0.40   # HOME injection only
# < FRAC_HEARD → silent skip, no injection


# ---------------------------------------------------------------------------
# PlayEvent
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PlayEvent:
    """
    Immutable record of one play session.

    Attributes
    ----------
    track         : Track that was played
    track_idx     : index in the PhiGraphSnapshot
    started_at    : monotonic timestamp when play_next() was called
    ended_at      : monotonic timestamp when report_play() was called
    play_fraction : 0.0–1.0 — fraction of track played before report
    skipped       : True when play_fraction < FRAC_HEARD
    home_injected : HOME hub injection value (0.0 if none)
    code_injected : CODE hub injection value (0.0 if none)
    """

    track:          Track
    track_idx:      int
    started_at:     float
    ended_at:       float
    play_fraction:  float
    skipped:        bool
    home_injected:  float
    code_injected:  float

    @property
    def duration_s(self) -> float:
        return max(0.0, self.ended_at - self.started_at)

    def as_dict(self) -> dict:
        return {
            "track":          self.track.display_name,
            "track_idx":      self.track_idx,
            "duration_s":     round(self.duration_s, 3),
            "play_fraction":  round(self.play_fraction, 4),
            "skipped":        self.skipped,
            "home_injected":  round(self.home_injected, 6),
            "code_injected":  round(self.code_injected, 6),
        }


# ---------------------------------------------------------------------------
# PhiPlayer
# ---------------------------------------------------------------------------


class PhiPlayer:
    """
    CAIRRN-aware playback controller.

    Wires CAIRRNPrefeedShuffle, CAIRRNDispatcher, and CAIRRNHotLoader into
    a single play → feedback loop.

    Parameters
    ----------
    shuffle        : CAIRRNPrefeedShuffle — must have seed() already called
    dispatcher     : CAIRRNDispatcher — harmonic_index must be attached
    hot_loader     : CAIRRNHotLoader — optional; enables peek_and_preload()
    preload_ahead  : number of upcoming tracks to hot-load on each play_next()
                     (default 3)
    max_history    : PlayEvent ring-buffer capacity (default 200)
    """

    def __init__(
        self,
        shuffle: CAIRRNPrefeedShuffle,
        dispatcher: CAIRRNDispatcher,
        hot_loader: Optional[CAIRRNHotLoader] = None,
        preload_ahead: int = 3,
        max_history: int = 200,
    ) -> None:
        self._shuffle = shuffle
        self._dispatcher = dispatcher
        self._hot_loader = hot_loader
        self._preload_ahead = max(1, int(preload_ahead))

        self._current_idx: Optional[int] = None
        self._current_track: Optional[Track] = None
        self._current_start: float = 0.0
        self._in_play: bool = False

        self._history: Deque[PlayEvent] = deque(maxlen=max_history)
        self._total_plays: int = 0
        self._total_skips: int = 0

    # ------------------------------------------------------------------
    # Playback
    # ------------------------------------------------------------------

    def play_next(self) -> Track:
        """
        Advance the shuffle cursor and return the next track to play.

        Side effects
        ------------
        1. Advances shuffle cursor via shuffle.next()
        2. Calls peek_and_preload() for the next *preload_ahead* tracks
           into the hot cache (if hot_loader is attached)
        3. Steps the dispatcher — runs the hot loader and CAIRRN CODE tick

        Returns
        -------
        Track — caller is responsible for actually playing the audio.

        Raises
        ------
        RuntimeError if the shuffle has no active order (seed() not called).
        RuntimeError if the snapshot is not built.
        """
        snap = self._shuffle._session.snapshot
        if snap is None:
            raise RuntimeError(
                "PhiPlayer: session snapshot not built — call session.build() "
                "and shuffle.seed() before play_next()."
            )

        idx = self._shuffle.next()
        if idx >= snap.N:
            raise RuntimeError(
                f"PhiPlayer: track index {idx} out of snapshot range (N={snap.N})."
            )

        self._current_idx = idx
        self._current_track = snap.tracks[idx]
        self._current_start = time.monotonic()
        self._in_play = True

        # Hot-load upcoming tracks in background before the cursor reaches them
        if self._hot_loader is not None:
            self._shuffle.peek_and_preload(self._hot_loader, n=self._preload_ahead)

        # NOTE: dispatcher.step() removed here — run_tick_loop() owns all
        # step() calls when driving the player from an async context.
        # If using this player outside an async context (e.g. tests, CLI),
        # call dispatcher.step() manually after play_next() as needed.

        return self._current_track

    def report_play(self, play_fraction: float) -> PlayEvent:
        """
        Record the outcome of the current track and feed it back into CAIRRN.

        Call this when the track ends naturally (play_fraction ≈ 1.0) or
        when the user skips (play_fraction = elapsed / total_duration).

        Parameters
        ----------
        play_fraction : float in [0.0, 1.0]
            0.0 = skipped immediately; 1.0 = played to end.

        Side effects
        ------------
        - Injects into HOME hub when play_fraction ≥ FRAC_HEARD (0.40)
        - Injects into CODE hub when play_fraction ≥ FRAC_LOVED (0.80)
        - Force-dispatches 2-step harmonic PROPAGATE so shard activations
          update before the next shuffle.prefeed() reads them
        - Records PlayEvent in history ring buffer

        Returns
        -------
        PlayEvent — immutable record of this play session.

        Raises
        ------
        RuntimeError if play_next() has not been called yet.
        """
        if self._current_track is None or not self._in_play:
            raise RuntimeError(
                "PhiPlayer: call play_next() before report_play()."
            )

        ended_at = time.monotonic()
        frac = float(max(0.0, min(1.0, play_fraction)))

        home_val, code_val = self._compute_injections(frac)
        self._inject_feedback(home_val, code_val)

        event = PlayEvent(
            track=self._current_track,
            track_idx=self._current_idx,       # type: ignore[arg-type]
            started_at=self._current_start,
            ended_at=ended_at,
            play_fraction=frac,
            skipped=frac < FRAC_HEARD,
            home_injected=home_val,
            code_injected=code_val,
        )

        self._history.append(event)
        self._total_plays += 1
        if event.skipped:
            self._total_skips += 1

        self._in_play = False
        return event

    # ------------------------------------------------------------------
    # State inspection
    # ------------------------------------------------------------------

    @property
    def current_track(self) -> Optional[Track]:
        """Track currently in play (set by play_next, cleared after report_play)."""
        return self._current_track if self._in_play else None

    @property
    def history(self) -> list[PlayEvent]:
        """All recorded PlayEvents, oldest first."""
        return list(self._history)

    @property
    def total_plays(self) -> int:
        return self._total_plays

    @property
    def skip_rate(self) -> float:
        """Fraction of tracks that were skipped (< FRAC_HEARD)."""
        if self._total_plays == 0:
            return 0.0
        return self._total_skips / self._total_plays

    def state(self) -> dict:
        """Serialisable player state snapshot."""
        last = self._history[-1] if self._history else None
        d: dict = {
            "in_play":      self._in_play,
            "current":      self._current_track.display_name if self._in_play and self._current_track else None,
            "current_idx":  self._current_idx if self._in_play else None,
            "total_plays":  self._total_plays,
            "total_skips":  self._total_skips,
            "skip_rate":    round(self.skip_rate, 4),
            "history_len":  len(self._history),
            "last_event":   last.as_dict() if last else None,
            "shuffle":      self._shuffle.state(),
            "dispatcher":   self._dispatcher.state(),
        }
        if self._hot_loader is not None:
            d["hot_loader_metrics"] = self._hot_loader.metrics.as_dict()
        return d

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _compute_injections(self, frac: float) -> tuple[float, float]:
        """
        Return (home_val, code_val) for a given play fraction.

        frac ≥ FRAC_LOVED (0.80) → HOME=frac, CODE=frac
        frac ≥ FRAC_HEARD (0.40) → HOME=frac, CODE=0.0
        frac  < FRAC_HEARD       → HOME=0.0,  CODE=0.0
        """
        if frac >= FRAC_LOVED:
            return frac, frac
        if frac >= FRAC_HEARD:
            return frac, 0.0
        return 0.0, 0.0

    def _inject_feedback(self, home_val: float, code_val: float) -> None:
        """
        Inject play-fraction values into the harmonic index via force_dispatch,
        then propagate 2 steps so shard activations are current for the next
        shuffle.prefeed() call.

        Uses force_dispatch (bypasses coherence gate) because feedback is an
        authoritative signal — we want it reflected immediately, not queued.
        """
        if home_val > 0.0:
            self._dispatcher.force_dispatch(
                PhiAction(
                    kind=PhiActionKind.HUB_INJECT,
                    payload={"hub_name": "HOME", "value": home_val},
                    priority=-1,  # urgent
                )
            )
        if code_val > 0.0:
            self._dispatcher.force_dispatch(
                PhiAction(
                    kind=PhiActionKind.HUB_INJECT,
                    payload={"hub_name": "CODE", "value": code_val},
                    priority=-1,
                )
            )
        if home_val > 0.0 or code_val > 0.0:
            self._dispatcher.force_dispatch(
                PhiAction(
                    kind=PhiActionKind.PROPAGATE,
                    payload={"steps": 2},
                    priority=-1,
                )
            )

    def __repr__(self) -> str:
        current = self._current_track.display_name if self._in_play and self._current_track else "idle"
        return (
            f"<PhiPlayer "
            f"plays={self._total_plays} "
            f"skip_rate={self.skip_rate:.2f} "
            f"current={current!r}>"
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_phi_player(
    shuffle: CAIRRNPrefeedShuffle,
    dispatcher: CAIRRNDispatcher,
    hot_loader: Optional[CAIRRNHotLoader] = None,
    preload_ahead: int = 3,
    max_history: int = 200,
) -> PhiPlayer:
    """
    Construct a PhiPlayer bound to the given subsystems.

    Parameters
    ----------
    shuffle       : CAIRRNPrefeedShuffle (seed() must be called before play_next())
    dispatcher    : CAIRRNDispatcher
    hot_loader    : optional CAIRRNHotLoader — enables track preloading
    preload_ahead : upcoming tracks to hot-load per play_next() call (default 3)
    max_history   : PlayEvent ring-buffer capacity (default 200)
    """
    return PhiPlayer(
        shuffle=shuffle,
        dispatcher=dispatcher,
        hot_loader=hot_loader,
        preload_ahead=preload_ahead,
        max_history=max_history,
    )


# ---------------------------------------------------------------------------
# PhiPipeline — fully-wired phi system
# ---------------------------------------------------------------------------


@dataclass
class PhiPipeline:
    """
    All phi components, fully wired and ready to use.

    Returned by ``make_phi_pipeline()``.  Every connection that the individual
    factories leave as a manual step (attach_dispatcher, register_hover, seed)
    is already made by the time this object is returned.

    Attributes
    ----------
    session    : PhiTracerSession  — built + snapshot available
    shuffle    : CAIRRNPrefeedShuffle — seeded, ready for next()
    hot_loader : CAIRRNHotLoader   — background prefetch cache
    dispatcher : CAIRRNDispatcher  — gate + queue + signal_hover()
    player     : PhiPlayer         — play_next() / report_play() loop
    tracer     : CursorTracer      — hover-region monitor, dispatcher attached
    """
    session:    object  # PhiTracerSession — typed as object to avoid circular
    shuffle:    CAIRRNPrefeedShuffle
    hot_loader: CAIRRNHotLoader
    dispatcher: CAIRRNDispatcher
    player:     PhiPlayer
    tracer:     object  # CursorTracer — typed as object to avoid circular

    def state(self) -> dict:
        """Serialisable snapshot of all wired components."""
        return {
            "player":     self.player.state(),
            "dispatcher": self.dispatcher.state(),
            "tracer":     self.tracer.snapshot() if hasattr(self.tracer, "snapshot") else {},
        }


def make_phi_pipeline(
    session: object,
    hover_regions: Optional[List] = None,
    preload_ahead: int = 3,
    max_history: int = 200,
    tracer_hub: str = "CODE",
    tracer_max_samples: int = 200,
    dispatcher_tau: float = 10.0,
    shuffle_exploration: float = 0.15,
    shuffle_rng_seed: int = 7,
) -> PhiPipeline:
    """
    Wire the complete phi pipeline from a built ``PhiTracerSession``.

    ``session.build()`` **must** be called before this function.

    Wiring sequence (bottom-up)
    ---------------------------
    1. ``CAIRRNPrefeedShuffle`` created + seeded from session
    2. ``CAIRRNHotLoader`` created
    3. ``CAIRRNDispatcher`` created with hot_loader + harmonic_index
    4. ``PhiPlayer`` created bound to shuffle + dispatcher + hot_loader
    5. ``CursorTracer`` created, ``attach_dispatcher(dispatcher)`` called
    6. Any ``hover_regions`` registered on the tracer

    Parameters
    ----------
    session          : PhiTracerSession — must have build() already called
    hover_regions    : list of ``HoverRegion`` — registered on the tracer so
                       cursor dwell fires ``dispatcher.signal_hover()`` for each
    preload_ahead    : tracks to hot-load ahead on each play_next() (default 3)
    max_history      : PhiPlayer PlayEvent ring-buffer capacity (default 200)
    tracer_hub       : CAIRRN hub the tracer routes through (default "CODE")
    tracer_max_samples: CursorTracer ring-buffer size (default 200)
    dispatcher_tau   : coherence decay constant for the dispatcher (default 10.0)
    shuffle_exploration: shuffle noise scale (default 0.15)
    shuffle_rng_seed : PrefeedShuffle RNG seed (default 7)

    Returns
    -------
    PhiPipeline — all components wired and ready to use.

    Raises
    ------
    RuntimeError
        If ``session.snapshot`` is None (session.build() was not called).
    """
    # Late import to avoid circular at module level
    from engine.cursor_tracer import CursorTracer, HoverRegion  # noqa: F401

    # Guard: snapshot must exist
    snap = getattr(session, "snapshot", None)
    if snap is None:
        raise RuntimeError(
            "make_phi_pipeline: session.snapshot is None — call session.build() first."
        )

    harmonic_index = getattr(session, "harmonic_index", None)
    if harmonic_index is None:
        raise RuntimeError(
            "make_phi_pipeline: session.harmonic_index is None — session may not be fully initialised."
        )

    # 1. Shuffle
    shuffle = make_prefeed_shuffle(
        session,  # type: ignore[arg-type]
        exploration=shuffle_exploration,
        rng_seed=shuffle_rng_seed,
    )
    shuffle.seed()

    # 2. Hot loader
    hot_loader = CAIRRNHotLoader()

    # 3. Dispatcher
    dispatcher = make_dispatcher(
        harmonic_index=harmonic_index,
        session=session,
        shuffle=shuffle,
        hot_loader=hot_loader,
        tau=dispatcher_tau,
    )

    # 4. Player
    player = make_phi_player(
        shuffle=shuffle,
        dispatcher=dispatcher,
        hot_loader=hot_loader,
        preload_ahead=preload_ahead,
        max_history=max_history,
    )

    # 4b. Wire player back into dispatcher so SHUFFLE_NEXT / SHUFFLE_SEED
    #     write-back player state directly — enables the bus-driven UI path.
    dispatcher.attach_player(player)

    # 5. Tracer — attach dispatcher so hover dwell fires signal_hover()
    tracer: CursorTracer = CursorTracer(
        max_samples=tracer_max_samples,
        hub=tracer_hub,
    )
    tracer.attach_dispatcher(dispatcher)

    # 6. Register hover regions
    if hover_regions:
        for region in hover_regions:
            tracer.register_hover(region)

    return PhiPipeline(
        session=session,
        shuffle=shuffle,
        hot_loader=hot_loader,
        dispatcher=dispatcher,
        player=player,
        tracer=tracer,
    )
