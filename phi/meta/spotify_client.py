# -*- coding: utf-8 -*-
"""phi.meta.spotify_client — Spotify track search + audio features.

Uses the Client Credentials OAuth flow — no user login required.
Provides exact numerical audio features that replace the BPM-bucketing
heuristics used by EnergyModel and MoodModel.

Audio features returned per track
----------------------------------
acousticness    float  0–1  Confidence the track is acoustic
danceability    float  0–1  How suitable for dancing (rhythm + beat stability)
energy          float  0–1  Perceptual intensity (loud + fast → high energy)
instrumentalness float 0–1  Predicts absence of vocals (>0.5 = likely instrumental)
liveness        float  0–1  Detects live audience
loudness        float  dB   Typical range −60 to 0
mode            int    0/1  0 = minor, 1 = major
speechiness     float  0–1  Spoken-word content
tempo           float  BPM  Estimated tempo
time_signature  int    3–7  Beats per bar
valence         float  0–1  Musical positiveness (0 = sad/angry, 1 = euphoric)
key             int    0–11 Pitch class (0=C … 11=B), −1 if undetected

Mood mapping from valence + energy
-----------------------------------
valence ≥ 0.65 and energy ≥ 0.60  →  energetic
valence ≥ 0.65                     →  happy
valence < 0.25 and energy ≥ 0.60  →  angry
valence < 0.25                     →  sad
energy  < 0.30                     →  calm
energy  < 0.50                     →  chill
otherwise                          →  focused

Setup (phi_config.yaml)
-----------------------
spotify:
  client_id:     "YOUR_CLIENT_ID"
  client_secret: "YOUR_CLIENT_SECRET"

Get credentials at https://developer.spotify.com/dashboard (free).
"""
from __future__ import annotations

import functools
import threading
import time
from dataclasses import dataclass, field
from typing import Optional


# ── result dataclasses ────────────────────────────────────────────────────────

@dataclass
class AudioFeatures:
    """Spotify audio features for a single track."""
    acousticness:     float = 0.0
    danceability:     float = 0.0
    energy:           float = 0.0
    instrumentalness: float = 0.0
    liveness:         float = 0.0
    loudness:         float = -60.0
    mode:             int   = -1   # 0=minor, 1=major, -1=unknown
    speechiness:      float = 0.0
    tempo:            float = 0.0
    time_signature:   int   = 4
    valence:          float = 0.0
    key:              int   = -1   # 0=C … 11=B, -1=unknown

    # ── derived helpers ───────────────────────────────────────────────────────

    @property
    def mood_tag(self) -> str:
        """Map valence + energy to a discrete mood label."""
        v, e = self.valence, self.energy
        if v >= 0.65 and e >= 0.60:
            return "energetic"
        if v >= 0.65:
            return "happy"
        if v < 0.25 and e >= 0.60:
            return "angry"
        if v < 0.25:
            return "sad"
        if e < 0.30:
            return "calm"
        if e < 0.50:
            return "chill"
        return "focused"

    @property
    def key_str(self) -> str:
        """Return e.g. 'C major', 'F# minor', or '' if unknown."""
        if self.key < 0:
            return ""
        names  = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        quality = "major" if self.mode == 1 else ("minor" if self.mode == 0 else "")
        return f"{names[self.key]} {quality}".strip()

    def as_annotation_dict(self) -> dict:
        return {
            "spotify_acousticness":     self.acousticness,
            "spotify_danceability":     self.danceability,
            "spotify_energy":           self.energy,
            "spotify_instrumentalness": self.instrumentalness,
            "spotify_liveness":         self.liveness,
            "spotify_loudness":         self.loudness,
            "spotify_mode":             self.mode,
            "spotify_speechiness":      self.speechiness,
            "spotify_tempo":            self.tempo,
            "spotify_time_signature":   self.time_signature,
            "spotify_valence":          self.valence,
            "spotify_key":              self.key,
            "spotify_mood":             self.mood_tag,
            "spotify_key_str":          self.key_str,
            "spotify_enriched":         True,
        }


@dataclass
class SpotifyTrack:
    """Metadata for one Spotify track search result."""
    track_id:    str
    title:       str
    artist:      str
    album:       str
    isrc:        Optional[str]    = None
    popularity:  int              = 0     # 0–100
    preview_url: Optional[str]   = None
    art_url:     Optional[str]   = None
    art_bytes:   Optional[bytes] = None
    features:    Optional[AudioFeatures] = None

    def as_meta_dict(self) -> dict:
        d: dict = {
            "title":    self.title,
            "artist":   self.artist,
            "album":    self.album,
        }
        if self.isrc:
            d["isrc"] = self.isrc
        if self.art_bytes:
            d["art_bytes"] = self.art_bytes
        return d

    def as_annotation_dict(self) -> dict:
        d: dict = {
            "spotify_track_id":   self.track_id,
            "spotify_popularity": self.popularity,
            # Always mark enriched=True when a track was matched — even if audio
            # features are unavailable (403 on new apps post-Nov 2024).
            "spotify_enriched":   True,
        }
        if self.isrc:
            d["isrc"] = self.isrc
        if self.preview_url:
            d["preview_url"] = self.preview_url
        if self.features:
            d.update(self.features.as_annotation_dict())
        return d


# ── rate limiter ──────────────────────────────────────────────────────────────

class _RateLimiter:
    def __init__(self, max_per_sec: float = 10.0) -> None:
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


# ── SpotifyClient ─────────────────────────────────────────────────────────────

class SpotifyClient:
    """
    Thin wrapper around spotipy with rate limiting and graceful degradation.

    All methods return None / {} on failure — never raise.
    """

    # Minimum back-off after a 429/rate-limit response.  spotipy reports
    # "Retry-After: 0" which causes it to hammer immediately; we enforce a
    # floor so the process doesn't spin.
    _RATE_LIMIT_BACKOFF_S: float = 60.0

    def __init__(
        self,
        client_id:     str,
        client_secret: str,
        *,
        max_per_sec:   float = 5.0,
    ) -> None:
        self._limiter           = _RateLimiter(max_per_sec)
        self._sp                = None
        self._backoff_until:    float = 0.0   # monotonic; skip calls until this time
        # Tracks whether /audio-features/ is available. Spotify deprecated this
        # endpoint for apps created after Nov 2024 (returns 403). After the first
        # 403 we stop trying so we don't waste one API call per track.
        self._features_available: bool = True
        if client_id and client_secret:
            try:
                import spotipy
                from spotipy.oauth2 import SpotifyClientCredentials
                from phi.config import PHI_DIR
                PHI_DIR.mkdir(parents=True, exist_ok=True)
                _cache_path = str(PHI_DIR / "spotify_token.cache")
                # spotipy ≥2.23 replaced cache_path= with cache_handler=
                try:
                    from spotipy.cache_handler import CacheFileHandler
                    _handler = CacheFileHandler(cache_path=_cache_path)
                    auth = SpotifyClientCredentials(
                        client_id=client_id,
                        client_secret=client_secret,
                        cache_handler=_handler,
                    )
                except ImportError:
                    auth = SpotifyClientCredentials(
                        client_id=client_id,
                        client_secret=client_secret,
                        cache_path=_cache_path,
                    )
                self._sp = spotipy.Spotify(auth_manager=auth)
                # Do NOT call search() here — it blocks for hours when rate-limited.
                # Credentials are validated lazily on the first real search call.
            except Exception as exc:
                import logging as _log
                _log.getLogger(__name__).warning(
                    "Spotify credentials invalid or spotipy unavailable: %s", exc
                )
                self._sp = None

    @property
    def available(self) -> bool:
        return self._sp is not None

    def _in_backoff(self) -> bool:
        """Return True when we're inside a rate-limit back-off window."""
        return time.monotonic() < self._backoff_until

    def _set_backoff(self) -> None:
        """Set a 60-second backoff from now."""
        self._backoff_until = time.monotonic() + self._RATE_LIMIT_BACKOFF_S
        import logging as _log
        _log.getLogger(__name__).warning(
            "SpotifyClient: rate-limited — backing off for %.0fs",
            self._RATE_LIMIT_BACKOFF_S,
        )

    # ── public API ────────────────────────────────────────────────────────────

    def search_by_isrc(self, isrc: str) -> Optional[SpotifyTrack]:
        """
        Look up a track by its ISRC (exact match — most reliable search method).
        Returns the matched track or None.
        """
        if not self._sp or not isrc or self._in_backoff():
            return None
        self._limiter.wait()
        try:
            result = self._sp.search(q=f"isrc:{isrc}", type="track", limit=1)
            items  = result.get("tracks", {}).get("items", [])
            if not items:
                return None
            return self._parse_track(items[0])
        except Exception as exc:
            if "429" in str(exc) or "rate" in str(exc).lower():
                self._set_backoff()
            return None

    def enrich_track_by_isrc(self, isrc: str) -> Optional["SpotifyTrack"]:
        """
        ISRC-based enrichment path: precise match + audio features.
        Returns None if ISRC lookup fails.
        """
        track = self.search_by_isrc(isrc)
        if track is None:
            return None
        track.features = self.get_audio_features(track.track_id)
        if track.art_url:
            track.art_bytes = self._fetch_art(track.art_url)
        return track

    def search_track(
        self,
        title:  str,
        artist: str,
        *,
        album:  str = "",
    ) -> Optional[SpotifyTrack]:
        """
        Search Spotify for a track by title + artist.
        Returns the best match or None.
        """
        if not self._sp or not (title or artist) or self._in_backoff():
            return None

        # Build query: title + artist, optionally album
        parts = []
        if title:  parts.append(f'track:"{title}"')
        if artist: parts.append(f'artist:"{artist}"')
        if album:  parts.append(f'album:"{album}"')
        q = " ".join(parts)

        self._limiter.wait()
        try:
            result = self._sp.search(q=q, type="track", limit=1)
            items  = result.get("tracks", {}).get("items", [])
            if not items:
                # Retry with a looser query (no quotes) — skip if now in backoff
                if self._in_backoff():
                    return None
                q2 = " ".join(filter(None, [title, artist]))
                self._limiter.wait()
                result = self._sp.search(q=q2, type="track", limit=1)
                items  = result.get("tracks", {}).get("items", [])
            if not items:
                return None
            return self._parse_track(items[0])
        except Exception as exc:
            if "429" in str(exc) or "rate" in str(exc).lower():
                self._set_backoff()
            return None

    def get_audio_features(self, track_id: str) -> Optional[AudioFeatures]:
        """
        Fetch audio features for a track ID.

        Note: Spotify deprecated this endpoint for apps created after Nov 2024.
        On a 403 response the flag self._features_available is set to False so
        subsequent calls are skipped without hitting the API.
        """
        if not self._sp or not track_id or not self._features_available or self._in_backoff():
            return None
        self._limiter.wait()
        try:
            feats = self._sp.audio_features([track_id])
            if not feats or feats[0] is None:
                return None
            f = feats[0]
            return AudioFeatures(
                acousticness     = float(f.get("acousticness", 0)),
                danceability     = float(f.get("danceability", 0)),
                energy           = float(f.get("energy", 0)),
                instrumentalness = float(f.get("instrumentalness", 0)),
                liveness         = float(f.get("liveness", 0)),
                loudness         = float(f.get("loudness", -60)),
                mode             = int(f.get("mode", -1)),
                speechiness      = float(f.get("speechiness", 0)),
                tempo            = float(f.get("tempo", 0)),
                time_signature   = int(f.get("time_signature", 4)),
                valence          = float(f.get("valence", 0)),
                key              = int(f.get("key", -1)),
            )
        except Exception as exc:
            msg = str(exc)
            if "403" in msg:
                import logging as _log
                _log.getLogger(__name__).info(
                    "Spotify /audio-features/ returned 403 — "
                    "endpoint unavailable for new apps. Disabling for this session."
                )
                self._features_available = False
            elif "429" in msg or "rate" in msg.lower():
                self._set_backoff()
            return None

    def enrich_track(
        self,
        title:  str,
        artist: str,
        album:  str = "",
    ) -> Optional[SpotifyTrack]:
        """
        Combined search + audio features in one call.
        Returns None on any failure.
        """
        track = self.search_track(title, artist, album=album)
        if track is None:
            return None
        track.features = self.get_audio_features(track.track_id)
        if track.art_url:
            track.art_bytes = self._fetch_art(track.art_url)
        return track

    # ── private ───────────────────────────────────────────────────────────────

    def _parse_track(self, item: dict) -> SpotifyTrack:
        artists    = item.get("artists", [])
        artist_str = ", ".join(a["name"] for a in artists) if artists else ""
        album_obj  = item.get("album", {})

        # Album art — pick largest image
        images  = album_obj.get("images", [])
        art_url = images[0]["url"] if images else None

        # ISRC from external IDs
        ext_ids = item.get("external_ids", {})
        isrc    = ext_ids.get("isrc")

        return SpotifyTrack(
            track_id    = item.get("id", ""),
            title       = item.get("name", ""),
            artist      = artist_str,
            album       = album_obj.get("name", ""),
            isrc        = isrc,
            popularity  = int(item.get("popularity", 0)),
            preview_url = item.get("preview_url"),
            art_url     = art_url,
        )

    @staticmethod
    def _fetch_art(url: str, *, timeout: float = 6.0) -> Optional[bytes]:
        try:
            import requests
            resp = requests.get(url, timeout=timeout)
            if resp.status_code == 200 and resp.content:
                return resp.content
        except Exception:
            pass
        return None


# ── module-level factory ──────────────────────────────────────────────────────

def build_spotify_client() -> Optional[SpotifyClient]:
    """
    Build a SpotifyClient from phi_config.yaml credentials.
    Returns None if not configured or spotipy is unavailable.
    """
    try:
        from phi.config import load_phi_config
        cfg = load_phi_config().get("spotify", {})
        cid = cfg.get("client_id", "")
        sec = cfg.get("client_secret", "")
        if not (cid and sec):
            return None
        client = SpotifyClient(cid, sec)
        return client if client.available else None
    except Exception:
        return None
