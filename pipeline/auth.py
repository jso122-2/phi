"""
pipeline.auth — Spotify OAuth with DNS-transient retry.

Key design (2026-07-16):
    Mullvad relay switching kills system DNS for ~2-5s.  Any network call
    during that window throws socket.gaierror.  _retry_network() wraps
    every outbound call with 6×5s retries specifically for that failure mode.

Public API
----------
    get_spotify_client() -> spotipy.Spotify
        Main entry point.  Reads credentials from .env, caches token to
        .cache/spotify_token.  Subsequent runs skip the browser entirely.
"""
from __future__ import annotations

import http.server
import os
import socket
import threading
import time
import urllib.parse
import webbrowser
from pathlib import Path
from typing import Callable, Optional, TypeVar

# spotipy is a pipeline dependency — not in the mamba env for the vault workspace,
# so we import lazily to allow importing this module in test environments.
try:
    import spotipy
    from spotipy.oauth2 import SpotifyOAuth
    _SPOTIPY_AVAILABLE = True
except ImportError:
    _SPOTIPY_AVAILABLE = False

_T = TypeVar("_T")

# ── constants ──────────────────────────────────────────────────────────────────
_SCOPES = ",".join([
    "user-library-read",
    "playlist-read-private",
    "playlist-read-collaborative",
    "user-follow-read",
])
_AUTH_TIMEOUT: int = 120          # seconds to wait for browser OAuth
_TOKEN_CACHE: Path = Path(".cache/spotify_token")

_RETRY_COUNT: int = 6             # DNS warmup: 6 attempts
_RETRY_DELAY: float = 5.0         # 5s between attempts (matches Mullvad relay settle time)
_DNS_ERRORS: tuple[type[OSError], ...] = (socket.gaierror, ConnectionRefusedError)


# ── DNS-transient retry ────────────────────────────────────────────────────────
def _retry_network(fn: Callable[[], _T], *, retries: int = _RETRY_COUNT, delay: float = _RETRY_DELAY) -> _T:
    """
    Wrap a network call with retry logic for DNS transients.

    Mullvad relay switching kills system DNS while rerouting (typically 2-5s).
    socket.gaierror is thrown during that window.  This wrapper retries up to
    `retries` times with `delay` seconds between attempts before re-raising.

    Parameters
    ----------
    fn      : zero-argument callable that performs the network call
    retries : maximum number of retry attempts (default 6)
    delay   : seconds to wait between retries (default 5.0)

    Raises
    ------
    socket.gaierror  if all retries are exhausted
    Any other exception from fn() is re-raised immediately without retry.
    """
    last_exc: Optional[Exception] = None
    for attempt in range(retries + 1):
        try:
            return fn()
        except _DNS_ERRORS as exc:
            last_exc = exc
            if attempt < retries:
                time.sleep(delay)
        # Non-DNS errors propagate immediately
    raise last_exc  # type: ignore[misc]


# ── internal OAuth helpers ─────────────────────────────────────────────────────
def _parse_redirect_uri(uri: str) -> tuple[str, int, str]:
    """
    Extract (host, port, path) from a redirect URI.

    Parameters
    ----------
    uri : e.g. 'http://localhost:8888/callback'

    Returns
    -------
    (host, port, path) — e.g. ('localhost', 8888, '/callback')
    """
    parsed = urllib.parse.urlparse(uri)
    host = parsed.hostname or "localhost"
    port = parsed.port or 8888
    path = parsed.path or "/callback"
    return host, port, path


class _OAuthCallbackHandler(http.server.BaseHTTPRequestHandler):
    """Minimal HTTP handler that captures the ?code= query parameter."""

    code: Optional[str] = None

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        if "code" in params:
            _OAuthCallbackHandler.code = params["code"][0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"<html><body><h2>Spotify auth complete. You can close this tab.</h2></body></html>")
        else:
            self.send_response(400)
            self.end_headers()

    def log_message(self, *_args: object) -> None:  # silence access log
        pass


class _ReuseAddrServer(http.server.HTTPServer):
    allow_reuse_address = True


def _wait_for_code(server: _ReuseAddrServer, timeout: int) -> str:
    """
    Poll the local server until the OAuth ?code= arrives or timeout.

    Parameters
    ----------
    server  : already-bound HTTPServer
    timeout : seconds to wait

    Returns
    -------
    str — the OAuth code

    Raises
    ------
    TimeoutError if the code doesn't arrive within `timeout` seconds
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        server.handle_request()
        if _OAuthCallbackHandler.code is not None:
            return _OAuthCallbackHandler.code
        time.sleep(0.2)
    raise TimeoutError(f"Spotify OAuth code not received within {timeout}s")


# ── public API ─────────────────────────────────────────────────────────────────
def get_spotify_client() -> "spotipy.Spotify":
    """
    Build and return an authenticated spotipy.Spotify instance.

    Flow
    ----
    1. Read SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI from env
       (loaded from .env by the caller or by run.py).
    2. If a cached token exists at .cache/spotify_token, use it (silent refresh).
    3. Otherwise: start local callback server → open browser → wait for code
       → exchange for token → cache.

    All outbound network calls are wrapped with _retry_network() to survive
    Mullvad DNS kills during relay switching.

    Returns
    -------
    spotipy.Spotify — authenticated, ready to call the API

    Raises
    ------
    RuntimeError  if spotipy is not installed
    EnvironmentError  if SPOTIFY_CLIENT_ID or SPOTIFY_CLIENT_SECRET is missing
    """
    if not _SPOTIPY_AVAILABLE:
        raise RuntimeError(
            "spotipy is not installed — run: pip install spotipy"
        )

    client_id = os.environ.get("SPOTIFY_CLIENT_ID", "")
    client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET", "")
    redirect_uri = os.environ.get("SPOTIFY_REDIRECT_URI", "http://localhost:8888/callback")

    if not client_id or not client_secret:
        raise EnvironmentError(
            "SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET must be set in .env"
        )

    _TOKEN_CACHE.parent.mkdir(parents=True, exist_ok=True)

    auth_manager = SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope=_SCOPES,
        cache_path=str(_TOKEN_CACHE),
        open_browser=False,
    )

    # Try silent token refresh first (cached token path)
    cached = _retry_network(lambda: auth_manager.get_cached_token())
    if cached and not auth_manager.is_token_expired(cached):
        return spotipy.Spotify(auth_manager=auth_manager)

    # Full browser flow
    host, port, path = _parse_redirect_uri(redirect_uri)
    _OAuthCallbackHandler.code = None
    server = _ReuseAddrServer((host, port), _OAuthCallbackHandler)

    auth_url = auth_manager.get_authorize_url()
    webbrowser.open(auth_url)

    try:
        _wait_for_code(server, timeout=_AUTH_TIMEOUT)
    finally:
        server.server_close()

    code = _OAuthCallbackHandler.code
    if code is None:
        raise RuntimeError("OAuth flow completed but no code was captured")

    _retry_network(lambda: auth_manager.get_access_token(code, as_dict=False))
    return spotipy.Spotify(auth_manager=auth_manager)
