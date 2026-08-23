# -*- coding: utf-8 -*-
"""phi.meta.spotify_user_client — Spotify user-authenticated client.

The Client Credentials flow (used by SpotifyClient) can only access public
Spotify data.  To read the user's private playlists and liked songs we need
the Authorization Code flow — this module provides it.

OAuth setup
-----------
    client_id / client_secret : from phi_config.yaml spotify section
    redirect_uri              : http://localhost:8888/callback
    scope                     : playlist-read-private
                                playlist-read-collaborative
                                user-library-read
    token cache               : ~/.phi/spotify_user_token.cache

First run opens a browser; the user approves the app and is redirected back.
spotipy handles the local HTTP server automatically.
Subsequent runs reuse the cached token (auto-refreshed when expired).

Usage
-----
    from phi.meta.spotify_user_client import build_user_client

    client = build_user_client()   # may open a browser on first use
    if not client:
        # credentials not configured
        ...

    for pl in client.get_all_playlists():
        print(pl.name, pl.track_count)
        for track in client.get_playlist_tracks(pl.spotify_id):
            print(" ", track.name, track.artist)

CLI
---
    python -m phi.meta.spotify_user_client          # list all playlists
    python -m phi.meta.spotify_user_client --tracks # include track lists
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

_REDIRECT_URI        = "http://localhost:8888/callback"
_REDIRECT_URI_FALLBACK = "http://localhost:8889/callback"
_SCOPE          = (
    "playlist-read-private "
    "playlist-read-collaborative "
    "user-library-read"
)
_PAGE_SIZE      = 50   # Spotify max items per page


# ── result dataclasses ────────────────────────────────────────────────────────

@dataclass
class SpotifyPlaylistMeta:
    """Lightweight snapshot of a Spotify playlist header."""
    spotify_id:  str
    name:        str
    owner:       str
    track_count: int
    is_public:   bool
    description: str = ""
    snapshot_id: str = ""   # Spotify version token — changes when playlist changes


@dataclass
class SpotifyTrackMeta:
    """Minimal metadata for one track in a Spotify playlist."""
    spotify_id:  str
    name:        str
    artist:      str            # comma-joined artist names
    album:       str
    isrc:        str = ""
    duration_ms: int = 0
    added_at:    str = ""       # ISO-8601 timestamp
    track_number: int = 0

    @property
    def search_query(self) -> str:
        """'Artist - Title' for YouTube Music search."""
        return f"{self.artist} - {self.name}"

    @property
    def safe_filename(self) -> str:
        """Filesystem-safe 'Artist - Title' stem."""
        def _c(s: str) -> str:
            for ch in r'/\:*?"<>|':
                s = s.replace(ch, "_")
            return s.strip()
        return f"{_c(self.artist)} - {_c(self.name)}"


# ── rate limiter ──────────────────────────────────────────────────────────────

class _RateLimiter:
    def __init__(self, max_per_sec: float = 5.0) -> None:
        self._interval = 1.0 / max_per_sec
        self._last     = 0.0

    def wait(self) -> None:
        now  = time.monotonic()
        gap  = self._interval - (now - self._last)
        if gap > 0:
            time.sleep(gap)
        self._last = time.monotonic()


# ── SpotifyUserClient ─────────────────────────────────────────────────────────

class SpotifyUserClient:
    """
    Spotify user-authenticated client.

    Wraps spotipy with rate limiting and graceful error handling.
    All methods return empty lists on failure — never raise.

    Parameters
    ----------
    client_id     : Spotify app client_id
    client_secret : Spotify app client_secret
    cache_path    : where to store the OAuth token (default ~/.phi/spotify_user_token.cache)
    max_per_sec   : API call rate limit (default 5 req/s)
    open_browser  : if True (default), open a browser for user consent on first auth
    """

    _RATE_LIMIT_BACKOFF_S: float = 60.0

    def __init__(
        self,
        client_id:     str,
        client_secret: str,
        *,
        cache_path:    Optional[Path] = None,
        redirect_uri:  str            = "",
        max_per_sec:   float          = 5.0,
        open_browser:  bool           = True,
    ) -> None:
        self._limiter          = _RateLimiter(max_per_sec)
        self._sp               = None
        self._backoff_until:   float = 0.0

        if not cache_path:
            from phi.config import PHI_DIR
            cache_path = PHI_DIR / "spotify_user_token.cache"

        self._auth_error: str = ""   # human-readable auth failure reason

        if client_id and client_secret:
            try:
                import socket as _socket
                import spotipy
                from spotipy.oauth2 import SpotifyOAuth
                from spotipy.cache_handler import CacheFileHandler
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                handler = CacheFileHandler(cache_path=str(cache_path))

                # Auto-detect if the preferred port is already occupied and fall back.
                preferred_uri = redirect_uri or _REDIRECT_URI
                effective_uri = preferred_uri
                try:
                    _port = int(preferred_uri.split(":")[2].split("/")[0])
                    with _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM) as _s:
                        if _s.connect_ex(("localhost", _port)) == 0:
                            # Port in use — try fallback
                            effective_uri = _REDIRECT_URI_FALLBACK
                            log.warning(
                                "Port %d is in use — trying fallback redirect URI %s",
                                _port, effective_uri,
                            )
                except Exception:
                    pass

                auth = SpotifyOAuth(
                    client_id      = client_id,
                    client_secret  = client_secret,
                    redirect_uri   = effective_uri,
                    scope          = _SCOPE,
                    cache_handler  = handler,
                    open_browser   = open_browser,
                    show_dialog    = False,
                )
                self._sp = spotipy.Spotify(auth_manager=auth)
                # Validate eagerly by fetching the current user profile
                me = self._sp.current_user()
                self._user_id = me.get("id", "")
                log.info("SpotifyUserClient: authenticated as %r", self._user_id)
            except Exception as exc:
                msg = str(exc)
                if "Invalid redirect URI" in msg or "redirect_uri" in msg.lower():
                    self._auth_error = (
                        "Redirect URI not registered in Spotify dashboard.\n"
                        "Go to developer.spotify.com/dashboard → your app → Edit → "
                        "Redirect URIs → add:\n"
                        f"  {_REDIRECT_URI}"
                    )
                elif "Invalid client" in msg or "client_id" in msg.lower():
                    self._auth_error = (
                        "Invalid Spotify credentials. Check client_id and client_secret "
                        "in phi_config.yaml."
                    )
                else:
                    self._auth_error = f"Spotify auth failed: {exc}"
                log.warning("SpotifyUserClient: %s", self._auth_error)
                self._sp = None
                self._user_id = ""

    @property
    def available(self) -> bool:
        return self._sp is not None

    @property
    def user_id(self) -> str:
        return getattr(self, "_user_id", "")

    # ── playlist listing ──────────────────────────────────────────────────────

    def get_all_playlists(self) -> list[SpotifyPlaylistMeta]:
        """
        Return ALL playlists in the user's library (owned + followed), paginated.

        Returns an empty list on any error.
        """
        if not self._sp:
            return []
        results: list[SpotifyPlaylistMeta] = []
        offset = 0
        while True:
            if self._in_backoff():
                time.sleep(2)
                continue
            self._limiter.wait()
            try:
                page = self._sp.current_user_playlists(limit=_PAGE_SIZE, offset=offset)
            except Exception as exc:
                self._handle_exc(exc, "get_all_playlists")
                break

            items = page.get("items") or []
            for item in items:
                if item is None:
                    continue
                owner   = (item.get("owner") or {}).get("id", "")
                tracks  = (item.get("tracks") or {}).get("total", 0)
                results.append(SpotifyPlaylistMeta(
                    spotify_id  = item.get("id", ""),
                    name        = item.get("name", "Untitled"),
                    owner       = owner,
                    track_count = tracks,
                    is_public   = bool(item.get("public")),
                    description = item.get("description", ""),
                    snapshot_id = item.get("snapshot_id", ""),
                ))

            offset += len(items)
            if not page.get("next"):
                break

        log.info("SpotifyUserClient: fetched %d playlists", len(results))
        return results

    # ── track listing ─────────────────────────────────────────────────────────

    def get_playlist_tracks(self, playlist_id: str) -> list[SpotifyTrackMeta]:
        """
        Return all tracks in *playlist_id*, fully paginated.

        Skips local / podcast episodes and null items.
        """
        if not self._sp or not playlist_id:
            return []
        results: list[SpotifyTrackMeta] = []
        offset = 0
        while True:
            if self._in_backoff():
                time.sleep(2)
                continue
            self._limiter.wait()
            try:
                page = self._sp.playlist_tracks(
                    playlist_id,
                    limit  = _PAGE_SIZE,
                    offset = offset,
                    fields = (
                        "items(added_at,track(id,name,artists,album,external_ids,"
                        "duration_ms,track_number,is_local)),next"
                    ),
                )
            except Exception as exc:
                self._handle_exc(exc, f"get_playlist_tracks({playlist_id})")
                break

            items = page.get("items") or []
            for item in items:
                if item is None:
                    continue
                track = item.get("track")
                if not track or track.get("is_local"):
                    continue
                tid = track.get("id") or ""
                if not tid:
                    continue

                artists   = track.get("artists") or []
                artist_s  = ", ".join(a["name"] for a in artists if a.get("name"))
                album     = (track.get("album") or {}).get("name", "")
                ext_ids   = track.get("external_ids") or {}
                isrc      = ext_ids.get("isrc", "")

                results.append(SpotifyTrackMeta(
                    spotify_id   = tid,
                    name         = track.get("name", ""),
                    artist       = artist_s,
                    album        = album,
                    isrc         = isrc,
                    duration_ms  = int(track.get("duration_ms") or 0),
                    added_at     = item.get("added_at", ""),
                    track_number = int(track.get("track_number") or 0),
                ))

            offset += len(items)
            if not page.get("next"):
                break

        return results

    def get_liked_songs(self) -> list[SpotifyTrackMeta]:
        """Return all tracks in the user's Liked Songs library, paginated."""
        if not self._sp:
            return []
        results: list[SpotifyTrackMeta] = []
        offset = 0
        while True:
            if self._in_backoff():
                time.sleep(2)
                continue
            self._limiter.wait()
            try:
                page = self._sp.current_user_saved_tracks(
                    limit=_PAGE_SIZE, offset=offset
                )
            except Exception as exc:
                self._handle_exc(exc, "get_liked_songs")
                break

            items = page.get("items") or []
            for item in items:
                if item is None:
                    continue
                track = item.get("track")
                if not track:
                    continue
                tid = track.get("id") or ""
                if not tid:
                    continue
                artists  = track.get("artists") or []
                artist_s = ", ".join(a["name"] for a in artists if a.get("name"))
                album    = (track.get("album") or {}).get("name", "")
                ext_ids  = track.get("external_ids") or {}
                results.append(SpotifyTrackMeta(
                    spotify_id  = tid,
                    name        = track.get("name", ""),
                    artist      = artist_s,
                    album       = album,
                    isrc        = ext_ids.get("isrc", ""),
                    duration_ms = int(track.get("duration_ms") or 0),
                    added_at    = item.get("added_at", ""),
                ))

            offset += len(items)
            if not page.get("next"):
                break

        log.info("SpotifyUserClient: fetched %d liked songs", len(results))
        return results

    # ── private ───────────────────────────────────────────────────────────────

    def _in_backoff(self) -> bool:
        return time.monotonic() < self._backoff_until

    def _handle_exc(self, exc: Exception, context: str) -> None:
        msg = str(exc)
        if "429" in msg or "rate" in msg.lower():
            self._backoff_until = time.monotonic() + self._RATE_LIMIT_BACKOFF_S
            log.warning("SpotifyUserClient rate-limited in %s — backing off", context)
        else:
            log.error("SpotifyUserClient error in %s: %s", context, exc)


# ── factory ───────────────────────────────────────────────────────────────────

def build_user_client(
    *,
    open_browser: bool = True,
    cache_path:   Optional[Path] = None,
) -> Optional[SpotifyUserClient]:
    """
    Build a SpotifyUserClient from phi_config.yaml credentials.

    Returns None if not configured or spotipy is unavailable.
    On first use, opens a browser for the user to approve access.
    Subsequent calls reuse the cached token.

    Required setup (one-time):
      1. Go to developer.spotify.com/dashboard → your app → Edit
      2. Add to Redirect URIs: the value of spotify.redirect_uri in phi_config.yaml
         (default: http://localhost:8888/callback)
      3. Save and restart phi.
    """
    try:
        from phi.config import load_phi_config
        cfg = load_phi_config().get("spotify", {})
        cid = cfg.get("client_id", "").strip()
        sec = cfg.get("client_secret", "").strip()
        if not (cid and sec):
            log.warning(
                "build_user_client: spotify.client_id/client_secret not set in phi_config.yaml"
            )
            return None
        # Allow overriding the redirect URI via config (useful when the port is taken)
        redirect_uri = cfg.get("redirect_uri", "").strip() or _REDIRECT_URI
        client = SpotifyUserClient(
            cid, sec,
            redirect_uri=redirect_uri,
            open_browser=open_browser,
            cache_path=cache_path,
        )
        return client  # return even if not available so caller can read _auth_error
    except Exception as exc:
        log.error("build_user_client: %s", exc)
        return None


# ── CLI entry point ───────────────────────────────────────────────────────────

def _main(argv: list[str] | None = None) -> None:
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        prog="python -m phi.meta.spotify_user_client",
        description="List the authenticated user's Spotify playlists.",
    )
    parser.add_argument(
        "--tracks", action="store_true",
        help="Also list tracks for each playlist (slower)",
    )
    parser.add_argument(
        "--no-browser", action="store_true",
        help="Disable automatic browser open (paste URL manually)",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.WARNING, format="%(message)s")

    client = build_user_client(open_browser=not args.no_browser)
    if client is None:
        print("ERROR: Spotify user client unavailable.", file=sys.stderr)
        print(
            "  Check phi_config.yaml has spotify.client_id and spotify.client_secret.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Authenticated as: {client.user_id}\n")
    playlists = client.get_all_playlists()
    print(f"Found {len(playlists)} playlists:\n")

    for pl in playlists:
        pub = "public" if pl.is_public else "private"
        print(f"  {pl.name!r}  [{pl.spotify_id}]  {pl.track_count} tracks  {pub}")

        if args.tracks:
            tracks = client.get_playlist_tracks(pl.spotify_id)
            for t in tracks[:5]:
                print(f"      {t.artist} — {t.name}  ({t.duration_ms // 1000}s)")
            if len(tracks) > 5:
                print(f"      … +{len(tracks) - 5} more")


if __name__ == "__main__":
    _main()
