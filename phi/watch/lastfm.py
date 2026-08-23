# -*- coding: utf-8 -*-
"""phi.watch.lastfm — Last.fm scrobbling.

Implements the Last.fm Scrobbling API v2.0 via plain urllib (no extra deps).

Scrobble rules (per Last.fm spec):
  · Track must have been playing for > 30 seconds  AND
  · Track must be > 240 seconds long  OR  > 50% complete

Usage
-----
    scrobbler = LastFmScrobbler(api_key, api_secret, session_key)
    scrobbler.now_playing(title, artist, album, duration)
    scrobbler.scrobble(title, artist, album, duration, timestamp)

First-launch auth (opens browser):
    url, token = LastFmScrobbler.get_auth_url(api_key)
    # user clicks Authorize in their browser
    session_key = LastFmScrobbler.get_session(api_key, api_secret, token)

Credentials are stored in ~/.phi/lastfm.json so the auth flow
only runs once.
"""
from __future__ import annotations

import hashlib
import json
import time
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path
from typing import Callable

_API_URL   = "https://ws.audioscrobbler.com/2.0/"
_AUTH_URL  = "https://www.last.fm/api/auth/"
_CREDS     = Path.home() / ".phi" / "lastfm.json"
_TIMEOUT   = 6


# ── low-level signing ─────────────────────────────────────────────────────────

def _sign(params: dict[str, str], secret: str) -> str:
    """HMAC-MD5 method signature as specified by Last.fm API."""
    keys = sorted(k for k in params if k != "format")
    raw  = "".join(k + params[k] for k in keys) + secret
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def _call(method: str, params: dict[str, str], secret: str | None) -> dict:
    """Make a signed POST call to the Last.fm API."""
    p: dict[str, str] = {"method": method, "format": "json", **params}
    if secret:
        p["api_sig"] = _sign(p, secret)
    body = urllib.parse.urlencode(p).encode()
    req  = urllib.request.Request(
        _API_URL, data=body,
        headers={"User-Agent": "phi/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return {}


# ── auth helpers ──────────────────────────────────────────────────────────────

def get_auth_url(api_key: str) -> tuple[str, str]:
    """
    Generate a Last.fm auth URL and return (url, token).

    The user visits the URL, clicks Authorize, then call get_session().
    """
    # Step 1: get a request token
    data = _call("auth.getToken", {"api_key": api_key}, None)
    token = data.get("token", "")
    url   = f"{_AUTH_URL}?api_key={api_key}&token={token}"
    return url, token


def get_session(api_key: str, api_secret: str, token: str) -> str:
    """Exchange an authorized token for a persistent session key."""
    data = _call(
        "auth.getSession",
        {"api_key": api_key, "token": token},
        api_secret,
    )
    return (data.get("session") or {}).get("key", "")


# ── Scrobbler class ───────────────────────────────────────────────────────────

class LastFmScrobbler:
    """
    Thread-safe Last.fm scrobbler.

    All network calls are fire-and-forget (non-blocking).
    Failures are silently swallowed — scrobbling should never crash phi.
    """

    def __init__(
        self,
        api_key:     str,
        api_secret:  str,
        session_key: str,
        schedule:    Callable,   # Tk root.after for deferred calls
    ) -> None:
        self._key     = api_key
        self._secret  = api_secret
        self._sk      = session_key
        self._schedule = schedule
        self._enabled  = bool(api_key and api_secret and session_key)

    # ── public ────────────────────────────────────────────────────────────────

    @property
    def enabled(self) -> bool:
        return self._enabled

    def now_playing(
        self,
        title:    str,
        artist:   str,
        album:    str = "",
        duration: float = 0.0,
    ) -> None:
        """Update Last.fm "Now Scrobbling" (non-blocking, best-effort)."""
        if not self._enabled or not (title or artist):
            return
        import threading
        threading.Thread(
            target=self._np,
            args=(title, artist, album, duration),
            daemon=True,
        ).start()

    def scrobble(
        self,
        title:     str,
        artist:    str,
        album:     str   = "",
        duration:  float = 0.0,
        timestamp: int | None = None,
    ) -> None:
        """Submit a scrobble (non-blocking, best-effort)."""
        if not self._enabled or not (title or artist):
            return
        ts = timestamp or int(time.time())
        import threading
        threading.Thread(
            target=self._sc,
            args=(title, artist, album, duration, ts),
            daemon=True,
        ).start()

    def should_scrobble(self, elapsed: float, duration: float) -> bool:
        """
        Return True if the track qualifies for scrobbling under Last.fm rules:
        · Played > 30 seconds
        · Played > 240 s  OR  > 50% of duration
        """
        return (
            elapsed >= 30
            and (elapsed >= 240 or (duration > 0 and elapsed / duration >= 0.5))
        )

    # ── private (runs on background threads) ─────────────────────────────────

    def _np(self, title: str, artist: str, album: str, duration: float) -> None:
        params: dict[str, str] = {
            "api_key":     self._key,
            "sk":          self._sk,
            "track":       title,
            "artist":      artist,
        }
        if album:    params["album"]    = album
        if duration: params["duration"] = str(int(duration))
        _call("track.updateNowPlaying", params, self._secret)

    def _sc(
        self, title: str, artist: str, album: str,
        duration: float, ts: int,
    ) -> None:
        params: dict[str, str] = {
            "api_key":   self._key,
            "sk":        self._sk,
            "track":     title,
            "artist":    artist,
            "timestamp": str(ts),
        }
        if album:    params["album"]    = album
        if duration: params["duration"] = str(int(duration))
        _call("track.scrobble", params, self._secret)


# ── credential helpers ────────────────────────────────────────────────────────

def load_creds() -> dict:
    """Load stored credentials from ~/.phi/lastfm.json."""
    try:
        return json.loads(_CREDS.read_text())
    except Exception:
        return {}


def save_creds(api_key: str, api_secret: str, session_key: str) -> None:
    """Persist credentials to ~/.phi/lastfm.json."""
    _CREDS.parent.mkdir(parents=True, exist_ok=True)
    _CREDS.write_text(
        json.dumps(
            {"api_key": api_key, "api_secret": api_secret, "session_key": session_key},
            indent=2,
        )
    )


def build_scrobbler(schedule: Callable) -> LastFmScrobbler | None:
    """
    Load persisted credentials and return a ready LastFmScrobbler.
    Returns None if credentials are not configured.
    """
    creds = load_creds()
    if not creds.get("session_key"):
        return None
    return LastFmScrobbler(
        api_key     = creds.get("api_key", ""),
        api_secret  = creds.get("api_secret", ""),
        session_key = creds.get("session_key", ""),
        schedule    = schedule,
    )
