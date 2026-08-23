# -*- coding: utf-8 -*-
"""phi.meta.art_spider — background daemon that fills missing album art.

Crawl strategy (in order, stops on first hit per track):
    1. Deezer album cover  — free, no auth, 250 × 250 JPEG
    2. CoverArtArchive     — free, no auth, via release_mbid from annotations
    3. Folder scan         — cover.jpg / cover.png / folder.jpg in same dir

The spider runs in a daemon thread and respects rate limits already built
into DeezerClient and MBClient.  It is intentionally slow (≤ 1 resolved
track / second) so it never competes with playback I/O.

Public API
----------
    spider = ArtSpider(library, cache)
    spider.start()          — begin background crawl
    spider.stop()           — signal stop (non-blocking)
    spider.status()         — dict: total, done, pending, errors, running
    spider.kick()           — wake up if sleeping (e.g. after library scan)
"""
from __future__ import annotations

import os
import sqlite3
import threading
import time
import urllib.request
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from phi.core.library import Library
    from phi.meta.cache import MetaCache

_UA = "phi-art-spider/1.0 (local music player)"
_TIMEOUT = 10
_SLEEP_BETWEEN = 0.9   # seconds between resolved tracks (≈ 1 req/s net)
_SLEEP_IDLE    = 30.0  # seconds to sleep when no work is queued


class ArtSpider:
    """
    Background art-fetching daemon.

    Parameters
    ----------
    library : Library
        Live library instance — in-memory meta_cache is patched on hit.
    cache   : MetaCache
        Persistent SQLite cache — art_bytes column is patched on hit.
    """

    def __init__(self, library: "Library", cache: "MetaCache") -> None:
        self._library = library
        self._cache   = cache
        self._thread: Optional[threading.Thread] = None
        self._stop    = threading.Event()
        self._wake    = threading.Event()
        self._lock    = threading.Lock()

        self._total   = 0
        self._done    = 0
        self._errors  = 0
        self._running = False
        self._current = ""

    # ── public ────────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the spider thread if not already running."""
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop.clear()
            self._thread = threading.Thread(
                target=self._run, daemon=True, name="art-spider"
            )
            self._thread.start()

    def stop(self) -> None:
        """Signal the spider to stop after its current track."""
        self._stop.set()
        self._wake.set()

    def kick(self) -> None:
        """Wake the spider immediately (call after adding new library paths)."""
        self._wake.set()

    def status(self) -> dict:
        with self._lock:
            return {
                "running":  self._running,
                "total":    self._total,
                "done":     self._done,
                "errors":   self._errors,
                "pending":  max(0, self._total - self._done - self._errors),
                "current":  self._current,
            }

    # ── internal loop ─────────────────────────────────────────────────────────

    def _run(self) -> None:
        with self._lock:
            self._running = True

        try:
            while not self._stop.is_set():
                paths = self._cache.paths_missing_art()
                # Also include library paths not yet in cache
                lib_paths = list(self._library.playlist)
                missing = [
                    p for p in lib_paths
                    if p in paths or (
                        not (self._library.get_meta(p) or {}).get("art_bytes")
                        and p not in paths
                    )
                ]
                # Deduplicate while preserving order
                seen: set[str] = set()
                work: list[str] = []
                for p in paths + [m for m in missing if m not in paths]:
                    if p not in seen:
                        seen.add(p)
                        work.append(p)

                with self._lock:
                    self._total = len(work)

                if not work:
                    self._wake.clear()
                    self._wake.wait(timeout=_SLEEP_IDLE)
                    continue

                for path in work:
                    if self._stop.is_set():
                        break

                    with self._lock:
                        self._current = os.path.basename(path)

                    try:
                        art = self._fetch_art(path)
                    except sqlite3.ProgrammingError:
                        # Cache connection was closed (app is shutting down).
                        # Exit the loop cleanly instead of crashing the thread.
                        return

                    if art:
                        self._patch(path, art)
                        with self._lock:
                            self._done += 1
                        time.sleep(_SLEEP_BETWEEN)
                    else:
                        with self._lock:
                            self._errors += 1

                with self._lock:
                    self._current = ""
        finally:
            with self._lock:
                self._running = False

    def _fetch_art(self, path: str) -> Optional[bytes]:
        """Try each source in order, return bytes on first hit."""
        meta = self._library.get_meta(path) or {}
        title  = meta.get("title")  or os.path.splitext(os.path.basename(path))[0]
        artist = meta.get("artist") or ""
        album  = meta.get("album")  or ""

        # ── 1. Deezer album cover ─────────────────────────────────────────────
        if title or artist:
            art = self._deezer_art(title, artist)
            if art:
                return art

        # ── 2. CoverArtArchive via release_mbid ──────────────────────────────
        ann = self._cache.get_annotation(path) or {}
        release_mbid = ann.get("release_mbid")
        if release_mbid:
            art = self._caa_art(release_mbid)
            if art:
                return art

        # ── 3. Folder scan ────────────────────────────────────────────────────
        return self._folder_art(path)

    def _deezer_art(self, title: str, artist: str) -> Optional[bytes]:
        try:
            from phi.meta.deezer_client import get_deezer_client
            return get_deezer_client().fetch_album_art_bytes(title, artist)
        except Exception:
            return None

    def _caa_art(self, release_mbid: str) -> Optional[bytes]:
        try:
            url = f"https://coverartarchive.org/release/{release_mbid}/front-250"
            req = urllib.request.Request(url, headers={"User-Agent": _UA})
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                return resp.read()
        except Exception:
            return None

    def _folder_art(self, path: str) -> Optional[bytes]:
        folder = os.path.dirname(path)
        for name in ("cover.jpg", "cover.png", "folder.jpg",
                     "artwork.jpg", "front.jpg", "AlbumArt.jpg"):
            candidate = os.path.join(folder, name)
            if os.path.isfile(candidate):
                try:
                    with open(candidate, "rb") as f:
                        return f.read()
                except Exception:
                    pass
        return None

    def _patch(self, path: str, art_bytes: bytes) -> None:
        """Write art to cache, hot-patch the live library, and bake ASCII."""
        # Persistent cache
        self._cache.patch_art(path, art_bytes)
        # In-memory library cache (so the panel updates without restart)
        meta = self._library.meta_cache.get(path)
        if meta is not None:
            meta["art_bytes"] = art_bytes
        # Pre-bake the coloured ASCII grid so first render is instant.
        # ascii_bake is idempotent — no-op if the file already exists.
        from phi.meta.art import ascii_bake  # noqa: PLC0415
        threading.Thread(target=ascii_bake, args=(art_bytes,), daemon=True).start()


# ── module-level singleton ────────────────────────────────────────────────────

_spider: Optional[ArtSpider] = None
_spider_lock = threading.Lock()


def get_art_spider(library: "Library", cache: "MetaCache") -> "ArtSpider":
    """Return the shared ArtSpider singleton (created on first call)."""
    global _spider
    with _spider_lock:
        if _spider is None:
            _spider = ArtSpider(library, cache)
    return _spider
