# -*- coding: utf-8 -*-
"""phi.meta.mb_client — MusicBrainz + CoverArtArchive fetch layer.

Rate-limited to ≤ 10 requests / second (MusicBrainz policy requires a
proper User-Agent and allows 1 req/sec anonymous; 10 req/sec with a
registered User-Agent string).

All methods return None / {} on failure rather than raising so the
enrichment pipeline can degrade gracefully.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Optional


# ── MusicBrainz result types ──────────────────────────────────────────────────

@dataclass
class MBRecording:
    """Flattened metadata fetched from MusicBrainz for one recording."""
    mbid:           str
    title:          Optional[str]   = None
    artist:         Optional[str]   = None
    artist_mbid:    Optional[str]   = None
    artist_country: Optional[str]   = None   # e.g. "US", "GB"
    artist_type:    Optional[str]   = None   # "Person", "Group", "Orchestra", …
    album:          Optional[str]   = None
    release_mbid:   Optional[str]   = None
    label:          Optional[str]   = None   # record label name
    catalog_number: Optional[str]   = None
    track_number:   Optional[int]   = None
    total_tracks:   Optional[int]   = None
    disc_number:    Optional[int]   = None
    year:           Optional[str]   = None
    country:        Optional[str]   = None   # release country (not artist country)
    genre:          Optional[str]   = None   # top tag
    genres:         list[str]       = field(default_factory=list)   # up to 5 tags
    isrc:           Optional[str]   = None
    composer:       Optional[str]   = None
    art_bytes:      Optional[bytes] = None

    def as_meta_dict(self) -> dict:
        """Return a dict compatible with Library.meta_cache format."""
        return {
            k: v for k, v in {
                "title":        self.title,
                "artist":       self.artist,
                "album":        self.album,
                "track":        self.track_number,
                "year":         self.year,
                "genre":        self.genre,
                "art_bytes":    self.art_bytes,
                "mbid":         self.mbid,
                "release_mbid": self.release_mbid,
                "isrc":         self.isrc,
                "label":        self.label,
                "composer":     self.composer,
            }.items() if v is not None
        }

    def as_annotation_dict(self) -> dict:
        """Return enrichment data for Library.annotations."""
        d: dict = {
            k: v for k, v in {
                "mbid":           self.mbid,
                "artist_mbid":    self.artist_mbid,
                "release_mbid":   self.release_mbid,
                "artist_country": self.artist_country,
                "artist_type":    self.artist_type,
                "label":          self.label,
                "catalog_number": self.catalog_number,
                "country":        self.country,
                "isrc":           self.isrc,
                "composer":       self.composer,
                "total_tracks":   self.total_tracks,
                "disc_number":    self.disc_number,
                "mb_enriched":    True,
            }.items() if v is not None
        }
        if self.genres:
            d["mb_genres"] = self.genres
        return d


# ── rate limiter ──────────────────────────────────────────────────────────────

class _RateLimiter:
    """Token-bucket rate limiter, thread-safe."""

    def __init__(self, max_per_sec: float = 2.0) -> None:
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


# ── MusicBrainzClient ────────────────────────────────────────────────────────

class MusicBrainzClient:
    """
    Thin wrapper around musicbrainzngs with rate limiting and graceful
    degradation.

    Parameters
    ----------
    app_name    application name for the required User-Agent header
    app_version application version string
    contact     contact email (required by MB policy)
    max_per_sec maximum requests per second (default: 2, safe for all accounts)
    """

    def __init__(
        self,
        app_name:    str   = "phi",
        app_version: str   = "0.3.0",
        contact:     str   = "phi@local",
        max_per_sec: float = 2.0,
    ) -> None:
        self._limiter = _RateLimiter(max_per_sec)
        try:
            import musicbrainzngs as mbz
            mbz.set_useragent(app_name, app_version, contact)
            self._mbz = mbz
        except ImportError:
            self._mbz = None

    # ── public API ────────────────────────────────────────────────────────────

    def fetch_recording(self, mbid: str) -> Optional[MBRecording]:
        """
        Fetch recording metadata from MusicBrainz.

        Includes: title, artist (with country + type), release, label,
        track number, total tracks, year, ISRC, multiple genre tags.

        Returns an MBRecording on success, None on any failure.
        """
        if not self._mbz or not mbid:
            return None

        self._limiter.wait()
        try:
            result = self._mbz.get_recording_by_id(
                mbid,
                includes=[
                    "artists",
                    "releases",
                    "release-groups",
                    "tags",
                    "isrcs",
                    "artist-credits",
                    "labels",
                    "work-level-rels",
                ],
            )
        except Exception:
            return None

        rec = result.get("recording", {})
        if not rec:
            return None

        title           = rec.get("title")
        artist          = None
        artist_mbid     = None
        artist_country  = None
        artist_type     = None

        for credit in rec.get("artist-credit", []):
            if isinstance(credit, dict) and "artist" in credit:
                a_obj          = credit["artist"]
                artist         = a_obj.get("name")
                artist_mbid    = a_obj.get("id")
                artist_country = a_obj.get("country")
                artist_type    = a_obj.get("type")
                break

        album        = None
        release_mbid = None
        track_number = None
        total_tracks = None
        disc_number  = None
        year         = None
        country      = None
        label        = None
        catalog_number = None

        releases = rec.get("release-list", [])
        if releases:
            rel          = releases[0]
            album        = rel.get("title")
            release_mbid = rel.get("id")
            year         = (rel.get("date") or "")[:4] or None
            country      = rel.get("country")

            # Label + catalog number from label-info-list
            label_list = rel.get("label-info-list", [])
            if label_list and isinstance(label_list, list):
                li = label_list[0]
                if isinstance(li, dict):
                    label_obj = li.get("label", {})
                    if isinstance(label_obj, dict):
                        label = label_obj.get("name")
                    catalog_number = li.get("catalog-number")

            # Track number + total tracks inside medium-list
            for medium in rel.get("medium-list", []):
                track_list = medium.get("track-list", [])
                for track in track_list:
                    if track.get("recording", {}).get("id") == mbid:
                        try:
                            track_number = int(track.get("number", 0))
                        except (ValueError, TypeError):
                            pass
                        try:
                            total_tracks = int(medium.get("track-count", 0)) or None
                        except (ValueError, TypeError):
                            pass
                        try:
                            disc_number = int(medium.get("position", 1))
                        except (ValueError, TypeError):
                            pass

        # Tags → genres (top 5 by count, descending)
        tags = rec.get("tag-list", [])
        if isinstance(tags, dict):
            tags = [tags]
        tags_sorted = sorted(tags, key=lambda t: -int(t.get("count", 0) or 0))
        genres = [t["name"] for t in tags_sorted[:5] if t.get("name")]
        genre  = genres[0] if genres else None

        # ISRC (first one if multiple)
        isrc_list = rec.get("isrc-list", [])
        isrc = isrc_list[0] if isrc_list else None

        # Composer — extracted from work-level performance relations.
        # MB models composition via work artist-rels. We capture multiple writing
        # roles (composer, writer, lyricist, arranger) and join up to 3 names.
        # Both "artist-relation-list" and "relation-list" field names are checked
        # because musicbrainzngs normalisation varies by server version.
        _WRITING_ROLES = {"composer", "writer", "lyricist", "arranger", "orchestrator"}
        composer_names: list[str] = []

        for work_rel in rec.get("work-relation-list", []):
            if not isinstance(work_rel, dict):
                continue
            if work_rel.get("type") != "performance":
                continue
            work = work_rel.get("work", {})
            artist_rels = (
                work.get("artist-relation-list")
                or work.get("relation-list")
                or []
            )
            for ar in artist_rels:
                if not isinstance(ar, dict):
                    continue
                rel_type = (ar.get("type") or "").strip().lower()
                if rel_type not in _WRITING_ROLES:
                    continue
                a = ar.get("artist", {})
                name = (a.get("name") or a.get("sort-name") or "").strip()
                if name and name not in composer_names:
                    composer_names.append(name)

        composer = "; ".join(composer_names[:3]) if composer_names else None

        recording = MBRecording(
            mbid           = mbid,
            title          = title,
            artist         = artist,
            artist_mbid    = artist_mbid,
            artist_country = artist_country,
            artist_type    = artist_type,
            album          = album,
            release_mbid   = release_mbid,
            label          = label,
            catalog_number = catalog_number,
            track_number   = track_number,
            total_tracks   = total_tracks,
            disc_number    = disc_number,
            year           = year,
            country        = country,
            genre          = genre,
            genres         = genres,
            isrc           = isrc,
            composer       = composer,
        )

        # Fetch cover art if we have a release MBID
        if release_mbid:
            recording.art_bytes = self.fetch_cover_art(release_mbid)

        return recording

    def fetch_artist(self, artist_mbid: str) -> Optional[dict]:
        """
        Fetch artist-level metadata from MusicBrainz.

        Returns a dict with keys:
            name, type, area, begin_year, end_year,
            members (list of str, Groups only), aliases (list of str)

        Returns None on any failure.
        """
        if not self._mbz or not artist_mbid:
            return None

        self._limiter.wait()
        try:
            result = self._mbz.get_artist_by_id(
                artist_mbid,
                includes=["aliases", "artist-rels", "tags"],
            )
        except Exception:
            return None

        art = result.get("artist", {})
        if not art:
            return None

        # Life span
        ls         = art.get("life-span") or {}
        begin_str  = ls.get("begin") or ""
        end_str    = ls.get("end")   or ""
        begin_year = int(begin_str[:4]) if begin_str and begin_str[:4].isdigit() else None
        end_year   = int(end_str[:4])   if end_str   and end_str[:4].isdigit()   else None

        # Area (origin location)
        area_obj = art.get("area") or {}
        area     = area_obj.get("name")

        # Members — artist-rels where type is "member of band"
        members: list[str] = []
        for rel in (art.get("artist-relation-list") or []):
            if "member" in (rel.get("type") or "").lower():
                a = rel.get("artist", {})
                if a.get("name"):
                    members.append(a["name"])

        # Aliases
        aliases = [
            a["name"] for a in (art.get("alias-list") or [])
            if a.get("name")
        ][:5]

        return {
            "mb_artist_name":       art.get("name"),
            "mb_artist_type":       art.get("type"),
            "mb_artist_area":       area,
            "mb_artist_begin_year": begin_year,
            "mb_artist_end_year":   end_year,
            "mb_artist_members":    members or None,
            "mb_artist_aliases":    aliases or None,
            "mb_artist_enriched":   True,
        }

    def fetch_cover_art(self, release_mbid: str, *, size: str = "250") -> Optional[bytes]:
        """
        Fetch front cover art from CoverArtArchive for a release MBID.

        size: "250" | "500" | "1200" — thumbnail size in pixels
        Returns None on any failure (no art, network error, etc.)
        """
        if not release_mbid:
            return None

        self._limiter.wait()
        try:
            import requests
            url  = f"https://coverartarchive.org/release/{release_mbid}/front-{size}"
            resp = requests.get(url, timeout=8, allow_redirects=True)
            if resp.status_code == 200 and resp.content:
                return resp.content
        except Exception:
            pass
        return None
