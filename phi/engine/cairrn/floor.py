# -*- coding: utf-8 -*-
"""phi.engine.cairrn.floor — the CAIRRN substrate as executable analogy.

THE ANALOGY, MADE LITERAL
──────────────────────────

    Pages  are trees.
    Songs  (and their nesting — track → album → genre → mood) are leaves.
    CAIRRN is the forest floor.

A leaf falls (a song plays or skips).
The floor absorbs it through its root network (CAIRRN hubs).
Nutrients propagate through the mycelium (harmonic ring diffusion).
Dormant roots in other trees stir (shard handlers wake).
The forest breathes — the ring waveform is its respiratory signal.

LEAF
────
A single track event.  A leaf carries identity (path), canopy position
(album, genre, mood — the nesting), and a signal from its tree
(completion_rate — did the wind carry it down gently, or tear it off?).

    leaf.completion_rate → 1.0   gentle landing  (track played to end)
    leaf.completion_rate → 0.0   torn off early  (track skipped)

TREE
────
A UI page — a standing tree whose roots reach into one CAIRRN hub.

    "playing"  → CODE      τ≈13.8  the listening-context tree
    "library"  → HOME      τ≈49.5  the catalogue tree, grows slowly
    "genre"    → MATH      τ≈19.5  the classification tree
    "playlist" → CODE      τ≈13.8  shares roots with playing
    "mixer"    → COMMANDS  τ≈9.5   the action tree, rapid response

RIDER
─────
The user's active intent, expressed through button presses and cursor position.

The Rider is not a separate component — it IS the user, present in the forest
via the UI.  Every direct interaction is a steering impulse:

    root_pulse(page_name)             cursor enters a tree — Rider moves location
    skip_event(path, skip_pressure)   loudest Rider signal — explicit direction change
    seek_kin(n_candidates)            Rider actively probing the soil for kin
    leaf_falls(completion_rate→0.0)   Rider tearing a leaf — forceful exit
    leaf_falls(completion_rate→1.0)   Rider at rest — ambient, trusting signal

In the River model (see keep/carrin-logic-cache-flow-as-a-living-river.md), the
Rider is a separate control node inside the recursive bubble that steers flow.
On the Forest Floor, the Rider needs no separate model — every API call that
originates from a direct UI interaction IS a Rider steering impulse, landing
immediately in the floor via root_pulse() or skip_event().  Background signals
(heartbeat, mycelial_surge, decompose) are the river flowing on its own;
Rider signals are when the user puts their hand in the current.

The current tree (set by root_pulse) is the Rider's location.
The skip pressure is the Rider's velocity.
The cursor is always present — it simply hasn't spoken yet.

FOREST FLOOR
────────────
The CAIRRN harmonic ring.  8 shards, each a region of the floor.

    shard 0  quiet  →  no ML writes in progress           (agent-context)
    shard 1  warm   →  active listening session            (CODE)
    shard 2  hot    →  user in library, topology shifting  (HOME)
    shard 3  warm   →  similarity search or CLAP active    (MATH)
    shards 4–6      →  propagation waveguide
    shard 7  hot    →  enrichment queue demanding action   (COMMANDS)

EXECUTABLE SUMMARY
───────────────────

    floor = ForestFloor()
    floor.load_state()                      # restore last session (no-op on first launch)
    floor.warm_from_history(library)        # replay recent listening history

    floor.leaf_falls("/music/song.mp3", completion_rate=0.88)
    # → CODE hub step  (leaf absorbed through listening-context roots)
    # → harmonic propagation (nutrients spread one step)
    # → shard-1 handlers called if floor shifts under CODE shard

    floor.root_pulse("genre")
    # → MATH hub step via page nav
    # → 2-step propagation (wider diffusion from navigation burst)

    floor.mycelial_surge(n_tracks=15)
    # → MATH hub step (CLAP batch = nutrient injection into embedding region)
    # → 3-step propagation (CLAP bursts spread wide)
    # → shard-3 handlers: similarity index marked stale

    floor.decompose(queue_len=25)
    # → COMMANDS hub step
    # → shard-7 handlers: enrichment dispatcher signalled

    floor.heartbeat(progress=0.42, energy=0.77)
    # → CODE hub step from poll tick (the forest's ~1.5 s respiratory pulse)

    print(floor.breathe())
    # → ASCII ring waveform showing activation across all 8 shards

IPC (optional)
──────────────
ForestFloor can optionally write live hub state to a local JSON file on
every heartbeat so the phi MCP server can observe the live substrate:

    floor = ForestFloor(ipc_enabled=True)   # default: False

When ipc_enabled=True, each heartbeat writes /tmp/phi_cairrn_state.json
atomically.  The MCP cairrn_inject() tool writes commands to
/tmp/phi_cairrn_cmds.json; the floor drains them on the next heartbeat.
"""
from __future__ import annotations

import json
import logging
import math
import os
import pathlib
import time
from datetime import datetime as _dt
from typing import Callable, Dict, List, Optional, TYPE_CHECKING

from phi.engine.cairrn._constants import PAGE_HUB
from phi.engine.cairrn.bridge      import CairnBridge
from phi.engine.cairrn.router      import PhiCairrnRouter, RequestKind, DispatchResult, RIDER_KINDS
from phi.engine.cairrn.watchdog    import CairrnWorkerWatchdog
from phi.engine.cairrn.types       import Leaf, Tree, RiderState

if TYPE_CHECKING:
    pass    # library type avoided to prevent circular import

# ── IPC paths (only used when ipc_enabled=True) ───────────────────────────────
_IPC_STATE_FILE: str = "/tmp/phi_cairrn_state.json"
_IPC_CMD_FILE:   str = "/tmp/phi_cairrn_cmds.json"

# Persistent state path — survives restarts, used for cold-start hot-load
_PERSISTENT_STATE: pathlib.Path = pathlib.Path.home() / ".phi" / "cairrn_state.json"

_log = logging.getLogger("phi.cairrn.floor")


# ── ForestFloor ───────────────────────────────────────────────────────────────

class ForestFloor:
    """
    The phi CAIRRN substrate expressed as a living forest floor.

    Owns a PhiCairrnRouter (and therefore a CairnBridge + WatchdogWorker).
    Every phi operation enters through one of this class's named methods.

    Public API
    ──────────
    Leaf events (track plays / skips):
        leaf_falls(path, completion_rate, ...)
        skip_event(path, skip_pressure)

    Root pulses (page navigation):
        root_pulse(page_name)

    Background ML signals:
        mycelial_surge(n_tracks)     — CLAP batch complete
        decompose(queue_len, total)  — enrichment pressure
        seek_kin(n_candidates)       — similarity search

    Respiratory pulse (poll loop):
        heartbeat(progress, energy)

    Library changes:
        library_changed(n_added, n_removed, total)

    Playback history:
        track_history_feed(depth_back, depth_forward, recent_paths)

    Persistence (cold-start warm-up):
        save_state(path?)            — write to ~/.phi/cairrn_state.json
        load_state(path?, max_age?)  — restore if fresh (no-op otherwise)
        warm_from_history(library)   — replay last n plays with age-decay

    Subscriber registration:
        when_floor_shifts(shard, handler)

    Inspection:
        breathe()     — ASCII ring waveform
        soil_report() — per-hub coherence table
    """

    def __init__(
        self,
        coherence_floor: float = 0.50,
        z_threshold:     float = 2.5,
        ipc_enabled:     bool  = False,
        verbose:         bool  = False,
    ) -> None:
        self._bridge   = CairnBridge(
            coherence_floor=coherence_floor,
            z_spawn_threshold=z_threshold,
        )
        self._watchdog = CairrnWorkerWatchdog(bridge=self._bridge)
        self.router    = PhiCairrnRouter(self._bridge, watchdog=self._watchdog)

        self.fallen_leaves: List[Leaf]       = []
        self.active_trees:  Dict[str, Tree]  = {}
        self._current_tree: Optional[Tree]   = None
        self._rider:        RiderState       = RiderState()
        self._ipc_enabled = ipc_enabled
        self._verbose     = verbose

        # Playback history context (populated by track_history_feed)
        self._history_depth_back:    int       = 0
        self._history_depth_forward: int       = 0
        self._history_recent:        list[str] = []

        for page_name in PAGE_HUB:
            self.active_trees[page_name] = Tree.from_page(page_name)

    # ── Safe routing helpers ──────────────────────────────────────────────────
    # Every public floor method that calls router.route() or route_page_nav()
    # goes through one of these two helpers.  A bridge OverflowError (from a
    # runaway GNN metric), a NaN in the ring, or any other routing exception is
    # caught here and logged — returning a coherent fallback DispatchResult so
    # the caller (UI main thread, poll loop, or playback controller) never sees
    # an unhandled exception from CAIRRN signal processing.

    def _safe_route(
        self,
        kind:    RequestKind,
        metric:  float,
        payload: dict | None = None,
    ) -> DispatchResult:
        """router.route() with overflow/exception guard.

        Returns a coherent fallback DispatchResult on any bridge exception so
        the caller (UI main thread, poll loop, playback controller) never sees
        an unhandled exception from CAIRRN signal processing.
        """
        try:
            return self.router.route(kind, metric, payload or {})
        except Exception:
            import traceback as _tb
            _log.warning(
                "floor._safe_route %s metric=%.4f — bridge exception (non-fatal): %s",
                kind.value, metric, _tb.format_exc().splitlines()[-1],
            )
            return self._fallback_result(kind, float(metric), payload or {})

    def _safe_route_page_nav(self, page_name: str) -> DispatchResult:
        """router.route_page_nav() with overflow/exception guard."""
        try:
            return self.router.route_page_nav(page_name)
        except Exception:
            import traceback as _tb
            _log.warning(
                "floor._safe_route_page_nav page='%s' — bridge exception (non-fatal): %s",
                page_name, _tb.format_exc().splitlines()[-1],
            )
            hub_name = PAGE_HUB.get(page_name, "HOME")
            return DispatchResult(
                kind=RequestKind.PAGE_NAV, hub=hub_name, shard=0,
                modulated=0.0, coherent=True, coherence=1.0,
                rerouted=False, priority=1, z_awareness=0.0,
                metric=1.0, is_rider=True,
                payload={"page": page_name, "hub": hub_name},
            )

    def _fallback_result(
        self, kind: RequestKind, metric: float, payload: dict,
    ) -> DispatchResult:
        """Coherent no-op DispatchResult used when routing raises."""
        return DispatchResult(
            kind=kind, hub="HOME", shard=0,
            modulated=0.0, coherent=True, coherence=1.0,
            rerouted=False, priority=1, z_awareness=0.0,
            metric=metric, is_rider=(kind in RIDER_KINDS),
            payload=payload,
        )

    # ── Leaf events (track plays) ─────────────────────────────────────────────

    def leaf_falls(
        self,
        path:            str,
        completion_rate: float,
        album:           str = "",
        genre:           str = "",
        mood:            str = "",
        no_annotations:  bool = False,
    ) -> DispatchResult:
        """
        A leaf falls from the canopy onto the forest floor.

        Records the departure leaf and routes skip pressure into the ML
        annotation domain.  Does NOT route TRACK_TRANSITION — that is owned
        exclusively by the arrival path (_apply_track_to_ui) so a single
        track change cannot DOUBLE_ROUTE CODE within the watchdog window.

        Args
        ----
        path            : absolute path of the track
        completion_rate : [0, 1] — 1.0 = listened to end, 0.0 = immediate skip
        album / genre / mood : canopy nesting metadata
        no_annotations  : True when the track has no CLAP/mood annotation yet.
                          Escalates the ML_INFERENCE priority from DEFER to NORMAL
                          for this single dispatch so the annotation worker fires
                          ahead of other DEFER-priority background tasks.
        """
        leaf = Leaf(
            path=path, completion_rate=completion_rate,
            album=album, genre=genre, mood=mood,
        )
        self.fallen_leaves.append(leaf)
        if self._current_tree:
            self._current_tree.catch(leaf)

        # Skip pressure → ML annotation domain (departure signal only).
        # TRACK_TRANSITION lives on arrival — see _apply_track_to_ui.
        result = self._safe_route(
            RequestKind.ML_INFERENCE,
            metric=leaf.skip_pressure,
            payload={
                "path": path,
                "reason": "skip_pressure",
                "no_annotations": no_annotations,
            },
        )

        if self._verbose:
            print(f"LEAF  {result}")
        return result

    def skip_event(self, path: str, skip_pressure: float) -> DispatchResult:
        """
        Explicit hard skip — the user tore the leaf off early.

        Routes a SKIP_EVENT through CODE with *skip_pressure* as the metric.
        A burst of skips drives CODE's z-awareness above 2.5, signalling the
        ranker to recompute before the user hears a bad next-track.

        This is distinct from the skip signal in leaf_falls() — that one is
        quiet (completion_rate ≈ 0.0 → ML_INFERENCE); this one is explicit
        and loud, designed to catch context shifts proactively.

        Args
        ----
        path          : absolute path of the skipped track
        skip_pressure : [0, 1] — 1.0 = immediate skip, 0.5 = abandoned midway
        """
        self._update_rider(
            location=self._current_tree.name if self._current_tree else self._rider.location,
            pressure=float(skip_pressure),   # skip pressure IS the Rider velocity delta
            action="skip",
        )
        result = self._safe_route(
            RequestKind.SKIP_EVENT,
            metric=float(skip_pressure),
            payload={"path": path, "skip_pressure": skip_pressure},
        )
        if self._verbose:
            print(f"SKIP  path={path[-40:]}  pressure={skip_pressure:.2f}  {result}")
        return result

    # ── Root pulses (page navigation) ────────────────────────────────────────

    def root_pulse(self, page_name: str) -> DispatchResult:
        """
        The user moves to a tree — its root fires a pulse into the floor.

        Navigation burst metric = 1.0 (full-strength signal).  The floor
        propagates 2 steps so adjacent trees feel the stir.

        Args
        ----
        page_name : one of "playing", "library", "genre", "playlist", "mixer"
        """
        self._current_tree = self.active_trees.get(page_name)
        self._update_rider(
            location=page_name,
            pressure=0.1,   # cursor movement is a gentle Rider signal
            action=f"root_pulse:{page_name}",
        )
        result = self._safe_route_page_nav(page_name)
        if self._verbose:
            hub = PAGE_HUB.get(page_name, "HOME")
            print(f"ROOT  page='{page_name}'  hub={hub}  {result}")
        return result

    # ── Background ML signals ─────────────────────────────────────────────────

    def mycelial_surge(self, n_tracks: int) -> DispatchResult:
        """
        A CLAP batch completes — nutrients injected into the embedding region.

        Metric = min(1.0, n_tracks / 20).  Routes through MATH hub (shard 3).
        3-step propagation carries the surge into HOME and COMMANDS via wrap.

        Args
        ----
        n_tracks : number of tracks annotated in this batch
        """
        metric = min(1.0, n_tracks / 20.0)
        result = self._safe_route(
            RequestKind.CLAP_INFERENCE,
            metric=metric,
            payload={"n_tracks": n_tracks},
        )
        # Secondary: update ML annotation domain
        self._safe_route(
            RequestKind.ML_INFERENCE,
            metric=metric,
            payload={"n_tracks": n_tracks, "reason": "clap_batch"},
        )
        if self._verbose:
            print(f"MYCELIUM  n_tracks={n_tracks}  {result}")
        return result

    def decompose(self, queue_len: int, total: int = 1) -> DispatchResult:
        """
        Enrichment queue pressure — decomposition returning nutrients.

        Leaves decompose (AcoustID + MusicBrainz enrichment).  The COMMANDS
        hub (τ≈9.5, fastest-decaying) absorbs the signal.  High queue_len
        → high pressure → COMMANDS goes incoherent quickly → dispatcher woken.

        Args
        ----
        queue_len : pending enrichment tasks
        total     : total library size (for normalisation, optional)
        """
        metric = min(1.0, queue_len / 50.0)
        result = self._safe_route(
            RequestKind.ENRICH_DISPATCH,
            metric=metric,
            payload={"queue_len": queue_len, "total": total},
        )
        if self._verbose:
            print(f"DECOMPOSE  queue_len={queue_len}  {result}")
        return result

    def seek_kin(self, n_candidates: int = 10) -> DispatchResult:
        """
        Similarity search — roots seeking kin through the embedding soil.

        Routes through MATH (shard 3).  If MATH signals incoherence, the
        caller should rebuild the similarity index before using it.

        Args
        ----
        n_candidates : number of similar tracks being sought
        """
        metric = min(1.0, n_candidates / 50.0)
        result = self._safe_route(
            RequestKind.SIMILARITY_SEARCH,
            metric=metric,
            payload={"n_candidates": n_candidates},
        )
        if self._verbose:
            print(f"KIN_SEARCH  n={n_candidates}  {result}")
        return result

    def studio_build(self, n_tracks: int = 20) -> DispatchResult:
        """
        ML playlist-studio batch build — signal before PlaylistStudio.build().

        Routes through MATH (shard 3) with wide propagation (3 steps) so the
        CLAP similarity index is warm and hub coherence reflects the upcoming
        batch embedding scan.

        Args
        ----
        n_tracks : target playlist length (normalises the metric)
        """
        metric = min(1.0, n_tracks / 40.0)
        result = self._safe_route(
            RequestKind.PLAYLIST_BUILD,
            metric=metric,
            payload={"n_tracks": n_tracks},
        )
        if self._verbose:
            print(f"STUDIO_BUILD  n={n_tracks}  {result}")
        return result

    # ── Respiratory pulse (poll loop) ─────────────────────────────────────────

    def heartbeat(self, progress: float, energy: float) -> DispatchResult:
        """
        The forest's respiratory pulse — fired every ~1.5 s from the poll loop.

        Blends playback position (progress) and beat energy into a composite
        metric that keeps the CODE hub alive and its coherence decaying
        naturally over the session.

        When ipc_enabled=True, also drains pending MCP commands and writes
        updated hub state to the IPC state file.

        Args
        ----
        progress : [0, 1]  position in current track
        energy   : [0, 1]  beat / energy level from BeatSimulator
        """
        if self._ipc_enabled:
            self.drain_ipc_commands()

        metric = 0.5 * max(0.0, min(1.0, progress)) + 0.5 * max(0.0, min(1.0, energy))
        result = self._safe_route(
            RequestKind.POLL_TICK,
            metric=metric,
            payload={"progress": progress, "energy": energy},
        )
        self._rider.decay()   # velocity drifts back toward rest between active impulses
        self._watchdog.poll_tick(self._bridge)

        if self._ipc_enabled:
            self._write_ipc_state()

        # Always flush to persistent path (used by load_state on next cold start)
        self._flush_persistent_state()

        if self._verbose:
            print(f"HEARTBEAT  prog={progress:.2f}  energy={energy:.2f}  {result}")
        return result

    # ── Library topology change ───────────────────────────────────────────────

    def library_changed(
        self,
        n_added:   int,
        n_removed: int,
        total:     int = 0,
    ) -> DispatchResult:
        """
        Tracks were added or removed — the catalogue tree has grown or shed.

        Routes through HOME hub.  Metric is proportional to change magnitude.
        Caps at 1.0 for n_added + n_removed ≥ 100.

        Args
        ----
        n_added   : tracks added in this event
        n_removed : tracks removed
        total     : current library size (optional)
        """
        change = n_added + n_removed
        metric = min(1.0, change / 100.0)
        result = self._safe_route(
            RequestKind.PAGE_NAV,
            metric=metric,
            payload={"n_added": n_added, "n_removed": n_removed, "total": total},
        )
        if self._verbose:
            print(f"LIBRARY  +{n_added} -{n_removed}  total={total}  {result}")
        return result

    # ── History context feed ──────────────────────────────────────────────────

    def track_history_feed(
        self,
        depth_back:    int,
        depth_forward: int,
        recent_paths:  list[str],
    ) -> None:
        """
        Feed playback history chain depth into the CAIRRN substrate.

        Called once per track load by PlaybackController after pushing to
        history.  Annotates IPC state so external agents see the actual
        listening chain (not just what the queue index suggests).

        Does NOT route through the pipeline — read-only annotation.

        Args
        ----
        depth_back    : depth of the back-history stack (long session → HOME warmer)
        depth_forward : non-zero means user re-listened (boosts CODE coherence)
        recent_paths  : last ≤5 played track paths
        """
        self._history_depth_back    = depth_back
        self._history_depth_forward = depth_forward
        self._history_recent        = recent_paths[:5]

    # ── Cold-start persistence ────────────────────────────────────────────────

    def save_state(self, path: Optional[pathlib.Path] = None) -> bool:
        """
        Persist current hub activations and harmonic index to disk.

        Written atomically (temp-file rename).  Also called automatically on
        every heartbeat tick via _flush_persistent_state().

        Args
        ----
        path : target file; defaults to ``~/.phi/cairrn_state.json``

        Returns
        -------
        bool
            True on success, False on any I/O error.
        """
        target = path or _PERSISTENT_STATE
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "version": 1,
                "ts":      time.time(),
                "hubs":    self._bridge.hub_state(),
                "index":   self._bridge.index_state(),
            }
            tmp = str(target) + ".tmp"
            with open(tmp, "w") as fh:
                json.dump(payload, fh)
            os.replace(tmp, str(target))
            _log.debug("save_state: wrote %s", target)
            return True
        except Exception as exc:
            _log.warning("save_state: failed — %s", exc)
            return False

    def load_state(
        self,
        path:          Optional[pathlib.Path] = None,
        max_age_hours: float = 24.0,
    ) -> bool:
        """
        Restore persisted hub activations from the previous session.

        Reads ``~/.phi/cairrn_state.json``, validates that the snapshot is
        not older than *max_age_hours*, then seeds the live bridge.

        No-op if:
          - the file does not exist (first launch or rotated)
          - the snapshot is stale
          - the file is malformed

        In all failure cases the floor starts cold — identical to previous
        behaviour, so this call is unconditionally safe to add to init.

        Args
        ----
        path          : path to read; defaults to ``~/.phi/cairrn_state.json``
        max_age_hours : snapshots older than this are discarded (default 24 h)

        Returns
        -------
        bool
            True if state was restored, False otherwise.
        """
        target = path or _PERSISTENT_STATE
        if not target.exists():
            _log.debug("load_state: no persisted state at %s", target)
            return False
        try:
            with open(target) as fh:
                data = json.load(fh)
            age_hours = (time.time() - float(data.get("ts", 0))) / 3600.0
            if age_hours > max_age_hours:
                _log.info(
                    "load_state: snapshot is %.1fh old (limit=%.0fh) — discarding",
                    age_hours, max_age_hours,
                )
                return False
            self._bridge.load_hub_state(data["hubs"], data.get("index"))
            _log.info("load_state: restored from %s (age=%.1fh)", target, age_hours)
            return True
        except Exception as exc:
            _log.warning("load_state: failed — %s", exc)
            return False

    def warm_from_history(
        self,
        library,            # phi.core.library.Library — no circular import
        n:            int   = 20,
        decay_hours:  float = 48.0,
    ) -> int:
        """
        Replay the last *n* played tracks through the floor with age-decay.

        Pre-warms the CAIRRN floor at launch so the CODE hub is already
        seeded with listening context before the Rider selects the first track.
        Without this the floor starts completely cold and the first few
        song-selection decisions come from a flat activation map.

        Algorithm
        ---------
        1. Collect all paths in library.play_stats that have a last_played
           timestamp and a completion_rate.
        2. Sort by recency, take the most recent *n*.
        3. Replay oldest-first (so recency stacks correctly):
               decay  = exp(−age_hours / decay_hours)
               rate   = completion_rate × decay
               floor.leaf_falls(path, rate, ...)
        4. Return the number of leaves successfully replayed.

        Annotations (genre, mood) are read from library.annotations when
        present; album from play_stats if populated, else empty string.

        Args
        ----
        library     : the live Library instance (post-session restore, so
                      play_stats is populated)
        n           : most-recent tracks to replay (default 20)
        decay_hours : half-life in hours — 48h ago play has e^-1 ≈ 37% weight

        Returns
        -------
        int
            Number of leaves actually replayed.
        """
        if not hasattr(library, "play_stats") or not library.play_stats:
            _log.debug("warm_from_history: play_stats empty — skipping")
            return 0

        played = [
            (path, stats)
            for path, stats in library.play_stats.items()
            if stats.get("last_played") and stats.get("completion_rate") is not None
        ]
        if not played:
            _log.debug("warm_from_history: no timestamped plays — skipping")
            return 0

        played.sort(key=lambda t: t[1].get("last_played", ""), reverse=True)
        played = played[:n]
        played.reverse()    # oldest first — recency stacks correctly in bridge

        now        = time.time()
        n_injected = 0
        # Suspend DOUBLE_ROUTE detection: rapid replay of 20 leaves back-to-back
        # fires the 450ms watchdog window on every route() call — this is expected
        # noise, not a real race condition.  Timestamps are cleared on entry and
        # exit so the first live-playback event after warmup gets a clean slate.
        self._watchdog.begin_batch_warmup()
        try:
            for path, stats in played:
                try:
                    last_played = stats["last_played"]
                    if isinstance(last_played, (int, float)):
                        age_h = (now - float(last_played)) / 3600.0
                    else:
                        age_h = (now - _dt.fromisoformat(str(last_played)).timestamp()) / 3600.0

                    decay = math.exp(-age_h / decay_hours)
                    rate  = float(stats.get("completion_rate", 0.5)) * decay

                    ann   = library.annotations.get(path, {}) if hasattr(library, "annotations") else {}
                    genre = ann.get("genre", "")
                    mood  = ann.get("mood",  "")
                    album = stats.get("album", "")

                    # Arrival-side signal for cold-start — leaf_falls no longer
                    # routes TRACK_TRANSITION (owned by _apply_track_to_ui at runtime).
                    self.router.route(
                        RequestKind.TRACK_TRANSITION,
                        metric=rate,
                        payload={
                            "path": path, "album": album,
                            "genre": genre, "mood": mood,
                            "reason": "warm_from_history",
                        },
                    )
                    self.leaf_falls(path=path, completion_rate=rate,
                                    album=album, genre=genre, mood=mood)
                    n_injected += 1
                except Exception:
                    pass
        finally:
            self._watchdog.end_batch_warmup()

        _log.info(
            "warm_from_history: replayed %d/%d leaves (decay_hours=%g)",
            n_injected, len(played), decay_hours,
        )
        return n_injected

    # ── Subscriber registration ───────────────────────────────────────────────

    def when_floor_shifts(
        self,
        shard:   int,
        handler: Callable[[DispatchResult, Dict], None],
    ) -> None:
        """
        Register a handler that fires when a floor region becomes active.

        This is how dormant roots wake: the floor shifts beneath them.
        Future ML models call this once at startup without touching app.py.

        Example::

            def _on_embedding_shift(result, payload):
                if result.should_act:
                    self._rebuild_genre_index()

            floor.when_floor_shifts(shard=3, handler=_on_embedding_shift)

        Args
        ----
        shard   : ring shard [0–7] to watch
        handler : callable with signature (result, payload) → None
        """
        self.router.subscribe(shard=shard, handler=handler)

    def unwatch(self, shard: int, handler: Callable) -> None:
        """Remove a previously registered floor handler."""
        self.router.unsubscribe(shard=shard, handler=handler)

    # ── Rider (user active intent) ────────────────────────────────────────────

    def rider_impulse(self, action: str, metric: float = 0.5) -> DispatchResult:
        """
        A direct button press — the Rider's hand on the controls.

        Routes through CODE hub (shard 1, the active listening context).
        Use for UI actions not covered by skip_event() or root_pulse():
        play/pause, seek, queue add/remove, like/unlike.

        Args
        ----
        action : short label ("play", "pause", "seek", "queue_add", "like", …)
        metric : action intensity [0, 1] — 0 = gentle, 1 = decisive (default 0.5)

        Returns
        -------
        DispatchResult tagged is_rider=True
        """
        self._update_rider(
            location=self._current_tree.name if self._current_tree else self._rider.location,
            pressure=metric * 0.4,   # button presses are moderate steering
            action=f"rider:{action}",
        )
        result = self._safe_route(
            RequestKind.RIDER_ACTION,
            metric=float(metric),
            payload={"action": action},
        )
        if self._verbose:
            print(f"RIDER  action='{action}'  metric={metric:.2f}  {result}")
        return result

    @property
    def rider(self) -> RiderState:
        """Current Rider state — location, velocity, impulse count."""
        return self._rider

    def rider_state(self) -> dict:
        """Serialisable Rider state dict for IPC / MCP reporting."""
        return {
            "location":        self._rider.location,
            "velocity":        round(self._rider.velocity, 4),
            "impulse_count":   self._rider.impulse_count,
            "last_action":     self._rider.last_action,
            "is_active":       self._rider.is_active,
            "restless":        self._rider.restless,
        }

    def _update_rider(self, location: str, pressure: float, action: str) -> None:
        """Record a Rider impulse into _rider state."""
        self._rider.record(location=location, pressure=pressure, action=action)

    # ── IPC (optional — only active when ipc_enabled=True) ───────────────────

    def drain_ipc_commands(self) -> int:
        """
        Drain and apply pending commands from /tmp/phi_cairrn_cmds.json.

        Written by the phi MCP cairrn_inject() tool.  Each command is a
        JSON object {"hub": str, "value": float}.  Commands are consumed
        exactly once (file removed after reading).

        Returns
        -------
        int
            Number of commands successfully applied.
        """
        if not os.path.exists(_IPC_CMD_FILE):
            return 0
        try:
            with open(_IPC_CMD_FILE) as fh:
                cmds = json.load(fh)
            if not isinstance(cmds, list):
                cmds = [cmds]
            os.remove(_IPC_CMD_FILE)
        except Exception as exc:
            _log.warning("drain_ipc_commands: read/remove failed — %s", exc)
            return 0

        applied = 0
        for cmd in cmds:
            try:
                self._bridge.step(str(cmd["hub"]).strip(), float(cmd["value"]))
                applied += 1
            except Exception as exc:
                _log.warning("drain_ipc_commands: bad command %r — %s", cmd, exc)

        if applied:
            _log.debug("drain_ipc_commands: applied %d command(s)", applied)
        return applied

    # ── Inspection ────────────────────────────────────────────────────────────

    def breathe(self) -> str:
        """
        Return the forest's current respiratory signal — the 8-shard ring.

        Each shard is a region of the floor.  Positive activation means
        that region is recently energised; negative means it has been drawn
        on by the double-well attractor.  The pattern shifts with every leaf
        fall, root pulse, and mycelial surge.
        """
        index  = self._bridge.index_state()
        step   = self._bridge._global_step
        g_coh  = self._bridge.global_coherence()
        g_z    = self._bridge.global_z_awareness()

        COLS   = 24
        MID    = COLS // 2
        max_ab = max(abs(v) for v in index) or 1.0

        lines = [
            f"\nFOREST FLOOR  step={step}  coh={g_coh:.3f}  z={g_z:.3f}",
            "─" * 60,
        ]
        for shard, val in enumerate(index):
            norm     = val / max_ab
            width    = int(abs(norm) * MID)
            bar      = (" " * MID + "█" * width) if norm >= 0 else (" " * (MID - width) + "█" * width + " " * MID)
            hub_name = self._shard_hub(shard)
            coh      = self._bridge._hubs[hub_name].coherence if hub_name in self._bridge._hubs else 1.0
            lines.append(f"  [{shard}] {bar}  {val:+.3f}  {hub_name or '':>13}  coh={coh:.2f}")

        lines.append("─" * 60)
        lines.append("trees:")
        for name, tree in self.active_trees.items():
            marker = "◀" if tree is self._current_tree else " "
            lines.append(
                f"  {marker} {name:<10}  hub={tree.hub:<13}"
                f"  leaves={tree.leaf_count}  mean_completion={tree.mean_completion:.2f}"
            )
        lines.append(f"total leaves fallen: {len(self.fallen_leaves)}")
        lines.append("─" * 60)
        r = self._rider
        vel_bar  = "█" * int(r.velocity * 20)
        r_status = "restless" if r.restless else ("active" if r.is_active else "idle")
        lines.append(
            f"rider  loc='{r.location}'  vel=[{vel_bar:<20}] {r.velocity:.3f}"
            f"  [{r_status}]  impulses={r.impulse_count}  last='{r.last_action}'"
        )
        return "\n".join(lines)

    def soil_report(self) -> str:
        """
        Detailed per-hub coherence and z-awareness report.
        Appends the watchdog health line.
        """
        return self.router.report() + "\n" + self._watchdog.status_line()

    def shutdown(self, wait: bool = True) -> None:
        """Shut down the shard handler executor.  Call on application exit."""
        self.router.shutdown(wait=wait)

    # ── Internal ──────────────────────────────────────────────────────────────

    @staticmethod
    def _shard_hub(shard: int) -> str:
        """Map shard index back to the phi hub that naturally owns it."""
        _MAP = {0: "agent-context", 1: "CODE", 2: "HOME", 3: "MATH", 7: "COMMANDS"}
        return _MAP.get(shard, "")

    def _flush_persistent_state(self) -> None:
        """
        Write hub state + index to the persistent path on every heartbeat.

        Silent on failure — a missed flush is non-fatal.  The next heartbeat
        will try again.  Uses the same atomic temp-file rename as save_state().
        """
        try:
            _PERSISTENT_STATE.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "version": 1,
                "ts":      time.time(),
                "hubs":    self._bridge.hub_state(),
                "index":   self._bridge.index_state(),
            }
            tmp = str(_PERSISTENT_STATE) + ".tmp"
            with open(tmp, "w") as fh:
                json.dump(payload, fh)
            os.replace(tmp, str(_PERSISTENT_STATE))
        except Exception:
            pass    # non-fatal — cold start will just start fresh

    def _write_ipc_state(self) -> None:
        """
        Write live hub state to /tmp/phi_cairrn_state.json for MCP observation.

        Only called when ipc_enabled=True.  Atomic write via temp-file rename.
        """
        try:
            payload = {
                "source":           "phi",
                "hubs":             self._bridge.hub_state(),
                "index":            self._bridge.index_state(),
                "global_coherence": round(self._bridge.global_coherence(), 4),
                "global_z":         round(self._bridge.global_z_awareness(), 4),
                "spawn_signals":    {
                    k: round(v, 4)
                    for k, v in self._bridge.spawn_signals(include_z=True).items()
                },
                "z_signals": {
                    k: round(v, 4)
                    for k, v in self._bridge.z_awareness_signals().items()
                },
                "rider": self.rider_state(),
                "history": {
                    "depth_back":    self._history_depth_back,
                    "depth_forward": self._history_depth_forward,
                    "recent":        [os.path.basename(p) for p in self._history_recent],
                },
                "ts": time.time(),
            }
            tmp = _IPC_STATE_FILE + ".tmp"
            with open(tmp, "w") as fh:
                json.dump(payload, fh)
            os.replace(tmp, _IPC_STATE_FILE)
        except Exception as exc:
            _log.warning("_write_ipc_state: failed — %s: %s", type(exc).__name__, exc)


# ── Standalone demo ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import math as _math

    print("=" * 62)
    print("  PHI FOREST FLOOR — standalone CAIRRN demo")
    print("=" * 62)

    floor = ForestFloor(verbose=True)

    print("\n── Leaves falling ──")
    floor.leaf_falls("/music/01-ambient-dusk.flac",     completion_rate=0.95, genre="ambient", mood="calm")
    floor.leaf_falls("/music/02-focused-drive.mp3",     completion_rate=0.82, genre="electronic", mood="focused")
    floor.leaf_falls("/music/03-high-energy-pulse.mp3", completion_rate=0.30, genre="electronic", mood="energetic")
    floor.leaf_falls("/music/04-chill-return.flac",     completion_rate=0.91, genre="ambient", mood="chill")

    print("\n── Root pulses ──")
    floor.root_pulse("playing")
    floor.root_pulse("genre")
    floor.root_pulse("library")

    print("\n── Mycelial surge: CLAP annotates 12 tracks ──")
    floor.mycelial_surge(n_tracks=12)

    print("\n── Heartbeats ──")
    for i in range(5):
        floor.heartbeat(progress=(i + 1) / 5.0, energy=0.5 + 0.3 * _math.sin(i * 1.2))

    print("\n── Enrichment pressure ──")
    floor.decompose(queue_len=18, total=500)

    print()
    print(floor.breathe())
    print()
    print(floor.soil_report())
