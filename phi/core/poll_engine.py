# -*- coding: utf-8 -*-
"""phi.core.poll_engine — timer-driven playback polling orchestrator.

Runs at ``POLL_MS`` cadence on the Qt main thread.  Owns the crossfade,
gapless-preload, CAIRRN heartbeat, Now-Playing sync, and end-of-track detection
ticks.  All external state is injected; the engine holds no UI references.

Sub-tick handlers (one job each):
    BeatTick        — beat sim + visualiser energy   (_poll_beat)
    XfadeGaplessTick— crossfade + gapless preload    (_poll_xfade)
    MediaKeysTick   — rate-limited NowPlaying sync   (_poll_media_keys)
    CairnTick       — off-thread CAIRRN heartbeat    (_poll_cairrn)
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Optional

from phi.config import POLL_MS
from phi.core._poll_beat import BeatTick
from phi.core._poll_cairrn import CairnTick
from phi.core._poll_media_keys import MediaKeysTick
from phi.core._poll_state import TickSnapshot
from phi.core._poll_xfade import XfadeGaplessTick

if TYPE_CHECKING:
    from phi.audio.beat import BeatSimulator
    from phi.audio.media_keys import MediaKeyHandler
    from phi.core.player import PlayerEngine
    from phi.core.queue import QueueEngine
    from phi.core.race_watcher import PhiRaceWatcher
    from phi.engine.forest_floor import ForestFloor


class PollEngine:
    """Timer-driven playback poll — orchestrates per-tick sub-handlers.

    Args:
        player:               Audio playback engine.
        queue:                Playback queue.
        transport:            Transport bar widget (``set_seek`` / ``set_playing``).
        race_watcher:         Race-condition guard for double-advance / gapless.
        beat:                 Beat simulator for visualiser energy.
        hyphal:               Hyphal panel visualiser.
        floor:                ForestFloor for CAIRRN heartbeat.
        media_keys:           System media key / Now Playing handler.
        schedule:             Callable(ms, fn) — post fn to the main thread after ms.
        on_advance:           Callback fired at end-of-track (= PhiApp._advance).
        peek_next_path:       Returns the absolute path of the next queued track.
        get_duration:         Returns current track duration (float seconds).
        set_duration:         Stores a freshly fetched duration.
        on_crossfade_handoff: Optional — called with the promoted crossfade path.
        sync_rooms:           Optional — sync mini transport in Library/Playlist/Mixer.
        get_mini:             Optional — returns the mini-player widget (or None).
        wave:                 Optional wave visualiser widget.
        dispatcher:           Optional CAIRRNDispatcher — stepped on each CAIRRN tick.
    """

    def __init__(
        self,
        player: "PlayerEngine",
        queue: "QueueEngine",
        transport,
        race_watcher: "PhiRaceWatcher",
        beat: "BeatSimulator",
        hyphal,
        floor: "ForestFloor",
        media_keys: "MediaKeyHandler",
        schedule:       Callable,
        on_advance:     Callable[[], None],
        peek_next_path: Callable[[], Optional[str]],
        get_duration:   Callable[[], float],
        set_duration:   Callable[[float], None],
        on_crossfade_handoff: Callable[[str], None] | None = None,
        sync_rooms: Callable[[bool], None] | None = None,
        get_mini: Callable[[], object | None] | None = None,
        wave=None,
        dispatcher=None,
    ) -> None:
        self._player = player
        self._queue = queue
        self._transport = transport
        self._race_watcher = race_watcher
        self._schedule = schedule
        self._on_advance = on_advance
        self._get_duration = get_duration
        self._set_duration = set_duration
        self._sync_rooms = sync_rooms
        self._get_mini = get_mini

        self._beat_tick = BeatTick(beat, hyphal, wave)
        self._xfade_tick = XfadeGaplessTick(
            player, queue, race_watcher,
            peek_next_path, on_advance, on_crossfade_handoff,
        )
        self._media_keys_tick = MediaKeysTick(media_keys)
        self._cairrn_tick = CairnTick(floor, dispatcher)
        self._running = False

    def start(self) -> None:
        """Schedule the first poll tick."""
        self._running = True
        self._schedule(POLL_MS, self._poll)

    def stop(self) -> None:
        """Halt polling. Already-queued ticks become no-ops and do not reschedule."""
        self._running = False

    # ──────────────────────────────────────────────────────── main tick ──

    def _poll(self) -> None:
        if not self._running:
            return
        self._race_watcher.poll_tick(self._player, self._queue)

        # Single ObjC snapshot — one lock, one rate(), one currentTime().
        busy, raw_ms, pos = self._player.tick_state()
        snap = TickSnapshot(
            busy=busy,
            raw_ms=raw_ms,
            pos=pos,
            duration=self._get_duration(),
            paused=self._player.paused,
            playing=busy and not self._player.paused,
        )

        self._beat_tick.tick(snap, POLL_MS)   # → snap.energy, snap.on_beat

        if not self._transport.is_seeking and snap.duration > 0 and snap.raw_ms >= 0:
            self._transport.set_seek(min(snap.pos, snap.duration), snap.duration)

        self._xfade_tick.tick(snap)

        if self._get_mini:
            mini = self._get_mini()
            if mini and getattr(mini, "_visible", False) and hasattr(mini, "set_playing"):
                mini.set_playing(snap.playing)  # type: ignore[union-attr]

        if self._sync_rooms:
            self._sync_rooms(snap.playing)

        if (
            self._queue.pos >= 0
            and not snap.paused
            and not snap.busy
            and snap.raw_ms == -1
            and not self._player._xfading
            and not self._xfade_tick.xfade_handled
        ):
            self._xfade_tick.reset_gapless()
            self._on_advance()

        self._media_keys_tick.tick(snap)
        self._cairrn_tick.tick(snap)

        if self._running:
            self._schedule(POLL_MS, self._poll)
