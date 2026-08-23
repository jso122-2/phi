# -*- coding: utf-8 -*-
"""phi.core.player — AVFoundation AVPlayer audio engine.

PlayerEngine owns all playback state.  The public API is identical to the
former python-mpv/libmpv implementation so PollEngine, PlaybackController,
and all callers are unchanged.

Why AVPlayer instead of libmpv
──────────────────────────────
On macOS 26 (Tahoe), libmpv's mpv_create() raises a fatal SIGBUS inside
CoreMedia initialisation.  The mpv binary also crashes.  AVPlayer is the
native macOS audio/video engine and works without issues on any macOS version.

Requires a running event loop on the main thread.  AVPlayer property reads
(currentTime, rate) are thread-safe; transport commands (play/pause/seek) are
marshalled to the main thread via _dispatch_main() to guarantee Cocoa safety.

CMTime representation
─────────────────────
pyobjc represents CMTime as a 4-tuple: (value, timescale, flags, epoch).
A valid time at *s* seconds is: (int(s * TS), TS, 1, 0)
where TS is 1 000 000 (microsecond precision).

Crossfade
─────────
Two independent AVPlayer instances (main + xfade).  The poll loop drives
volume ramps via tick_crossfade(), matching the former libmpv architecture.

Gapless (Phase 2)
──────────────────
queue_next() stores the next path but does not yet preload it.
"""
from __future__ import annotations

import logging
import math
import os
import threading
from typing import Optional

import objc

# ── AVFoundation / CoreMedia bootstrap ────────────────────────────────────────

_AV_LOADED = False

def _ensure_av() -> None:
    global _AV_LOADED
    if _AV_LOADED:
        return
    try:
        objc.loadBundle(
            "AVFoundation",
            bundle_path="/System/Library/Frameworks/AVFoundation.framework",
            module_globals=globals(),
        )
        _AV_LOADED = True
    except Exception as exc:
        raise RuntimeError(f"AVFoundation unavailable: {exc}") from exc


_TS = 1_000_000  # CMTime timescale — microsecond precision


def _cm(seconds: float) -> tuple:
    """Convert seconds to CMTime 4-tuple (value, timescale, flags, epoch)."""
    return (int(seconds * _TS), _TS, 1, 0)


def _secs(cm_time: tuple) -> float:
    """Extract seconds from a CMTime 4-tuple."""
    if cm_time[1]:
        return cm_time[0] / cm_time[1]
    return 0.0


# ── main-queue dispatch helper ────────────────────────────────────────────────

# Qt apps register a hook here so AVPlayer transport commands reach the main
# thread via Qt's own queue (poll_queue, drained every 5 ms) rather than via
# NSRunLoop.performBlock_, which NSRunLoop.mainRunLoop() won't guarantee to
# fire while PySide6 owns the event loop.
#
# Call register_qt_dispatch(hook) once at app startup.  hook(fn) must be
# thread-safe and must schedule fn() to run on the Qt main thread shortly.
_qt_dispatch_hook: Optional[Callable] = None


def register_qt_dispatch(hook: Callable) -> None:
    """Register a Qt-safe main-thread dispatcher (call once from PhiMainWindow)."""
    global _qt_dispatch_hook
    _qt_dispatch_hook = hook


def _dispatch_main(fn) -> None:
    """Marshal *fn* to the main thread.

    Priority order:
      1. If a Qt dispatch hook is registered (PySide6 app), use it — the hook
         puts fn on the poll_queue which the Qt main thread drains every 5 ms.
      2. If already on the main thread (NSThread check), call fn() directly.
      3. Fall back to NSRunLoop.performBlock_ (Tkinter / bare Cocoa).
      4. Last resort: direct call from background thread (unsafe, logs warning).
    """
    if _qt_dispatch_hook is not None:
        _qt_dispatch_hook(fn)
        return
    try:
        from Foundation import NSThread, NSRunLoop
        if NSThread.isMainThread():
            fn()
        else:
            NSRunLoop.mainRunLoop().performBlock_(fn)
    except Exception:
        _log.warning("_dispatch_main: no Qt hook and NSRunLoop unavailable; "
                     "calling fn() directly from background thread (unsafe)")
        fn()


_log = logging.getLogger("phi.player")

# AVPlayerItem status codes (AVFoundation enum, stable across macOS versions)
_ITEM_UNKNOWN       = 0
_ITEM_READY         = 1   # AVPlayerItemStatusReadyToPlay
_ITEM_FAILED        = 2   # AVPlayerItemStatusFailed

# How long to wait for an item to become ready before giving up and playing anyway
_READY_TIMEOUT_SECS = 3.0
_READY_POLL_SECS    = 0.020  # 20 ms polling interval


# ── single AVPlayer channel ───────────────────────────────────────────────────

class _AVChannel:
    """Wraps a single AVPlayer + AVPlayerItem."""

    def __init__(self) -> None:
        _ensure_av()
        self._player = None
        self._item   = None
        self._duration_secs: float = 0.0
        self._eof_flag: bool = False    # sticky — set on first EOF, cleared on load/stop
        self._pending_play: bool = False  # play() called before item was readyToPlay
        self._lock = threading.Lock()

    def load(self, path: str, start: float = 0.0) -> None:
        from Foundation import NSURL
        url  = NSURL.fileURLWithPath_(path)
        item = AVPlayerItem.playerItemWithURL_(url)
        with self._lock:
            self._eof_flag     = False
            self._pending_play = False   # cancel any in-flight _play_when_ready thread
            self._item = item
            if self._player is None:
                self._player = AVPlayer.playerWithPlayerItem_(item)
                # Local files have no network latency — disable stall-buffering so
                # AVPlayer starts as soon as the decoder is initialised, not after
                # accumulating a larger playback buffer.
                try:
                    self._player.setAutomaticallyWaitsToMinimizeStalling_(False)
                except Exception:
                    pass
            else:
                self._player.replaceCurrentItemWithPlayerItem_(item)
            if start > 0.0:
                self._player.seekToTime_(_cm(start))
        self._duration_secs = 0.0

    def play(self) -> None:
        """Start playback, waiting for AVPlayerItem readiness if necessary.

        If the item is already readyToPlay the call is synchronous (< 1 µs).
        Otherwise a 20 ms polling thread fires player.play() the moment the
        item transitions to readyToPlay, eliminating the silent gap on startup.
        """
        with self._lock:
            item   = self._item
            player = self._player
        if item is None or player is None:
            return
        try:
            status = item.status()
        except Exception:
            status = _ITEM_UNKNOWN
        if status == _ITEM_READY:
            with self._lock:
                if self._player:
                    self._player.play()
        else:
            with self._lock:
                self._pending_play = True
            threading.Thread(
                target=self._play_when_ready,
                args=(item,),
                daemon=True,
                name="phi-play-ready",
            ).start()

    def _play_when_ready(self, expected_item) -> None:
        """Poll AVPlayerItem.status every 20 ms; call play() on readyToPlay."""
        import time
        deadline = time.monotonic() + _READY_TIMEOUT_SECS
        while time.monotonic() < deadline:
            with self._lock:
                still_pending = self._pending_play
                current_item  = self._item
                player        = self._player
            # Abort if the item was replaced (new track) or play was cancelled
            if not still_pending or current_item is not expected_item or player is None:
                return
            try:
                status = expected_item.status()
            except Exception:
                return
            if status == _ITEM_READY:
                # Grab the player reference and clear the flag *before* dispatching
                # so a concurrent load() can't race and see _pending_play still set.
                with self._lock:
                    if self._pending_play and self._item is expected_item and self._player:
                        _player_ref = self._player
                        self._pending_play = False
                    else:
                        return
                # Marshal player.play() to the main thread via NSRunLoop.performBlock_
                # so AVPlayer receives transport commands from the expected context.
                _dispatch_main(_player_ref.play)
                return
            if status == _ITEM_FAILED:
                with self._lock:
                    self._pending_play = False
                _log.warning("AVPlayerItem failed before becoming ready")
                return
            time.sleep(_READY_POLL_SECS)
        # Timeout — attempt play anyway so we never silently drop a track
        _log.warning("AVPlayerItem did not reach readyToPlay within %.1fs; playing anyway",
                     _READY_TIMEOUT_SECS)
        with self._lock:
            if self._pending_play and self._item is expected_item and self._player:
                _player_ref = self._player
                self._pending_play = False
            else:
                return
        _dispatch_main(_player_ref.play)

    def pause(self) -> None:
        with self._lock:
            self._pending_play = False   # cancel deferred play if user pauses first
            if self._player:
                self._player.pause()

    def stop(self) -> None:
        with self._lock:
            self._eof_flag     = False
            self._pending_play = False   # cancel deferred play
            if self._player:
                self._player.pause()
                self._player.replaceCurrentItemWithPlayerItem_(None)
                self._item = None

    def seek(self, seconds: float) -> None:
        with self._lock:
            if self._player:
                self._player.seekToTime_(_cm(max(0.0, seconds)))

    def set_volume(self, v_0_100: float) -> None:
        with self._lock:
            if self._player:
                self._player.setVolume_(max(0.0, min(100.0, v_0_100)) / 100.0)

    def position(self) -> float:
        with self._lock:
            if self._player is None:
                return 0.0
        try:
            t = self._player.currentTime()
            return _secs(t)
        except Exception:
            return 0.0

    def rate(self) -> float:
        try:
            with self._lock:
                if self._player:
                    return float(self._player.rate())
        except Exception:
            pass
        return 0.0

    def rate_and_position(self) -> tuple[float, float]:
        """Read rate and currentTime in a single lock acquisition.

        Used by PlayerEngine.tick_state() to replace two separate ObjC calls
        with one back-to-back read, cutting per-tick ObjC crossings in half.
        Returns (rate, position_secs).
        """
        with self._lock:
            if self._player is None:
                return 0.0, 0.0
            player = self._player
        try:
            r = float(player.rate())
            t = player.currentTime()
            return r, _secs(t)
        except Exception:
            return 0.0, 0.0

    def duration(self) -> float:
        try:
            with self._lock:
                item = self._item
            if item is None:
                return 0.0
            asset = item.asset()
            if asset is None:
                return 0.0
            d = asset.duration()
            return _secs(d)
        except Exception:
            return 0.0

    def eof_reached(self) -> bool:
        """True once playback has reached end-of-file.

        Sticky: once set, stays True until load() or stop() clears the flag.
        Detection: rate drops to 0 while position is > 0 (track was playing).
        """
        if self._eof_flag:
            return True
        try:
            r = self.rate()
            p = self.position()
            if r == 0.0 and p > 0.05:
                self._eof_flag = True
                return True
        except Exception:
            pass
        return False

    def has_item(self) -> bool:
        with self._lock:
            return self._item is not None

    def terminate(self) -> None:
        self.stop()


# ── public PlayerEngine ────────────────────────────────────────────────────────

class PlayerEngine:
    """Stateful audio engine backed by AVFoundation AVPlayer.

    Public API is a drop-in replacement for the former python-mpv/libmpv version.
    """

    def __init__(self) -> None:
        _ensure_av()
        self._ch          = _AVChannel()
        self._xfade_ch:   Optional[_AVChannel] = None
        self._xfading     = False
        self._xfade_elapsed = 0.0
        self._xfade_secs    = 0.0
        self._xfade_path:   Optional[str] = None
        self._xfade_start_vol = 1.0

        self._loaded_path:  Optional[str] = None
        self._paused        = False
        self._playing       = False
        self._eof           = False   # sticky EOF — raw_ms returns -1 until next play()
        self._play_offset   = 0.0
        self._queued_path:  Optional[str] = None
        self._current_volume = 1.0
        self._muted          = False
        # Gapless Phase 2: xfade channel pre-buffered at vol=0, not yet playing.
        # Distinct from _xfading (which means the volume ramp is active).
        self._gapless_preloaded: bool = False

    # ── loading ───────────────────────────────────────────────────────────────

    def load(self, path: str) -> None:
        # Discard a stale gapless preload when a different path is requested.
        if self._gapless_preloaded and self._xfade_path != path:
            self._clear_gapless_preload()
        self._loaded_path = path
        self._paused      = False
        self._play_offset = 0.0

    # ── transport ─────────────────────────────────────────────────────────────

    def play(self, start: float = 0.0) -> None:
        if not self._loaded_path:
            return
        # Gapless promotion: xfade channel already decoded + buffered for this
        # path.  Swap it to main and call play() — AVFoundation starts in <1 ms
        # because the item is already readyToPlay.  Only works at start=0 (a seek
        # into a gapless buffer would need a fresh load at the target offset).
        if (
            self._gapless_preloaded
            and self._xfade_path == self._loaded_path
            and start == 0.0
            and self._xfade_ch is not None
        ):
            old_ch = self._ch
            self._ch               = self._xfade_ch
            self._xfade_ch         = None
            self._xfade_path       = None
            self._gapless_preloaded = False
            self._playing          = True
            self._paused           = False
            self._eof              = False
            self._play_offset      = 0.0
            self._apply_volume()
            self._ch.play()
            old_ch.terminate()
            return
        # Normal cold-load path.
        self._play_offset = start
        self._paused  = False
        self._playing = True
        self._eof     = False
        self._ch.load(self._loaded_path, start)
        self._ch.play()

    def pause(self) -> None:
        self._ch.pause()
        self._paused = True

    def unpause(self) -> None:
        self._ch.play()
        self._paused = False

    def stop(self) -> None:
        self._playing = False
        self._eof     = False
        self._ch.stop()
        self._paused      = False
        self._play_offset = 0.0
        if self._gapless_preloaded:
            self._clear_gapless_preload()

    def seek(self, seconds: float, duration: float) -> None:
        seconds = max(0.0, min(float(seconds), max(0.0, float(duration) - 0.05)))
        self._play_offset = seconds
        self._ch.seek(seconds)

    # ── volume ────────────────────────────────────────────────────────────────

    def _apply_volume(self) -> None:
        if self._xfading:
            return
        eff = 0.0 if self._muted else self._current_volume
        self._ch.set_volume(eff * 100.0)

    def set_volume(self, v: float) -> None:
        self._current_volume = max(0.0, min(1.0, v))
        self._apply_volume()

    def set_muted(self, muted: bool) -> None:
        self._muted = bool(muted)
        self._apply_volume()

    @property
    def muted(self) -> bool:
        return self._muted

    # ── queries ───────────────────────────────────────────────────────────────

    def position(self) -> float:
        pos = self._ch.position()
        return float(pos) if pos else self._play_offset

    def raw_ms(self) -> int:
        # _eof stays True until the next play() call — always return -1 so the
        # poll engine's advance gate fires on every tick until _on_advance() runs.
        if self._eof:
            return -1
        if not self._playing:
            return 0
        if self._ch.eof_reached():
            self._eof     = True
            self._playing = False
            return -1
        pos = self._ch.position()
        return int(pos * 1000) if pos else 0

    def is_busy(self) -> bool:
        if self._eof:
            return False
        if not self._playing:
            return False
        if self._ch.eof_reached():
            self._eof     = True
            self._playing = False
            return False
        return True

    def tick_state(self) -> tuple[bool, int, float]:
        """Single-snapshot poll query: (busy, raw_ms, position_secs).

        Replaces the separate is_busy() / raw_ms() / position() calls that the
        poll loop previously made in sequence.  Each of those individually
        acquires the AVChannel lock and crosses the ObjC bridge; here we pay
        that cost exactly once (one lock, one rate() read, one currentTime()
        read) and derive all three values from the same snapshot.

        Returns:
            busy (bool)  — True while a track is playing and not at EOF.
            raw_ms (int) — millisecond position, or -1 at EOF / 0 when stopped.
            pos (float)  — position in seconds; falls back to _play_offset when 0.
        """
        if self._eof:
            return False, -1, self._play_offset
        if not self._playing:
            return False, 0, self._play_offset

        rate, pos_raw = self._ch.rate_and_position()

        # EOF detected: rate dropped to 0 while position is well past start
        if rate == 0.0 and pos_raw > 0.05:
            self._eof     = True
            self._playing = False
            return False, -1, pos_raw if pos_raw else self._play_offset

        pos = pos_raw if pos_raw else self._play_offset
        return True, int(pos_raw * 1000) if pos_raw else 0, pos

    # ── properties ────────────────────────────────────────────────────────────

    @property
    def paused(self) -> bool:
        return self._paused

    @property
    def loaded_path(self) -> Optional[str]:
        return self._loaded_path

    @property
    def xfade_channel_busy(self) -> bool:
        if self._xfade_ch is None:
            return False
        return self._xfade_ch.has_item() and self._xfade_ch.position() > 0.0

    # ── gapless pre-buffer (Phase 2) ─────────────────────────────────────────

    def queue_next(self, path: str) -> bool:
        """Pre-buffer *path* on the xfade channel at zero volume.

        Called ~5 s before EOF.  The next play() call for the same path
        promotes this channel instantly instead of doing a cold load+decode.
        Returns True when the preload was accepted (always True even when
        a crossfade or prior preload is already active — the caller just
        skips the optimisation gracefully).
        """
        self._queued_path = path
        if self._xfading or self._gapless_preloaded:
            return True   # already busy — gapless will fall back to cold load
        if not os.path.isfile(path):
            return False
        try:
            ch = _AVChannel()
            ch.set_volume(0.0)
            ch.load(path)
            # NOT calling ch.play() — AVFoundation buffers the item to
            # readyToPlay state so it can be promoted with near-zero latency.
            self._xfade_ch          = ch
            self._xfade_path        = path
            self._gapless_preloaded = True
            return True
        except Exception as exc:
            import logging
            logging.getLogger("phi.player").debug(
                "gapless preload failed for %s: %s", os.path.basename(path), exc
            )
            return False

    def _clear_gapless_preload(self) -> None:
        """Discard a pending gapless pre-buffer (channel not yet playing)."""
        if self._xfade_ch is not None and not self._xfading:
            self._xfade_ch.terminate()
            self._xfade_ch = None
        self._xfade_path        = None
        self._gapless_preloaded = False
        self._queued_path       = None

    # ── crossfade ─────────────────────────────────────────────────────────────

    def begin_crossfade(self, next_path: str, fade_secs: float) -> bool:
        if self._xfading:
            return False
        # Gapless preload is mutually exclusive with crossfade.  Discard the
        # pre-buffered channel so begin_crossfade creates a fresh one.
        if self._gapless_preloaded:
            self._clear_gapless_preload()
        if not os.path.isfile(next_path):
            return False
        try:
            ch = _AVChannel()
            ch.set_volume(0.0)
            ch.load(next_path)
            ch.play()
            self._xfade_ch       = ch
            self._xfade_path     = next_path
            self._xfade_elapsed  = 0.0
            self._xfade_secs     = max(fade_secs, 0.5)
            self._xfading        = True
            self._xfade_start_vol = self._current_volume
            return True
        except Exception as exc:
            _log.warning("begin_crossfade failed: %s", exc)
            return False

    def tick_crossfade(self, delta_secs: float) -> bool:
        if not self._xfading or self._xfade_ch is None:
            return False
        self._xfade_elapsed += delta_secs
        t = min(1.0, self._xfade_elapsed / self._xfade_secs)
        # Equal-power crossfade: sin²θ + cos²θ = 1 keeps perceived loudness
        # constant across the fade, eliminating the audible dip at t=0.5 that
        # a linear ramp produces (linear preserves amplitude sum, not power sum).
        theta = t * math.pi / 2.0
        gain_in  = math.sin(theta)
        gain_out = math.cos(theta)
        eff = 0.0 if self._muted else self._current_volume
        self._xfade_ch.set_volume(gain_in  * eff * 100.0)
        self._ch.set_volume(      gain_out * self._xfade_start_vol * 100.0)
        if t >= 1.0:
            self._xfading = False
            return False
        return True

    def finish_crossfade_promote(self) -> Optional[str]:
        if self._xfade_ch is None or not self._xfade_path:
            self._xfading = False
            return None
        path     = self._xfade_path
        old_ch   = self._ch
        self._ch          = self._xfade_ch
        self._loaded_path = path
        self._xfade_ch    = None
        self._xfade_path  = None
        self._xfading     = False
        self._playing     = True
        self._paused      = False
        self._play_offset = 0.0
        self._apply_volume()
        self._ch.play()
        old_ch.terminate()
        return path

    def finish_crossfade(self, next_path: str) -> None:
        self.abort_crossfade()
        self.load(next_path)
        self.play()

    def abort_crossfade(self) -> None:
        self._xfading           = False
        self._gapless_preloaded = False   # clear regardless — channel is being terminated
        if self._xfade_ch is not None:
            self._xfade_ch.terminate()
            self._xfade_ch = None
        self._xfade_path = None
        self._apply_volume()

    # ── teardown ─────────────────────────────────────────────────────────────

    def quit(self) -> None:
        if self._xfade_ch is not None:
            self._xfade_ch.terminate()
        self._ch.terminate()
