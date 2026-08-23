# -*- coding: utf-8 -*-
"""phi.engine.curve_daemon — CurveDaemon: single orchestrating object for
dragon-curve background ML additions.

Coordinates three background processes that run alongside phi's playback engine:

    A  FoldInjector   — wire track fold-bits into the shared harmonic index
                        so the CAIRRN ring reflects the curve geometry of
                        whatever is playing.

    B  ArcScorer      — maintain a rolling D4_A buffer to score candidate
                        tracks for smooth arc continuation.

    C  PlaybackLogger — write JSONL events (play / skip) that ZoneClusterer
                        (Phase 2) consumes to build the transition matrix.

Usage (in PhiMainWindow.__init__)::

    from phi.engine.curve_daemon import CurveDaemon
    self.curve_daemon = CurveDaemon(
        harmonic_index = self._cairrn_index,
        meta_cache     = self.meta_cache,
        library        = self.library,
    )

Event hooks::

    # on every new track (called from _TrackUIMixin._apply_track_to_ui):
    self.curve_daemon.on_track_change(path)

    # on skip (called from PlaybackController via on_skip callback):
    self.curve_daemon.on_skip(path, pos)

    # on library scan complete (stub — Phase 2 will trigger ZoneClusterer):
    self.curve_daemon.on_library_refresh()

    # on app close:
    self.curve_daemon.shutdown()
"""
from __future__ import annotations

import collections
import logging
from typing import TYPE_CHECKING, Any, Callable

import numpy as np

if TYPE_CHECKING:
    from sims.harmonic import HarmonicIndex
    from phi.meta.cache import MetaCache
    from phi.core.library import Library

from phi.engine.fold_injector   import FoldInjector
from phi.engine.arc_scorer      import ArcScorer
from phi.engine.arc_engine      import ArcEngine
from phi.engine.playback_logger import PlaybackLogger
from phi.engine.zone_clusterer  import ZoneClusterer
from phi.engine.curve_walker    import CurveWalker
from phi.meta.consensus         import build_consensus_track
from phi.ui.qt.rooms._dragon_coord import bpm_key_to_unit

log = logging.getLogger("phi.curve_daemon")


class CurveDaemon:
    """Single orchestrating object for dragon-curve background ML additions.

    All methods are designed to be called from the Qt main thread and return
    quickly — no blocking I/O on the hot path.

    Args:
        harmonic_index: Shared ``HarmonicIndex`` (``app._cairrn_index``).
        meta_cache:     App-wide ``MetaCache`` instance.
        library:        App-wide ``Library`` instance.
    """

    def __init__(
        self,
        harmonic_index: "HarmonicIndex",
        meta_cache:     "MetaCache",
        library:        "Library",
    ) -> None:
        self._meta_cache = meta_cache
        self._library    = library
        self._current_path: str = ""
        self._zone_map: dict[str, int] = {}

        # Walker — curve-position sort engine (shared with QueueEngine)
        self.walker = CurveWalker(depth=8)

        # A — fold-bit injector
        self.fold_injector = FoldInjector(harmonic_index, weight=0.4)

        # B — arc scorer (rolling buffer)
        self.arc_scorer = ArcScorer(capacity=16)

        # Arc engine — session arc planner (Option 1)
        self.arc_engine = ArcEngine(depth=8)

        # C — playback logger
        self._logger = PlaybackLogger()

        # D — zone clusterer (Phase 2)
        self._zone_clusterer = ZoneClusterer(
            meta_cache = meta_cache,
            library    = library,
        )
        self._zone_clusterer.clustered.connect(self._on_clustered)

        # 8×8 zone-to-zone transition matrix (filled once ZoneClusterer finishes)
        self._transition_matrix: np.ndarray = np.ones((8, 8), dtype=np.float64) / 8.0

        # Rolling window of recently-played paths — passed as `exclude` to
        # ArcEngine.pick_next so the same high-scoring track cannot be cycled
        # back immediately.  Size = pool * 2 gives enough breathing room.
        self._recent_paths: collections.deque[str] = collections.deque(maxlen=12)

        # Optional callback — set by app.py to pre-queue arc suggestions.
        # Signature: (path: str) -> None
        self._on_suggest_next: Callable[[str], None] | None = None

        log.debug("CurveDaemon ready")

    # ── Event hooks ───────────────────────────────────────────────────────────

    def on_track_change(self, path: str) -> None:
        """Call when a new track starts playing.

        Performs A (fold inject), B (arc push), and C (log play event).
        Non-blocking — all three operations complete in microseconds on the
        main thread.

        Args:
            path: File path of the newly loaded track.
        """
        # ML fields (fold_bits, d4_a) live in the annotations table, not tracks
        ann: dict[str, Any] = self._meta_cache.get_annotation(path) or {}

        # A: inject fold bits into the shared harmonic index.
        # Primary source: MetaClipper-computed fold_bits stored in annotations.
        # Fallback: derive from ConsensusTrack bpm + key via the dragon curve so
        # every track reaches the ring even before MetaClipper has run.
        fold_bits = ann.get("fold_bits")
        if not fold_bits:
            try:
                meta = self._meta_cache.get(path) or {}
                ct   = build_consensus_track(ann, meta)
                x_n, y_n = bpm_key_to_unit(ct.bpm or None, ct.key or None)
                dc   = self.walker._dc
                cx, cy   = dc.unit_to_curve(x_n, y_n)
                seg       = dc.nearest_segment(cx, cy)
                fold_bits = dc.fold_bits(seg).tolist()
            except Exception:
                log.debug("fold_bits fallback failed for %s", path, exc_info=True)
        if fold_bits:
            try:
                self.fold_injector.inject(fold_bits)
            except Exception:
                log.warning("FoldInjector.inject failed", exc_info=True)

        # B: push d4_a into the arc buffer
        self.arc_scorer.push(ann.get("d4_a"))

        # C: append a play event to today's JSONL log
        try:
            self._logger.record(path, ann)
        except Exception:
            log.warning("PlaybackLogger.record failed", exc_info=True)

        self._current_path = path

        # Track recency — add to buffer BEFORE pick_next so the current track
        # is also excluded (pick_next already excludes current_path, but the
        # buffer catches the N tracks before it too).
        self._recent_paths.append(path)

        # Arc engine — pre-queue the next track if arc mode is active
        self.arc_engine.on_track_played()
        if self.arc_engine.active and self._on_suggest_next is not None:
            try:
                # Pull live ring state for CAIRRN-informed blending
                ring_act = self.fold_injector._index.activation_vector()
                suggestion = self.arc_engine.pick_next(
                    path,
                    self._library,
                    self._meta_cache,
                    self.walker,
                    exclude            = set(self._recent_paths),
                    zone_map           = self._zone_map          or None,
                    transition_matrix  = self._transition_matrix,
                    ring_activations   = ring_act,
                )
                if suggestion:
                    self._on_suggest_next(suggestion)
            except Exception:
                log.warning("ArcEngine.pick_next failed", exc_info=True)

    def on_skip(self, path: str, pos: float) -> None:
        """Call when a track is abandoned before ~30 % completion.

        Args:
            path: Track path being abandoned.
            pos:  Playback position in seconds at the time of skip.
        """
        try:
            self._logger.record_skip(path, pos)
        except Exception:
            log.warning("PlaybackLogger.record_skip failed", exc_info=True)

    def on_library_refresh(self) -> None:
        """Call after a library scan completes.

        Launches ZoneClusterer if ≥ 10 anchored tracks are available and the
        thread is not already running.  Fast no-op if nothing to do.
        """
        self._zone_clusterer.start_if_ready()

    def suggest_next_for(self, current_path: str) -> bool:
        """Fire an arc suggestion for *current_path* without updating play state.

        Safe to call at any time (e.g. on mode toggle or manual skip) to ensure
        the pre-queue slot at pos+1 holds an arc-picked track before advance()
        is called.  Unlike on_track_change this does NOT increment the arc step
        counter, log a play event, or update the recency buffer.

        Returns True if a suggestion was successfully enqueued.
        """
        if not self.arc_engine.active or self._on_suggest_next is None:
            return False
        try:
            ring_act = self.fold_injector._index.activation_vector()
            suggestion = self.arc_engine.pick_next(
                current_path,
                self._library,
                self._meta_cache,
                self.walker,
                exclude           = set(self._recent_paths) | {current_path},
                zone_map          = self._zone_map          or None,
                transition_matrix = self._transition_matrix,
                ring_activations  = ring_act,
            )
            if suggestion:
                self._on_suggest_next(suggestion)
                log.debug("suggest_next_for: pre-queued %s", suggestion[-40:])
                return True
        except Exception:
            log.warning("suggest_next_for failed", exc_info=True)
        return False

    # ── Query interface ───────────────────────────────────────────────────────

    def score_candidate(self, path: str) -> float:
        """Score a candidate track for smooth arc continuation.

        Reads the track's ``d4_a`` from meta_cache and asks the ArcScorer
        how well it fits the recent D4_A arc.

        Returns:
            float in [0, 1] — 1.0 = perfect continuation.
        """
        ann: dict[str, Any] = self._meta_cache.get_annotation(path) or {}
        d4_a = float(ann.get("d4_a") or ArcScorer._D4A_NEUTRAL)
        return self.arc_scorer.score_candidate(d4_a)

    def zone_of(self, path: str) -> int:
        """Return the zone_id (0–7) for a path, or -1 if not yet clustered."""
        return self._zone_map.get(path, -1)

    # ── ZoneClusterer slot ────────────────────────────────────────────────────

    def _on_clustered(self, zone_map: dict, transition_matrix: object) -> None:
        """Receive clustering results from ZoneClusterer and cache in-memory.

        Called on the Qt main thread via the ``clustered`` signal.
        """
        self._zone_map = dict(zone_map)
        T = np.asarray(transition_matrix, dtype=np.float64)
        if T.shape == (8, 8):
            self._transition_matrix = T
        log.debug(
            "CurveDaemon: zone map updated — %d tracks, T shape %s",
            len(self._zone_map),
            getattr(transition_matrix, "shape", "?"),
        )

    def index_state(self) -> dict:
        """Serialisable snapshot of the current harmonic index (for dragon room)."""
        return self.fold_injector.state()

    def cairrn_state(self) -> dict:
        """Live CAIRRN blending state — useful for Inference room display.

        Returns:
            {
                "ring":       list[float] (8,) — current shard activations,
                "coherence":  float ∈ [0, 1]  — ring concentration,
                "alpha":      float ∈ [0, 1]  — current CAIRRN blend weight,
                "arc_target": float ∈ [0, 1]  — current arc target (normalised D4_A),
                "arc_step":   int,
                "arc_shape":  str,
                "arc_active": bool,
            }
        """
        ring = self.fold_injector._index.activation_vector()
        coherence = self.arc_engine._ring_coherence(ring)
        return {
            "ring":       ring.tolist(),
            "coherence":  round(coherence, 4),
            "alpha":      round(coherence, 4),   # alpha == coherence by design
            "arc_target": round(self.arc_engine.target(), 4),
            "arc_step":   self.arc_engine._step,
            "arc_shape":  self.arc_engine.shape.value,
            "arc_active": self.arc_engine.active,
        }

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def flush_logs(self) -> None:
        """Force-flush the playback logger (safe to call any time)."""
        self._logger.flush()

    def shutdown(self) -> None:
        """Graceful shutdown — flush logs and release file handles.

        Call from ``_on_close`` before the process exits.
        """
        try:
            self._logger.close()
        except Exception:
            log.warning("PlaybackLogger.close failed on shutdown", exc_info=True)
        log.debug("CurveDaemon shutdown complete")
