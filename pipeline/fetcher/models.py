# -*- coding: utf-8 -*-
"""pipeline.fetcher.models — core data models for the download pipeline.

TrackInfo  — one Spotify track (name, artists, album, url, duration)
Job        — a batch of tracks destined for one output directory

Design note
-----------
Workers receive TrackInfo objects, not raw Spotify URLs.  The sources/
layer searches YouTube Music (or fallback sources) by title + artist,
which avoids yt-dlp's Spotify extractor — that extractor only returns
the 30-second preview_url from Spotify's Web API, not the full track.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List


@dataclass
class TrackInfo:
    """Metadata for one Spotify track, resolved before the download stage."""
    name:        str
    artists:     str            # comma-joined artist names
    album:       str
    spotify_url: str            # https://open.spotify.com/track/<id>
    isrc:        str  = ""
    duration_ms: int  = 0

    @property
    def search_query(self) -> str:
        """'Artist Name - Track Name' query for YouTube Music / YouTube."""
        return f"{self.artists} - {self.name}"

    @property
    def safe_filename(self) -> str:
        """Filesystem-safe 'Artist - Title' string (no slashes, colons, etc.)."""
        def _clean(s: str) -> str:
            for ch in r'/\:*?"<>|':
                s = s.replace(ch, "_")
            return s.strip()
        return f"{_clean(self.artists)} - {_clean(self.name)}"


@dataclass
class Job:
    """
    A unit of work: a list of tracks to download into one output directory.

    Large source lists (liked songs, big playlists) are chunked by the
    scheduler so each Job contains at most config.download.chunk_size tracks.
    This caps the blast-radius of a single crash.
    """
    id:         str
    name:       str
    tracks:     List[TrackInfo]  = field(default_factory=list)
    output_dir: Path             = field(default_factory=Path)
    fmt:        str              = "mp3"
    job_type:   str              = "liked"   # liked | album | playlist
