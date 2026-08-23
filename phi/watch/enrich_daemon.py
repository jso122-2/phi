# -*- coding: utf-8 -*-
"""phi.watch.enrich_daemon — background metadata enrichment worker.

Processes library tracks one at a time, rate-limited, pausing during
playback so it never competes with the audio engine for I/O or CPU.

Usage (in PhiApp.__init__)
--------------------------
    self.enrich = EnrichDaemon(
        library=self.library,
        review_queue=self.review_queue,
        is_playing=lambda: self.player.is_busy(),
        on_progress=self._on_enrich_progress,   # called on main thread via after()
        schedule=self.after,
    )
    self.enrich.start()

    # Later, once OctopusOrganizer has run:
    self.enrich.set_plan(plan)   # reorders the work queue immediately

The daemon is a daemon thread — it dies automatically when the process exits.
"""
from __future__ import annotations

import logging
import os
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures import TimeoutError as _FuturesTimeout
from dataclasses import dataclass, field
from typing import Callable, Optional, Any

_log = logging.getLogger("phi.enrich")

from phi.meta.consensus      import bpm_consensus, buoyancy_score, genre_consensus, meta_score
from phi.meta.discogs_client import DiscogsClient, build_discogs_client
from phi.meta.deezer_client  import DeezerClient, get_deezer_client
from phi.meta.enricher       import EnrichResult, enrich_track
from phi.meta.lastfm_meta    import fetch_track_info, get_lastfm_api_key
from phi.meta.lyrics         import get_lyrics
from phi.meta.mb_client      import MusicBrainzClient
from phi.meta.review_queue   import ReviewQueue
from phi.meta.spotify_client import SpotifyClient, build_spotify_client
from phi.meta.track_store    import TrackStore

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from phi.engine.forest_floor import ForestFloor

# OrganizationPlan is imported lazily to avoid a hard torch dependency at module load
_OrganizationPlan = None  # populated on first set_plan() call


# ── progress snapshot ─────────────────────────────────────────────────────────

@dataclass
class EnrichProgress:
    total:     int   = 0
    done:      int   = 0
    pending:   int   = 0     # in review queue
    failed:    int   = 0
    current:   str   = ""    # basename of track being processed
    running:   bool  = False
    paused:    bool  = False  # paused because audio is playing

    @property
    def pct(self) -> float:
        return (self.done / self.total * 100) if self.total > 0 else 0.0

    def status_line(self) -> str:
        if not self.running:
            return "idle"
        if self.paused:
            return f"paused  {self.done}/{self.total}"
        if self.current:
            import os
            return f"{self.done}/{self.total}  {os.path.basename(self.current)}"
        return f"{self.done}/{self.total}"


# ── daemon ────────────────────────────────────────────────────────────────────

class EnrichDaemon:
    """
    Background thread that enriches library tracks via AcoustID + MusicBrainz.

    Parameters
    ----------
    library         phi Library instance (read in background, written via schedule)
    review_queue    ReviewQueue shared with the UI
    api_key         AcoustID application API key. Pass an empty string to skip
                    AcoustID/MusicBrainz enrichment while still running all other
                    sources (Discogs, Deezer, Lyrics, Spotify, Last.fm, Consensus).
    is_playing      Callable returning True when audio is actively playing
    on_progress     Callback(EnrichProgress) — always invoked on the main thread
    schedule        Tk.after-compatible scheduler for thread-safe UI callbacks
    mb_contact      Contact email for MusicBrainz User-Agent header
    threshold       Auto-accept confidence threshold (default 0.70)
    write_back      Write enriched tags back to file (default True)
    inter_track_s   Sleep between tracks when not paused (default 1.0s)
    """

    # Re-run OctopusOrganizer every N enriched tracks so the plan stays fresh.
    _OCTOPUS_BATCH_SIZE = 10

    def __init__(
        self,
        library,
        review_queue:      ReviewQueue,
        api_key:           str,
        is_playing:        Callable[[], bool],
        on_progress:       Callable[[EnrichProgress], None],
        schedule:          Callable,
        *,
        mb_contact:        str                           = "phi@local",
        threshold:         float                         = 0.70,
        write_back:        bool                          = True,
        inter_track_s:     float                         = 1.0,
        enrich_online:     bool                          = False,
        meta_cache=None,
        floor:             Optional["ForestFloor"]       = None,
        on_batch_complete: Optional[Callable[[], None]]  = None,
    ) -> None:
        self._library      = library
        self._review_queue = review_queue
        self._api_key      = api_key
        self._is_playing   = is_playing
        self._on_progress  = on_progress
        self._schedule     = schedule
        self._threshold    = threshold
        self._write_back   = write_back
        self._inter_track  = inter_track_s
        self._enrich_online = enrich_online
        self._meta_cache   = meta_cache
        self._floor: Optional["ForestFloor"] = floor
        self._on_batch_complete = on_batch_complete
        self._batch_since_octopus = 0
        self._progress     = EnrichProgress()

        self._mb = MusicBrainzClient(
            app_name="phi",
            app_version="0.3.0",
            contact=mb_contact,
            max_per_sec=2.0,
        )

        # Online enrichment modules — only built when enrich_online=True so
        # the daemon never imports spotipy/discogs credentials in offline mode.
        if self._enrich_online:
            self._spotify:  SpotifyClient  | None = build_spotify_client()
            self._lfm_key:  str                   = get_lastfm_api_key()
            self._discogs:  DiscogsClient  | None = build_discogs_client()
            self._deezer:   DeezerClient          = get_deezer_client()
        else:
            self._spotify  = None
            self._lfm_key  = ""
            self._discogs  = None
            self._deezer   = None

        self._stop_event  = threading.Event()
        self._thread:    Optional[threading.Thread] = None

        # OctopusOrganizer plan — when set, enrichment follows octopus priority order
        self._org_plan = None     # type: Optional[Any]  # OrganizationPlan
        self._plan_lock = threading.Lock()

        # Local data store — writes per-track directories after enrichment
        self._track_store = TrackStore()
        self._store_pool  = ThreadPoolExecutor(max_workers=2, thread_name_prefix="phi-store")

        # Shared pool for concurrent API calls within a single track (Steps 2–6).
        # Only created in online mode; offline enrichment uses no external sources.
        self._api_pool: ThreadPoolExecutor | None = (
            ThreadPoolExecutor(max_workers=5, thread_name_prefix="phi-api")
            if self._enrich_online else None
        )

    # ── control ───────────────────────────────────────────────────────────────

    def set_plan(self, plan) -> None:
        """
        Hand the daemon an OrganizationPlan from OctopusOrganizer.

        When a plan is active, _unenriched_paths() returns tracks sorted by
        octopus priority (sprout × (1 − prune) + resurface × 0.30) rather
        than in arbitrary library order.

        Safe to call from any thread — protected by _plan_lock.
        Calling again with a newer plan replaces the old one immediately.

        Args:
            plan: OrganizationPlan (from phi.meta.octopus_organizer)
        """
        with self._plan_lock:
            self._org_plan = plan

    # ── control ───────────────────────────────────────────────────────────────

    def bind_floor(self, floor: "ForestFloor") -> None:
        """Attach the daemon to the CAIRRN forest floor substrate.

        Subscribes to shard 7 (COMMANDS hub, τ≈9.5).  When the enrichment
        queue pressure makes COMMANDS lose coherence, the daemon's inter-track
        sleep is shortened to 0.1s so it drains the backlog faster.  When the
        queue clears and coherence recovers, normal pacing resumes.

        Can be called after __init__ if the floor is not available at
        construction time (e.g. PhiApp wires it post-init).
        """
        self._floor = floor

        def _on_commands_shift(result, payload: dict) -> None:
            if result.should_act:
                # COMMANDS incoherent → enrichment backlog is high → sprint
                self._inter_track = 0.1
            else:
                # Coherence recovering → return to polite pacing
                self._inter_track = 1.0

        floor.when_floor_shifts(shard=7, handler=_on_commands_shift)

    def start(self) -> None:
        """Start the enrichment daemon (idempotent)."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
            name="phi-enrich",
        )
        self._thread.start()

    def stop(self) -> None:
        """Signal the daemon to stop after the current track finishes."""
        self._stop_event.set()

    @property
    def progress(self) -> EnrichProgress:
        return self._progress

    # ── worker ────────────────────────────────────────────────────────────────

    def _run(self) -> None:
        self._progress.running = True
        self._notify()

        while not self._stop_event.is_set():
            # Build the work list fresh each iteration so new tracks added
            # mid-session are picked up automatically.
            unenriched = self._unenriched_paths()

            if not unenriched:
                # All done — idle until library changes
                self._progress.running = False
                self._progress.current = ""
                self._notify()
                self._stop_event.wait(30)
                # Check again after wait
                if not self._unenriched_paths():
                    break
                self._progress.running = True
                continue

            self._progress.total   = len(unenriched) + self._progress.done
            self._progress.pending = self._review_queue.pending_count()
            self._notify()

            for path in unenriched:
                if self._stop_event.is_set():
                    break

                # Pause while audio is playing — don't steal I/O
                while self._is_playing() and not self._stop_event.is_set():
                    self._progress.paused = True
                    self._notify()
                    self._stop_event.wait(2.0)
                self._progress.paused = False

                self._progress.current = path
                self._notify()

                result = self._process(path)
                self._apply_result(result)

                self._progress.done   += 1
                self._progress.pending = self._review_queue.pending_count()
                self._notify()

                # After every _OCTOPUS_BATCH_SIZE tracks, signal OctopusOrganizer
                # to re-run on the main thread — the plan improves as more
                # librosa/CLAP embeddings become available.
                if self._on_batch_complete is not None:
                    self._batch_since_octopus += 1
                    if self._batch_since_octopus >= self._OCTOPUS_BATCH_SIZE:
                        self._batch_since_octopus = 0
                        self._schedule(0, self._on_batch_complete)

                # Polite inter-track wait
                if not self._stop_event.is_set():
                    self._stop_event.wait(self._inter_track)

        self._progress.running = False
        self._progress.current = ""
        self._notify()

    def _unenriched_paths(self) -> list[str]:
        """
        Return paths that still need enrichment from any source.

        When an OctopusOrganizer plan is active (set via set_plan()), tracks
        are returned in octopus priority order — highest sprout/resurface, lowest
        prune first.  Tracks flagged by the prune arm (score ≥ 0.75) are
        placed at the end of the queue rather than skipped entirely so the
        user can review them.

        Falls back to library playlist order when no plan is available.
        """
        # Snapshot the plan atomically
        with self._plan_lock:
            plan = self._org_plan

        # Build the set of paths that need enrichment
        needs_enrich: set[str] = set()
        for path in list(self._library.playlist):
            ann = self._library.get_annotation(path)

            # MB needs fingerprinting if: api key present AND not yet enriched AND
            # (never fingerprinted  OR  previously got no match but retry is due)
            needs_fp      = not ann.get("acoustid_fp")
            no_match_retry = (
                ann.get("acoustid_no_match")
                and self._acoustid_retry_due(ann)
            )
            needs_mb      = bool(self._api_key) and not ann.get("mb_enriched") and (needs_fp or no_match_retry)

            needs_sp      = self._spotify is not None and ann.get("spotify_enriched") is None
            needs_lf      = bool(self._lfm_key)        and not ann.get("lfm_enriched")
            needs_discogs = self._discogs is not None  and not ann.get("discogs_enriched")
            needs_deezer  = self._deezer  is not None  and not ann.get("deezer_enriched")
            needs_lyrics  = self._enrich_online        and not ann.get("lyrics_enriched")
            needs_artist  = bool(ann.get("artist_mbid")) and not ann.get("mb_artist_enriched")
            needs_meta    = not ann.get("meta_score")
            if needs_mb or needs_sp or needs_lf or needs_discogs or needs_deezer \
               or needs_lyrics or needs_artist or needs_meta:
                needs_enrich.add(path)

        if not needs_enrich:
            # No backlog — tell the floor the queue is empty
            if self._floor is not None:
                try:
                    self._floor.decompose(queue_len=0, total=max(len(self._library.playlist), 1))
                except Exception:
                    pass
            return []

        # Signal queue pressure into the COMMANDS hub on the forest floor.
        # High queue_len → COMMANDS loses coherence → shard-7 subscribers sprint.
        if self._floor is not None:
            try:
                self._floor.decompose(
                    queue_len=len(needs_enrich),
                    total=max(len(self._library.playlist), 1),
                )
            except Exception:
                pass

        # If an octopus plan is available, reorder using its priority ranking
        if plan is not None:
            # Separate prune-flagged tracks (score ≥ 0.75) to end of queue
            normal:  list[str] = []
            pruning: list[str] = []
            seen:    set[str]  = set()

            for job in plan.enrich_queue:
                if job.path in needs_enrich and job.path not in seen:
                    seen.add(job.path)
                    if job.prune_score >= 0.75:
                        pruning.append(job.path)
                    else:
                        normal.append(job.path)

            # Append any tracks the plan didn't cover (added after organiser ran)
            remainder = [p for p in self._library.playlist
                         if p in needs_enrich and p not in seen]

            return normal + remainder + pruning

        # No plan — preserve original library order
        return [p for p in self._library.playlist if p in needs_enrich]

    _ACOUSTID_RETRY_DAYS = 7   # retry no-match tracks after this many days

    def _acoustid_retry_due(self, ann: dict) -> bool:
        """Return True when a previous no-match is old enough to retry."""
        attempted_at = ann.get("acoustid_attempted_at")
        if not attempted_at:
            return True
        try:
            return (time.time() - float(attempted_at)) > self._ACOUSTID_RETRY_DAYS * 86_400
        except Exception:
            return True

    def _process(self, path: str) -> EnrichResult:
        """Run the full enrichment pipeline for one track.

        Step 1 (AcoustID → MusicBrainz) runs first — provides ISRC and
        canonical meta that downstream sources use for their searches.
        Steps 2–6 (Spotify / Last.fm / Discogs / Deezer / Lyrics) are
        independent and run concurrently via the shared API thread pool,
        cutting per-track latency from ~sum(T_i) to ~max(T_i).
        Steps 7–8 (artist enrichment, consensus scoring) run last so that
        consensus sees the full merged annotation picture.
        """
        existing_meta = self._library.get_meta(path)
        ann           = self._library.get_annotation(path)

        # ── Step 1: AcoustID → MusicBrainz (sequential — all steps depend on it)
        result = EnrichResult(path=path)
        no_match_retry = (
            ann.get("acoustid_no_match")
            and self._acoustid_retry_due(ann)
        )
        should_run_mb = (
            self._api_key
            and not ann.get("mb_enriched")
            and (not ann.get("acoustid_fp") or no_match_retry)
        )
        if should_run_mb:
            if no_match_retry:
                self._library.store_annotation(path, {
                    "acoustid_no_match":    None,
                    "acoustid_fp":          None,
                    "acoustid_attempted_at": None,
                })
            result = enrich_track(
                path=path,
                api_key=self._api_key,
                mb_client=self._mb,
                review_queue=self._review_queue,
                existing_meta=existing_meta,
                threshold=self._threshold,
                write_back=self._write_back,
            )
            if result.merged_meta:
                existing_meta = (
                    {**existing_meta, **result.merged_meta} if existing_meta
                    else result.merged_meta
                )

        # ── Steps 2–6: independent API sources — gather concurrently ─────────
        # Derive common lookup args from the best available meta after Step 1.
        title  = (existing_meta or {}).get("title")  or ""
        artist = (existing_meta or {}).get("artist") or ""
        album  = (existing_meta or {}).get("album")  or ""
        isrc   = (ann.get("isrc") or (existing_meta or {}).get("isrc") or "").strip()

        if self._api_pool is not None:
            futures: dict = {}

            if self._spotify and not ann.get("spotify_enriched"):
                futures[self._api_pool.submit(
                    self._step_spotify, title, artist, album, isrc, existing_meta
                )] = "spotify"

            if self._lfm_key and not ann.get("lfm_enriched") and (title or artist):
                futures[self._api_pool.submit(
                    self._step_lastfm, title, artist, existing_meta
                )] = "lastfm"

            if self._discogs and not ann.get("discogs_enriched") and (title or artist):
                futures[self._api_pool.submit(
                    self._step_discogs, title, artist, existing_meta
                )] = "discogs"

            if self._deezer and not ann.get("deezer_enriched") and (title or artist):
                futures[self._api_pool.submit(
                    self._step_deezer, title, artist
                )] = "deezer"

            if self._enrich_online and not ann.get("lyrics_enriched"):
                futures[self._api_pool.submit(
                    self._step_lyrics, path, existing_meta
                )] = "lyrics"

            if futures:
                try:
                    for fut in as_completed(futures, timeout=30):
                        try:
                            ann_update, meta_update = fut.result()
                        except Exception as exc:
                            _log.debug(
                                "API step failed for %s: %s",
                                os.path.basename(path), exc,
                            )
                            continue
                        result.annotation.update(ann_update)
                        if meta_update:
                            result.merged_meta = result.merged_meta or {}
                            result.merged_meta.update(meta_update)
                except _FuturesTimeout:
                    _log.warning(
                        "Enrichment API timeout (30s) for %s; partial results applied",
                        os.path.basename(path),
                    )

        # ── Step 7: MusicBrainz artist enrichment ─────────────────────────────
        # artist_mbid can come from the pre-existing annotation OR from Step 1/2.
        artist_mbid = ann.get("artist_mbid") or result.annotation.get("artist_mbid")
        if artist_mbid and not ann.get("mb_artist_enriched"):
            artist_data = self._mb.fetch_artist(artist_mbid)
            if artist_data:
                result.annotation.update(artist_data)

        # ── Step 8: Consensus + completeness score ────────────────────────────
        full_ann  = {**ann, **result.annotation}
        full_meta = {**(existing_meta or {}), **(result.merged_meta or {})}

        result.annotation.update(bpm_consensus(full_ann, full_meta))
        result.annotation.update(genre_consensus(full_ann, full_meta))
        result.annotation.update(meta_score(
            {**full_ann, **result.annotation},
            full_meta,
        ))
        # Buoyancy runs last — reads bpm_confidence + genre_consensus just written above.
        result.annotation["buoyancy"] = buoyancy_score(
            {**full_ann, **result.annotation},
            full_meta,
        )

        result.success = True
        return result

    # ── per-source step helpers (each returns (annotation_dict, meta_dict)) ──

    def _step_spotify(
        self,
        title: str,
        artist: str,
        album: str,
        isrc: str,
        existing_meta: Optional[dict],
    ) -> tuple[dict, dict]:
        ann_update: dict = {}
        meta_update: dict = {}
        try:
            sp_track = None
            if isrc:
                sp_track = self._spotify.enrich_track_by_isrc(isrc)
            if sp_track is None and (title or artist):
                sp_track = self._spotify.enrich_track(title, artist, album)
            if sp_track is not None:
                ann_update.update(sp_track.as_annotation_dict())
                if sp_track.art_bytes and not (existing_meta or {}).get("art_bytes"):
                    meta_update["art_bytes"] = sp_track.art_bytes
                if sp_track.isrc and not (existing_meta or {}).get("isrc"):
                    meta_update["isrc"] = sp_track.isrc
            else:
                ann_update["spotify_enriched"] = False
        except Exception as exc:
            _log.debug("Spotify step error: %s", exc)
        return ann_update, meta_update

    def _step_lastfm(
        self,
        title: str,
        artist: str,
        existing_meta: Optional[dict],
    ) -> tuple[dict, dict]:
        ann_update: dict = {}
        meta_update: dict = {}
        try:
            lfm_info = fetch_track_info(title, artist, self._lfm_key)
            if lfm_info is not None:
                ann_update.update(lfm_info.as_annotation_dict())
                top_tag = lfm_info.top_tag
                if top_tag and not (existing_meta or {}).get("genre"):
                    meta_update.setdefault("genre", top_tag)
        except Exception as exc:
            _log.debug("Last.fm step error: %s", exc)
        return ann_update, meta_update

    def _step_discogs(
        self,
        title: str,
        artist: str,
        existing_meta: Optional[dict],
    ) -> tuple[dict, dict]:
        ann_update: dict = {}
        meta_update: dict = {}
        try:
            year_raw = (existing_meta or {}).get("year")
            year = int(year_raw) if year_raw and str(year_raw).isdigit() else None
            discogs_rel = self._discogs.search_release(title, artist, year=year)
            if discogs_rel is not None:
                ann_update.update(discogs_rel.as_annotation_dict())
                if not (existing_meta or {}).get("genre") and discogs_rel.styles:
                    meta_update.setdefault("genre", discogs_rel.styles[0])
        except Exception as exc:
            _log.debug("Discogs step error: %s", exc)
        return ann_update, meta_update

    def _step_deezer(
        self,
        title: str,
        artist: str,
    ) -> tuple[dict, dict]:
        ann_update: dict = {}
        meta_update: dict = {}
        try:
            deezer_track = self._deezer.search_track(title, artist)
            if deezer_track is not None:
                ann_update.update(deezer_track.as_annotation_dict())
                if deezer_track.preview:
                    meta_update.setdefault("preview_url", deezer_track.preview)
        except Exception as exc:
            _log.debug("Deezer step error: %s", exc)
        return ann_update, meta_update

    def _step_lyrics(
        self,
        path: str,
        existing_meta: Optional[dict],
    ) -> tuple[dict, dict]:
        ann_update: dict = {}
        try:
            lyrics_text = get_lyrics(path, existing_meta)
            if lyrics_text:
                ann_update["lyrics_text"]     = lyrics_text
                ann_update["lyrics_enriched"] = True
            else:
                ann_update["lyrics_enriched"] = False
        except Exception as exc:
            _log.debug("Lyrics step error: %s", exc)
        return ann_update, {}

    def _apply_result(self, result: EnrichResult) -> None:
        """Apply enrichment result to the library (thread-safe via schedule)."""
        def _apply():
            if result.merged_meta:
                self._library.store_meta(result.path, result.merged_meta)
            if result.annotation:
                self._library.store_annotation(result.path, result.annotation)
                if self._meta_cache is not None:
                    try:
                        self._meta_cache.put_annotation(result.path, result.annotation)
                    except Exception:
                        pass

        self._schedule(0, _apply)

        # Fire-and-forget: refresh the per-track directory in the local store.
        # Runs in a low-priority pool so it never blocks the enrichment loop.
        if result.success:
            self._store_pool.submit(self._update_track_store, result.path)

    def _update_track_store(self, path: str) -> None:
        """Rebuild the per-track directory for *path* (called from store pool)."""
        try:
            self._track_store.build_one(path, force=True)
        except Exception:
            pass

    def _notify(self) -> None:
        """Push progress snapshot to the main thread."""
        snapshot = EnrichProgress(
            total=self._progress.total,
            done=self._progress.done,
            pending=self._progress.pending,
            failed=self._progress.failed,
            current=self._progress.current,
            running=self._progress.running,
            paused=self._progress.paused,
        )
        self._schedule(0, lambda: self._on_progress(snapshot))
