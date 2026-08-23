# -*- coding: utf-8 -*-
"""phi.meta.discogs_client — Discogs release metadata.

Fetches pressing info, community market data, styles, and production credits
that are not available from MusicBrainz or Spotify.

Data returned per release
--------------------------
year              int     Release year (this pressing)
master_year       int     Original release year (from master resource, if found)
country           str     Release country (e.g. "US", "UK", "Europe")
format            str     Primary format: "Vinyl", "CD", "Digital", "Cassette", …
format_details    list    Sub-descriptions: ["LP", "Album", "Stereo", "180g"]
genres            list    Broad genre list: ["Electronic", "Rock"]
styles            list    Specific style list: ["House", "Techno", "Acid"]
community_rating  float   Community average rating 0.0–5.0
community_count   int     Number of community ratings
have              int     Count of Discogs users who own this release
want              int     Count of Discogs users who want this release
desirability      float   want / (have + want + 1)  — 1.0 = highly sought
credits           dict    Role → [name, …] mapping.
                          Common roles include: producer, engineer,
                          "mastering engineer", "mixed by", "written-by",
                          "composed by", artwork
label             str     First label name
catno             str     Catalog number
notes             str     Release notes (capped at 500 chars)
discogs_release_id int    Discogs release ID
discogs_master_id  int    Discogs master release ID (0 if none)
discogs_enriched  bool

Setup (phi_config.yaml)
-----------------------
discogs:
  token: "YOUR_PERSONAL_ACCESS_TOKEN"

Get a token at https://www.discogs.com/settings/developers (free account).
Without a token the client still works at 25 req/min (unauthenticated).
With a token: 60 req/min.
"""
from __future__ import annotations

import json
import threading
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Optional


_API_BASE = "https://api.discogs.com"
_UA       = "phi/1.0 +https://github.com/phi-player"
_TIMEOUT  = 10


# ── result dataclass ──────────────────────────────────────────────────────────

@dataclass
class DiscogsRelease:
    release_id:      int
    master_id:       int              = 0
    year:            Optional[int]    = None
    master_year:     Optional[int]    = None
    country:         Optional[str]    = None
    format:          Optional[str]    = None
    format_details:  list[str]        = field(default_factory=list)
    genres:          list[str]        = field(default_factory=list)
    styles:          list[str]        = field(default_factory=list)
    community_rating: float           = 0.0
    community_count:  int             = 0
    have:            int              = 0
    want:            int              = 0
    credits:         dict[str, list[str]] = field(default_factory=dict)
    label:           Optional[str]    = None
    catno:           Optional[str]    = None
    notes:           Optional[str]    = None

    @property
    def desirability(self) -> float:
        """want / (have + want + 1) — higher means harder to find."""
        return self.want / (self.have + self.want + 1)

    def as_annotation_dict(self) -> dict:
        d: dict = {
            "discogs_release_id":  self.release_id,
            "discogs_master_id":   self.master_id,
            "discogs_have":        self.have,
            "discogs_want":        self.want,
            "discogs_desirability": round(self.desirability, 4),
            "discogs_enriched":    True,
        }
        if self.year:
            d["discogs_year"]    = self.year
        if self.master_year:
            d["discogs_master_year"] = self.master_year
        if self.country:
            d["discogs_country"] = self.country
        if self.format:
            d["discogs_format"]  = self.format
        if self.format_details:
            d["discogs_format_details"] = self.format_details
        if self.genres:
            d["discogs_genres"]  = self.genres
        if self.styles:
            d["discogs_styles"]  = self.styles
        if self.community_rating:
            d["discogs_community_rating"] = self.community_rating
        if self.community_count:
            d["discogs_community_count"]  = self.community_count
        if self.credits:
            d["discogs_credits"] = self.credits
        if self.label:
            d["discogs_label"]   = self.label
        if self.catno:
            d["discogs_catno"]   = self.catno
        if self.notes:
            d["discogs_notes"]   = self.notes
        return d


# ── rate limiter ──────────────────────────────────────────────────────────────

class _RateLimiter:
    def __init__(self, max_per_min: float = 25.0) -> None:
        self._interval = 60.0 / max_per_min
        self._last     = 0.0
        self._lock     = threading.Lock()

    def wait(self) -> None:
        with self._lock:
            now  = time.monotonic()
            wait = self._interval - (now - self._last)
            if wait > 0:
                threading.Event().wait(wait)
            self._last = time.monotonic()


# ── DiscogsClient ─────────────────────────────────────────────────────────────

class DiscogsClient:
    """
    Thin Discogs API wrapper with rate limiting and graceful degradation.
    All methods return None on failure — never raise.
    """

    def __init__(
        self,
        token:       str   = "",
        *,
        max_per_min: float = 60.0,
    ) -> None:
        self._token   = token.strip()
        self._limiter = _RateLimiter(max_per_min if token else 25.0)

    @property
    def available(self) -> bool:
        return True  # always available; token only affects rate limit

    # ── public API ────────────────────────────────────────────────────────────

    def search_release(
        self,
        title:  str,
        artist: str,
        *,
        year:   Optional[int] = None,
    ) -> Optional[DiscogsRelease]:
        """
        Search Discogs for a release matching *title* + *artist*.
        Returns the best match (first result) enriched with community data,
        or None on failure / no results.
        """
        if not (title or artist):
            return None

        params: dict[str, str] = {
            "type":    "release",
            "format":  "album",
            "per_page": "5",
        }
        if title:
            params["q"] = f"{artist} {title}".strip()
        if artist:
            params["artist"] = artist
        if year:
            params["year"] = str(year)

        data = self._get("/database/search", params)
        if not data:
            return None

        results = data.get("results", [])
        if not results:
            return None

        best = results[0]
        release_id = best.get("id")
        if not release_id:
            return None

        return self.fetch_release(release_id)

    def fetch_release(self, release_id: int) -> Optional[DiscogsRelease]:
        """
        Fetch full release data by ID.
        Returns a populated DiscogsRelease or None on failure.
        """
        data = self._get(f"/releases/{release_id}", {})
        if not data:
            return None
        return self._parse_release(data)

    # ── private ───────────────────────────────────────────────────────────────

    def _get(self, path: str, params: dict) -> Optional[dict]:
        """Make a rate-limited GET request to the Discogs API."""
        self._limiter.wait()
        try:
            qs  = urllib.parse.urlencode(params) if params else ""
            url = _API_BASE + path + (f"?{qs}" if qs else "")
            headers = {
                "User-Agent": _UA,
                "Accept":     "application/vnd.discogs.v2.discogs+json",
            }
            if self._token:
                headers["Authorization"] = f"Discogs token={self._token}"

            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                return json.loads(resp.read().decode("utf-8", errors="replace"))
        except Exception:
            return None

    def _parse_release(self, data: dict) -> DiscogsRelease:
        release_id = int(data.get("id", 0))
        master_id  = int(data.get("master_id") or 0)
        year_raw   = data.get("year")
        year       = int(year_raw) if year_raw else None
        country    = data.get("country")

        # Format — e.g. [{"name": "Vinyl", "qty": "1", "descriptions": ["LP", "Album"]}]
        fmt_name    = None
        fmt_details: list[str] = []
        for fmt in (data.get("formats") or []):
            if not fmt_name:
                fmt_name = fmt.get("name")
            fmt_details.extend(fmt.get("descriptions") or [])

        genres = data.get("genres") or []
        styles = data.get("styles") or []

        # Community ratings + have/want
        community       = data.get("community") or {}
        comm_rating_obj = community.get("rating") or {}
        comm_rating     = float(comm_rating_obj.get("average") or 0.0)
        comm_count      = int(comm_rating_obj.get("count") or 0)
        have            = int(community.get("have") or 0)
        want            = int(community.get("want") or 0)

        # Production credits from extraartists
        credits: dict[str, list[str]] = {}
        for ea in (data.get("extraartists") or []):
            role = (ea.get("role") or "").strip().lower()
            name = (ea.get("name") or "").strip()
            if role and name:
                credits.setdefault(role, [])
                if name not in credits[role]:
                    credits[role].append(name)

        # Label + catalog number
        label_name = None
        catno      = None
        for lbl in (data.get("labels") or []):
            if not label_name:
                label_name = lbl.get("name")
                catno      = lbl.get("catno")
            break

        # Notes — capped at 500 chars
        notes_raw = (data.get("notes") or "").strip()
        notes     = notes_raw[:500] if notes_raw else None

        # Fetch master year if we have a master_id
        master_year: Optional[int] = None
        if master_id:
            master_data = self._get(f"/masters/{master_id}", {})
            if master_data:
                my_raw = master_data.get("year")
                master_year = int(my_raw) if my_raw else None

        return DiscogsRelease(
            release_id      = release_id,
            master_id       = master_id,
            year            = year,
            master_year     = master_year,
            country         = country,
            format          = fmt_name,
            format_details  = list(dict.fromkeys(fmt_details)),  # deduplicate, preserve order
            genres          = genres,
            styles          = styles,
            community_rating= comm_rating,
            community_count = comm_count,
            have            = have,
            want            = want,
            credits         = credits,
            label           = label_name,
            catno           = catno,
            notes           = notes,
        )


# ── module-level factory ──────────────────────────────────────────────────────

def build_discogs_client() -> Optional[DiscogsClient]:
    """
    Build a DiscogsClient from phi_config.yaml.
    Returns None only if Discogs is explicitly disabled in config.
    Without a token the client still works at 25 req/min.
    """
    try:
        from phi.config import load_phi_config
        cfg   = load_phi_config().get("discogs", {})
        if cfg.get("disabled"):
            return None
        token = cfg.get("token", "")
        return DiscogsClient(token=token)
    except Exception:
        return DiscogsClient()
