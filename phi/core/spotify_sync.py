# -*- coding: utf-8 -*-
"""phi.core.spotify_sync — full Spotify → local playlist sync.

Four-phase pipeline
-------------------
1. SCRAPE    — fetch all user playlists + track lists from Spotify API
2. MATCH     — resolve each Spotify track to an existing local audio file
               Priority: ISRC exact match → title/artist path scan
3. DOWNLOAD  — fetch unmatched tracks via YouTubeMusicSource (yt-dlp)
4. IMPORT    — upsert all playlists into PlaylistStore

The download step is optional (``download_missing=False`` skips it) so you can
import what you already have without waiting for the full download run.

Sync state is written to ``~/.phi/spotify_sync_manifest.json`` after each
successful run, recording which playlist snapshot_ids have been synced so
future calls only re-download changed playlists.

Usage (programmatic)
--------------------
    from phi.core.spotify_sync import SpotifySync

    syncer = SpotifySync(
        download_dir = Path.home() / "Documents/misc/Spotify/Playlists",
    )
    result = syncer.run(
        library          = app.library,
        store            = app.playlist_store,
        download_missing = True,
        on_progress      = print,
    )
    print(result.summary())

CLI
---
    python -m phi.core.spotify_sync
    python -m phi.core.spotify_sync --no-download
    python -m phi.core.spotify_sync --dry-run
    python -m phi.core.spotify_sync --limit 5      # sync first 5 playlists only
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

log = logging.getLogger(__name__)

_DEFAULT_SPOTIFY_ROOT = Path.home() / "Documents" / "misc" / "Spotify"
_MANIFEST_PATH = Path.home() / ".phi" / "spotify_sync_manifest.json"
_AUDIO_EXTS    = frozenset({".mp3", ".flac", ".wav", ".m4a", ".ogg"})


# ── result dataclass ──────────────────────────────────────────────────────────

@dataclass
class SyncResult:
    playlists_scraped:   int = 0
    playlists_created:   int = 0
    playlists_updated:   int = 0
    tracks_matched:      int = 0    # already on disk, linked
    tracks_downloaded:   int = 0    # newly downloaded
    tracks_failed:       int = 0    # download attempted but failed
    tracks_skipped:      int = 0    # download skipped (no credentials, dry-run)
    errors:              list[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            f"Spotify sync complete:",
            f"  {self.playlists_scraped} playlists scraped from API",
            f"  {self.playlists_created} created  ·  {self.playlists_updated} updated in store",
            f"  {self.tracks_matched} tracks matched locally",
        ]
        if self.tracks_downloaded:
            lines.append(f"  {self.tracks_downloaded} tracks downloaded")
        if self.tracks_failed:
            lines.append(f"  {self.tracks_failed} tracks failed to download")
        if self.tracks_skipped:
            lines.append(f"  {self.tracks_skipped} tracks skipped (no audio found)")
        if self.errors:
            lines.append(f"  {len(self.errors)} errors")
        return "\n".join(lines)


# ── manifest ──────────────────────────────────────────────────────────────────

def _load_manifest() -> dict:
    """Load the sync manifest from disk. Returns {} if missing."""
    try:
        return json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_manifest(manifest: dict) -> None:
    _MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    _MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


# ── local file scanner ────────────────────────────────────────────────────────

class _LocalIndex:
    """
    Fast in-memory index of local audio files.

    Supports two lookup strategies:
      1. ISRC exact match  (ann["isrc"] → path)
      2. Fuzzy title+artist match  (normalised string comparison)
    """

    def __init__(self, library) -> None:
        self._by_isrc:   dict[str, str] = {}
        self._by_stem:   dict[str, str] = {}   # lower-normalised stem → path

        for path in library.playlist:
            # ISRC from annotation
            try:
                ann  = library.get_annotation(path) or {}
                isrc = (ann.get("isrc") or "").strip().upper()
                if isrc:
                    self._by_isrc[isrc] = path
            except Exception:
                pass

            # Stem-based index for fuzzy matching
            stem = os.path.splitext(os.path.basename(path))[0].lower()
            self._by_stem[stem] = path

            # Also index from meta title+artist
            try:
                meta   = library.get_meta(path) or {}
                title  = (meta.get("title")  or "").strip().lower()
                artist = (meta.get("artist") or "").strip().lower()
                if title and artist:
                    key = f"{artist} - {title}"
                    self._by_stem[key] = path
            except Exception:
                pass

    def find(self, track) -> Optional[str]:
        """
        Return the local path for *track* (a SpotifyTrackMeta), or None.

        Tries ISRC first, then normalised title+artist.
        """
        # 1. ISRC exact match
        isrc = (track.isrc or "").strip().upper()
        if isrc and isrc in self._by_isrc:
            return self._by_isrc[isrc]

        # 2. Normalised title+artist
        key = f"{track.artist.lower()} - {track.name.lower()}"
        if key in self._by_stem:
            return self._by_stem[key]

        # 3. Filename stem match (safe_filename)
        stem = track.safe_filename.lower()
        if stem in self._by_stem:
            return self._by_stem[stem]

        return None


# ── sidecar writer ────────────────────────────────────────────────────────────

def _write_sidecar(audio_path: Path, track) -> None:
    """Write a .json sidecar file alongside *audio_path* with track metadata."""
    sidecar = audio_path.with_suffix(".json")
    data = {
        "spotify_id":    track.spotify_id,
        "name":          track.name,
        "artist":        track.artist,
        "album":         track.album,
        "isrc":          track.isrc,
        "duration_ms":   track.duration_ms,
        "added_at":      track.added_at,
        "track_number":  track.track_number,
    }
    try:
        sidecar.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception as exc:
        log.debug("_write_sidecar: failed for %s: %s", sidecar.name, exc)


# ── SpotifySync ───────────────────────────────────────────────────────────────

class SpotifySync:
    """
    Full Spotify → local playlist sync orchestrator.

    Parameters
    ----------
    download_dir  : root under which per-playlist subdirectories are created
                    (default ~/Documents/misc/Spotify/Playlists)
    audio_format  : yt-dlp audio format (default "mp3")
    max_workers   : parallel download threads (default 1 to be polite)
    """

    def __init__(
        self,
        download_dir:  Optional[Path] = None,
        audio_format:  str            = "mp3",
        max_workers:   int            = 1,
    ) -> None:
        self._dl_root     = Path(download_dir) if download_dir else (
            _DEFAULT_SPOTIFY_ROOT / "Playlists"
        )
        self._fmt         = audio_format
        self._max_workers = max_workers

    # ── public ────────────────────────────────────────────────────────────────

    def run(
        self,
        library,
        store,
        *,
        download_missing: bool = True,
        dry_run:          bool = False,
        limit:            Optional[int] = None,
        on_progress:      Optional[Callable[[str], None]] = None,
        user_client       = None,
    ) -> SyncResult:
        """
        Execute the full sync pipeline.

        Parameters
        ----------
        library          : phi Library instance (for ISRC/meta lookups)
        store            : PlaylistStore instance (destination)
        download_missing : if True, download tracks not found locally via yt-dlp
        dry_run          : report actions without writing anything
        limit            : stop after this many playlists (None = all)
        on_progress      : callback(message: str) for progress reporting
        user_client      : SpotifyUserClient — if None, one is built from config

        Returns
        -------
        SyncResult with counts and any error messages.
        """
        result   = SyncResult()
        progress = on_progress or (lambda msg: None)

        # ── 1. Authenticate + scrape playlists ────────────────────────────────
        if user_client is None:
            from phi.meta.spotify_user_client import build_user_client
            user_client = build_user_client()

        if user_client is None:
            result.errors.append(
                "Spotify user client unavailable — check phi_config.yaml credentials"
            )
            return result

        progress("Fetching playlist list from Spotify…")
        playlists = user_client.get_all_playlists()
        if not playlists:
            result.errors.append("No playlists returned from Spotify API")
            return result

        if limit is not None:
            playlists = playlists[:limit]

        result.playlists_scraped = len(playlists)
        progress(f"Scraped {len(playlists)} playlists")

        # ── 2. Build local file index ─────────────────────────────────────────
        progress("Indexing local library…")
        local_index = _LocalIndex(library)

        # ── 3. Load sync manifest ─────────────────────────────────────────────
        manifest = _load_manifest()
        updated_manifest = dict(manifest)

        # ── 4. Download source ────────────────────────────────────────────────
        if download_missing and not dry_run:
            try:
                from pipeline.sources.youtube_music import YouTubeMusicSource
                from pipeline.fetcher.models        import TrackInfo
                downloader = YouTubeMusicSource()
            except ImportError as exc:
                log.warning("YouTubeMusicSource unavailable: %s — download disabled", exc)
                download_missing = False
                downloader = None
        else:
            downloader = None

        # ── 5. Process each playlist ──────────────────────────────────────────
        for pl_idx, pl in enumerate(playlists):
            progress(
                f"[{pl_idx + 1}/{len(playlists)}] {pl.name!r} ({pl.track_count} tracks)"
            )

            # Check if playlist changed since last sync
            cached_snapshot = manifest.get(pl.spotify_id, {}).get("snapshot_id", "")
            if cached_snapshot and cached_snapshot == pl.snapshot_id:
                progress(f"  → unchanged (snapshot match), skipping track fetch")
                # Still upsert to keep PlaylistStore fresh with existing paths
                cached_paths = manifest.get(pl.spotify_id, {}).get("paths", [])
                if cached_paths and not dry_run:
                    existing = store.by_spotify_id(pl.spotify_id)
                    if existing:
                        pid, created = store.upsert_spotify_playlist(
                            pl.spotify_id, pl.name, pl.owner, cached_paths
                        )
                        result.playlists_updated += 1
                continue

            # Fetch track list from Spotify
            tracks = user_client.get_playlist_tracks(pl.spotify_id)
            progress(f"  fetched {len(tracks)} tracks from API")

            # Per-playlist download directory
            pl_dir = self._dl_root / pl.spotify_id
            pl_dir.mkdir(parents=True, exist_ok=True)

            # Resolve paths for each track
            resolved_paths: list[str] = []

            for track in tracks:
                # Try to find it locally first
                local_path = local_index.find(track)

                if local_path:
                    resolved_paths.append(local_path)
                    result.tracks_matched += 1
                    continue

                # Not found locally — check if already downloaded in pl_dir
                existing_dl = self._find_in_dir(pl_dir, track)
                if existing_dl:
                    resolved_paths.append(str(existing_dl))
                    local_index._by_stem[track.safe_filename.lower()] = str(existing_dl)
                    result.tracks_matched += 1
                    continue

                # Need to download
                if not download_missing or dry_run:
                    result.tracks_skipped += 1
                    if dry_run:
                        progress(f"    [dry-run] would download: {track.safe_filename}")
                    continue

                # Download via yt-dlp
                progress(f"    ↓ {track.search_query}")
                try:
                    from pipeline.fetcher.models import TrackInfo
                    ti = TrackInfo(
                        name        = track.name,
                        artists     = track.artist,
                        album       = track.album,
                        spotify_url = f"https://open.spotify.com/track/{track.spotify_id}",
                        isrc        = track.isrc,
                        duration_ms = track.duration_ms,
                    )
                    dl_result = downloader.download(ti, pl_dir, fmt=self._fmt)
                    if dl_result.ok and dl_result.path:
                        resolved_paths.append(dl_result.path)
                        local_index._by_stem[track.safe_filename.lower()] = dl_result.path
                        if track.isrc:
                            local_index._by_isrc[track.isrc.upper()] = dl_result.path
                        _write_sidecar(Path(dl_result.path), track)
                        result.tracks_downloaded += 1
                    else:
                        log.warning("Download failed: %s — %s", track.search_query, dl_result.error)
                        result.tracks_failed += 1
                except Exception as exc:
                    log.error("Download error for %r: %s", track.search_query, exc)
                    result.tracks_failed += 1

                # Brief pause between downloads to be polite
                time.sleep(0.5)

            # ── Upsert into PlaylistStore ──────────────────────────────────────
            if resolved_paths and not dry_run:
                _pid, created = store.upsert_spotify_playlist(
                    pl.spotify_id, pl.name, pl.owner, resolved_paths
                )
                if created:
                    result.playlists_created += 1
                else:
                    result.playlists_updated += 1

            # Update manifest
            updated_manifest[pl.spotify_id] = {
                "name":        pl.name,
                "snapshot_id": pl.snapshot_id,
                "paths":       resolved_paths,
                "synced_at":   time.time(),
            }

        # ── 6. Save manifest ──────────────────────────────────────────────────
        if not dry_run:
            _save_manifest(updated_manifest)

        return result

    # ── helpers ───────────────────────────────────────────────────────────────

    def _find_in_dir(self, directory: Path, track) -> Optional[Path]:
        """Look for an already-downloaded file in *directory* matching *track*."""
        if not directory.exists():
            return None
        stem_lower = track.safe_filename.lower()
        for f in directory.iterdir():
            if f.suffix.lower() in _AUDIO_EXTS:
                if stem_lower in f.stem.lower() or f.stem.lower() in stem_lower:
                    return f
        return None


# ── CLI ───────────────────────────────────────────────────────────────────────

def _main(argv: list[str] | None = None) -> None:
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        prog="python -m phi.core.spotify_sync",
        description="Sync all Spotify playlists to the local phi library.",
    )
    parser.add_argument(
        "--no-download", action="store_true",
        help="Only scrape and import metadata; skip downloading missing tracks",
    )
    parser.add_argument(
        "--dry-run", "-n", action="store_true",
        help="Show what would be done without writing anything",
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Stop after N playlists (for testing)",
    )
    parser.add_argument(
        "--no-browser", action="store_true",
        help="Disable automatic browser open for OAuth (paste URL manually)",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    # Build library and store
    from phi.config import META_DB
    from phi.core.library       import Library
    from phi.core.playlist_store import PlaylistStore

    print("Loading library…")
    library = Library()
    try:
        import json as _json
        state_file = Path.home() / ".phi" / "state.json"
        if state_file.exists():
            state = _json.loads(state_file.read_text())
            for folder in state.get("folders", []):
                library.add_folder(folder)
    except Exception as exc:
        log.warning("Could not load library state: %s", exc)

    store = PlaylistStore(META_DB)

    # Build user client
    from phi.meta.spotify_user_client import build_user_client
    print("Authenticating with Spotify…")
    user_client = build_user_client(open_browser=not args.no_browser)
    if not user_client:
        print("ERROR: Spotify authentication failed.", file=sys.stderr)
        sys.exit(1)

    print(f"Authenticated as: {user_client.user_id}")

    # Run sync
    syncer = SpotifySync()
    result = syncer.run(
        library          = library,
        store            = store,
        download_missing = not args.no_download,
        dry_run          = args.dry_run,
        limit            = args.limit,
        on_progress      = print,
        user_client      = user_client,
    )

    print()
    print(result.summary())

    if result.errors:
        for e in result.errors:
            print(f"  ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    _main()
