# -*- coding: utf-8 -*-
"""phi.core.meta_worker — background metadata loading and model annotation.

Owns two responsibilities:
- Single-track async meta (read tag → store → fire on_meta_ready callback)
- Batch background prime (bulk SQL read → store → schedule model annotation run)

All UI side-effects are inverted via callbacks so this module stays import-clean
from UI code.
"""
from __future__ import annotations

import queue
import threading
from typing import TYPE_CHECKING, Callable

from phi.meta.reader import bulk_prime_cache, read_meta_cached

# Pre-import all mutagen format modules on the main thread at startup.
#
# mutagen.File() lazy-imports format-specific submodules (mp3, flac, ogg…)
# the first time it sees each audio format.  When multiple _fetch_duration_worker
# threads call mutagen.File() concurrently on startup, they each trigger
# source_to_code() for the same mutagen submodule simultaneously.  On macOS
# Apple Silicon this concurrent bytecode compilation race causes SIGBUS.
#
# Importing everything here forces all format-module compilation to happen on
# the main thread before any background worker is spawned.
try:
    # Pre-import every mutagen submodule that File() can dispatch to.
    # mutagen.File() lazy-imports the format module the first time it sees
    # a given audio format.  When multiple _fetch_duration_worker threads
    # call File() concurrently, they race on these first-time imports and
    # hit Python 3.11's importlib mmap race on Apple Silicon → SIGBUS.
    import mutagen._constants   # noqa: F401
    import mutagen._file        # noqa: F401
    import mutagen._iff         # noqa: F401
    import mutagen._riff        # noqa: F401
    import mutagen._tags        # noqa: F401
    import mutagen._tools       # noqa: F401
    import mutagen._util        # noqa: F401
    import mutagen._vorbis      # noqa: F401
    import mutagen.aac          # noqa: F401
    import mutagen.ac3          # noqa: F401
    import mutagen.aiff         # noqa: F401
    import mutagen.apev2        # noqa: F401
    import mutagen.asf          # noqa: F401
    import mutagen.dsdiff       # noqa: F401
    import mutagen.dsf          # noqa: F401
    import mutagen.easyid3      # noqa: F401
    import mutagen.easymp4      # noqa: F401
    import mutagen.flac         # noqa: F401
    import mutagen.id3          # noqa: F401
    import mutagen.m4a          # noqa: F401
    import mutagen.monkeysaudio # noqa: F401
    import mutagen.mp3          # noqa: F401
    import mutagen.mp4          # noqa: F401
    import mutagen.musepack     # noqa: F401
    import mutagen.ogg          # noqa: F401
    import mutagen.oggflac      # noqa: F401
    import mutagen.oggopus      # noqa: F401
    import mutagen.oggspeex     # noqa: F401
    import mutagen.oggtheora    # noqa: F401
    import mutagen.oggvorbis    # noqa: F401
    import mutagen.optimfrog    # noqa: F401
    import mutagen.smf          # noqa: F401
    import mutagen.tak          # noqa: F401
    import mutagen.trueaudio    # noqa: F401
    import mutagen.wave         # noqa: F401
    import mutagen.wavpack      # noqa: F401
    from mutagen import File as _MutagenFile
except Exception:
    _MutagenFile = None  # type: ignore[assignment]

if TYPE_CHECKING:
    from phi.core.library import Library
    from phi.meta.cache import MetaCache
    from phi.models.registry import ModelRegistry
    from phi.engine.forest_floor import ForestFloor


class MetaWorker:
    """Background metadata loader and model annotation scheduler.

    Args:
        library:            The shared track library.
        meta_cache:         Persistent metadata cache (SQLite).
        models:             Model registry for annotation runs.
        schedule:           ``widget.after`` — posts callables to the main thread.
        on_meta_ready:      Called on the main thread: ``(path, meta) -> None``.
        on_refresh:         Called on the main thread after a batch completes.
        on_flush:           Called after each annotation run to flush to disk.
        floor:              ForestFloor for CAIRRN heartbeats.
        get_duration:       Returns current playback duration float.
        set_duration:       Stores the fetched audio duration.
        on_duration_ready:  Called on the main thread: ``(dur) -> None``.
    """

    def __init__(
        self,
        library: "Library",
        meta_cache: "MetaCache",
        models: "ModelRegistry",
        schedule: Callable,
        on_meta_ready: Callable[[str, dict], None],
        on_refresh: Callable[[], None],
        on_flush: Callable[[], None],
        floor: "ForestFloor",
        get_duration: Callable[[], float],
        set_duration: Callable[[float], None],
        on_duration_ready: Callable[[float], None],
    ) -> None:
        self._library = library
        self._meta_cache = meta_cache
        self._models = models
        self._schedule = schedule
        self._on_meta_ready = on_meta_ready
        self._on_refresh = on_refresh
        self._on_flush = on_flush
        self._floor = floor
        self._get_duration = get_duration
        self._set_duration = set_duration
        self._on_duration_ready = on_duration_ready

        # Tracks the most recently requested path so _fetch_duration_worker can
        # discard results that arrived after the user has already moved on.
        self._last_fetch_path: str = ""

        # Single persistent duration-fetch thread.  All fetch_duration() calls
        # enqueue here; the loop drains to the latest request so rapid track
        # changes (skip-skip-skip) only open the file for the track currently
        # playing, eliminating per-track thread spawning and I/O contention
        # with the AVPlayer channel that has the same file already open.
        self._duration_queue: queue.Queue[str | None] = queue.Queue()
        _dt = threading.Thread(
            target=self._duration_loop,
            name="phi-duration",
            daemon=True,
        )
        _dt.start()

    # ──────────────────────────────────────────────────────── single-track ──

    def async_meta(self, path: str) -> None:
        """Fire-and-forget: read meta for *path*, schedule on_meta_ready on main thread."""
        threading.Thread(target=self._async_meta_worker, args=(path,), daemon=True).start()

    def _async_meta_worker(self, path: str) -> None:
        meta = read_meta_cached(path, self._meta_cache)
        self._library.store_meta(path, meta)
        self._schedule(0, lambda: self._on_meta_ready(path, meta))

    def fetch_duration(self, path: str) -> None:
        """Enqueue *path* for duration reading on the persistent duration thread.

        Replaces the old per-call threading.Thread spawn.  The persistent thread
        drains the queue to its latest entry so that rapid track changes never
        open stale files, and mutagen never races against AVPlayer's open handle.
        """
        self._last_fetch_path = path
        self._duration_queue.put(path)

    def _duration_loop(self) -> None:
        """Persistent daemon: drain to latest request, then fetch duration."""
        while True:
            path = self._duration_queue.get()
            if path is None:          # sentinel — shut down gracefully
                return
            # Drain: if more requests arrived while we were blocked, take the newest.
            try:
                while True:
                    path = self._duration_queue.get_nowait()
            except queue.Empty:
                pass
            if path is not None:
                self._fetch_duration_worker(path)

    def _fetch_duration_worker(self, path: str) -> None:
        try:
            if _MutagenFile is None:
                return
            _mf = _MutagenFile(path)
            dur = float(_mf.info.length) if _mf and hasattr(_mf, "info") else 0.0
        except Exception:
            return
        # Guard: if the user skipped tracks while mutagen was reading, discard
        # this result — applying a stale duration corrupts the seek bar and the
        # crossfade trigger for the track that is now actually playing.
        if path != self._last_fetch_path:
            return
        if dur > 0:
            self._set_duration(dur)
            self._schedule(0, lambda d=dur: self._on_duration_ready(d))

    # ──────────────────────────────────────────────────────────── batch ──

    def bg_meta(self, paths: list[str]) -> None:
        """Spawn background thread to load metadata for *paths*, then run models."""
        if paths:
            self._floor.library_changed(
                n_added=len(paths),
                n_removed=0,
                total=self._library.size,
            )
        threading.Thread(target=self._bg_meta_sync, args=(paths,), daemon=True).start()

    def _bg_meta_sync(self, paths: list[str]) -> None:
        all_meta = bulk_prime_cache(paths, self._meta_cache)
        for path, meta in all_meta.items():
            self._library.store_meta(path, meta)

        self._meta_cache.prune(set(self._library.playlist))
        self._schedule(0, self._on_refresh)
        self._schedule(0, lambda ps=list(paths): self.schedule_model_run(ps))

    def schedule_model_run(self, paths: list[str]) -> None:
        """Kick off a background model annotation pass. Already-annotated tracks are skipped.

        CAIRRN MATH gate: when CLAPModel raises _needs_reprocess (MATH hub
        went incoherent), expands the pass to all unannotated library tracks
        so newly coherent embedding space is fully filled before the next
        similarity search.
        """
        if self._models.running:
            return

        try:
            from phi.models import clap_model as _clap_mod
            if _clap_mod.needs_reprocess():
                _clap_mod.clear_reprocess()
                unannotated = [
                    p for p in self._library.playlist
                    if not (self._library.get_annotation(p) or {}).get("mood_source")
                ]
                paths = list(set(paths) | set(unannotated))
        except Exception:
            pass

        if not paths:
            return

        n_paths = len(paths)

        def _done() -> None:
            self._on_flush()
            self._floor.mycelial_surge(n_paths)

        self._models.run_batch(
            paths,
            self._library,
            schedule=self._schedule,
            on_done=_done,
        )
