# -*- coding: utf-8 -*-
"""phi.meta.deezer_client — Deezer track metadata (no auth required).

Uses the public Deezer API — no API key or OAuth needed.
Provides a BPM cross-reference, explicit flag, popularity rank, gain
offset (loudness normalisation target), and a 30-second preview URL.

Data returned per track
-----------------------
deezer_id       int     Deezer track ID
deezer_bpm      float   Deezer's own BPM estimate (cross-check against librosa)
deezer_gain     float   Gain offset in dB (Deezer's replay-gain-like value)
deezer_explicit bool    Explicit lyrics flag
deezer_rank     int     Popularity score (0 – ~1 000 000+; higher = more popular)
deezer_preview  str     URL to 30-second MP3 preview (may be None)
deezer_link     str     Canonical deezer.com track URL
deezer_enriched bool

Rate limit: 50 requests / 5 s (public API).  The internal rate limiter
targets 8 req/s (≈ 40 / 5s) to stay safely under the cap.

No setup needed.  No phi_config.yaml entry required.
"""
from __future__ import annotations

import json
import threading
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Optional


_API_BASE = "https://api.deezer.com"
_UA       = "phi/1.0 (local music player)"
_TIMEOUT  = 8


# ── result dataclass ──────────────────────────────────────────────────────────

@dataclass
class DeezerTrack:
    deezer_id: int
    bpm:       float         = 0.0
    gain:      float         = 0.0
    explicit:  bool          = False
    rank:      int           = 0
    preview:   Optional[str] = None
    link:      Optional[str] = None

    def as_annotation_dict(self) -> dict:
        d: dict = {
            "deezer_id":       self.deezer_id,
            "deezer_bpm":      self.bpm,
            "deezer_gain":     self.gain,
            "deezer_explicit": self.explicit,
            "deezer_rank":     self.rank,
            "deezer_enriched": True,
        }
        if self.preview:
            d["deezer_preview"] = self.preview
        if self.link:
            d["deezer_link"]    = self.link
        return d


# ── rate limiter ──────────────────────────────────────────────────────────────

class _RateLimiter:
    def __init__(self, max_per_sec: float = 8.0) -> None:
        self._interval = 1.0 / max_per_sec
        self._last     = 0.0
        self._lock     = threading.Lock()

    def wait(self) -> None:
        with self._lock:
            now  = time.monotonic()
            wait = self._interval - (now - self._last)
            if wait > 0:
                threading.Event().wait(wait)
            self._last = time.monotonic()


# ── DeezerClient ─────────────────────────────────────────────────────────────

class DeezerClient:
    """
    Thin Deezer API wrapper.  All methods return None on failure — never raise.
    """

    def __init__(self, *, max_per_sec: float = 8.0) -> None:
        self._limiter = _RateLimiter(max_per_sec)

    # ── public API ────────────────────────────────────────────────────────────

    def search_track(
        self,
        title:  str,
        artist: str,
    ) -> Optional[DeezerTrack]:
        """
        Search Deezer for *title* + *artist*.
        Returns the top result or None.
        """
        if not (title or artist):
            return None

        q = " ".join(filter(None, [
            f'track:"{title}"'  if title  else "",
            f'artist:"{artist}"' if artist else "",
        ]))

        self._limiter.wait()
        data = self._get("/search/track", {"q": q, "limit": "5"})
        if not data:
            return None

        items = data.get("data") or []
        if not items:
            # Fallback: loose query without field qualifiers
            self._limiter.wait()
            data = self._get("/search/track", {
                "q": f"{artist} {title}".strip(),
                "limit": "5",
            })
            items = (data or {}).get("data") or []

        if not items:
            return None

        # Pick the best match: prefer exact title match, then highest rank
        def _score(item: dict) -> tuple:
            t_match = (item.get("title") or "").lower() == title.lower()
            return (t_match, item.get("rank", 0))

        items.sort(key=_score, reverse=True)
        return self._parse_track(items[0])

    # ── private ───────────────────────────────────────────────────────────────

    def _get(self, path: str, params: dict) -> Optional[dict]:
        self._limiter.wait()
        try:
            qs  = urllib.parse.urlencode(params) if params else ""
            url = _API_BASE + path + (f"?{qs}" if qs else "")
            req = urllib.request.Request(url, headers={"User-Agent": _UA})
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                return json.loads(resp.read().decode("utf-8", errors="replace"))
        except Exception:
            return None

    def fetch_album_art_bytes(
        self,
        title:  str,
        artist: str,
        *,
        size: str = "cover_medium",
    ) -> Optional[bytes]:
        """
        Search Deezer for *title* + *artist* and return the album cover as raw
        JPEG bytes, or None if not found / any error.

        *size* selects the Deezer cover field:
            "cover_small"  — 56 × 56
            "cover_medium" — 250 × 250  (default)
            "cover_big"    — 500 × 500
            "cover_xl"     — 1000 × 1000
        """
        self._limiter.wait()
        q = " ".join(filter(None, [
            f'track:"{title}"'  if title  else "",
            f'artist:"{artist}"' if artist else "",
        ]))
        data = self._get("/search/track", {"q": q, "limit": "3"})
        items = (data or {}).get("data") or []
        if not items:
            self._limiter.wait()
            data = self._get("/search/track", {"q": f"{artist} {title}".strip(), "limit": "3"})
            items = (data or {}).get("data") or []
        if not items:
            return None

        cover_url = (items[0].get("album") or {}).get(size) or None
        if not cover_url:
            return None

        try:
            req = urllib.request.Request(cover_url, headers={"User-Agent": _UA})
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                return resp.read()
        except Exception:
            return None

    def _parse_track(self, item: dict) -> DeezerTrack:
        return DeezerTrack(
            deezer_id = int(item.get("id", 0)),
            bpm       = float(item.get("bpm") or 0.0),
            gain      = float(item.get("gain") or 0.0),
            explicit  = bool(item.get("explicit_lyrics") or False),
            rank      = int(item.get("rank") or 0),
            preview   = item.get("preview") or None,
            link      = item.get("link") or None,
        )


# ── module-level singleton ────────────────────────────────────────────────────

_client: Optional[DeezerClient] = None
_client_lock = threading.Lock()


def get_deezer_client() -> DeezerClient:
    """Return the shared DeezerClient (created once, thread-safe)."""
    global _client
    with _client_lock:
        if _client is None:
            _client = DeezerClient()
    return _client
