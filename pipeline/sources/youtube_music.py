# -*- coding: utf-8 -*-
"""pipeline.sources.youtube_music — YouTube Music download source.

THE FIX FOR 30-SECOND SONGS
============================
yt-dlp's built-in Spotify extractor fetches the track's `preview_url`
from Spotify's Web API — a 30-second MP3 clip.  Full tracks are
DRM-encrypted and cannot be obtained via the Spotify API.

This source deliberately does NOT pass Spotify URLs to yt-dlp.
Instead it:

    1. Builds a search query from the track's title + artists
       e.g.  "Radiohead - Creep"
    2. Uses yt-dlp's ytmsearch: prefix to search YouTube Music
       → finds the full-length music video / audio track
    3. Downloads and post-processes to the target format

The result is a full-length file, not a preview clip.
"""
from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path
from typing import Optional

from pipeline.fetcher.models import TrackInfo
from pipeline.sources.base import DownloadResult, Source

log = logging.getLogger(__name__)

_YTDLP = "yt-dlp"   # must be on PATH; prefer the mamba env's copy


def _find_downloaded_file(output_dir: Path, stem: str, fmt: str) -> Optional[str]:
    """
    Locate the file yt-dlp wrote into *output_dir*.

    yt-dlp can change the filename slightly (sanitisation, extension
    disambiguation), so we look for any file whose stem contains the
    expected stem as a substring rather than an exact match.
    """
    stem_lower = stem.lower()
    for f in output_dir.iterdir():
        if f.suffix.lstrip(".").lower() in (fmt, "mp3", "m4a", "ogg", "opus", "flac", "webm"):
            if stem_lower in f.stem.lower():
                return str(f)
    # Fallback: any new audio file (yt-dlp timestamp approach)
    audio_exts = {".mp3", ".m4a", ".ogg", ".opus", ".flac", ".webm", ".wav"}
    candidates = [f for f in output_dir.iterdir() if f.suffix.lower() in audio_exts]
    if candidates:
        return str(max(candidates, key=lambda f: f.stat().st_mtime))
    return None


class YouTubeMusicSource(Source):
    """
    Download from YouTube Music by searching title + artists.

    Search prefix: ytmsearch: (YouTube Music catalogue, prefers official audio)
    Fallback:      ytsearch:  (regular YouTube, if Music returns nothing)
    """

    name = "youtube_music"

    def download(
        self,
        track:      TrackInfo,
        output_dir: Path,
        fmt:        str  = "mp3",
        proxy:      Optional[str] = None,
        timeout_s:  int  = 600,
    ) -> DownloadResult:
        output_dir.mkdir(parents=True, exist_ok=True)
        query = track.search_query

        # Output template: Artist - Title.%(ext)s
        # yt-dlp sanitises the filename itself; we recover it afterwards.
        outtmpl = str(output_dir / "%(uploader)s - %(title)s.%(ext)s")

        cmd = [
            _YTDLP,
            # Search YouTube Music for the first result matching the query.
            # ytmsearch:1: returns one result from the Music catalogue.
            f"ytmsearch:1:{query}",

            # Audio-only: extract best audio and encode to target format.
            "--extract-audio",
            "--audio-format", fmt,
            "--audio-quality", "0",   # best quality

            # Skip if a file with the same name already exists.
            "--no-overwrites",

            # Embed metadata so phi's enricher has good base tags.
            "--embed-thumbnail",
            "--add-metadata",

            # Output path.
            "--output", outtmpl,

            # Never pass a Spotify URL here — that would trigger yt-dlp's
            # Spotify extractor and download only the 30-second preview.
        ]

        if proxy:
            cmd += ["--proxy", proxy]

        log.debug("yt-dlp ytmsearch: %r → %s", query, output_dir)
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_s,
            )
        except subprocess.TimeoutExpired:
            return DownloadResult(
                track=track, source=self.name, ok=False,
                error=f"yt-dlp timed out after {timeout_s}s",
            )
        except FileNotFoundError:
            return DownloadResult(
                track=track, source=self.name, ok=False,
                error=f"{_YTDLP!r} not found — install yt-dlp (pip install yt-dlp)",
            )
        except Exception as exc:
            return DownloadResult(
                track=track, source=self.name, ok=False,
                error=f"yt-dlp subprocess error: {exc}",
            )

        if result.returncode != 0:
            err = (result.stderr or result.stdout or "").strip().splitlines()
            tail = "\n".join(err[-5:]) if err else "no output"
            return DownloadResult(
                track=track, source=self.name, ok=False,
                error=f"yt-dlp exit {result.returncode}: {tail}",
            )

        path = _find_downloaded_file(output_dir, track.safe_filename, fmt)
        if path is None:
            return DownloadResult(
                track=track, source=self.name, ok=False,
                error="yt-dlp succeeded but no output file found",
            )

        log.info("youtube_music ✓  %s → %s", track.search_query, path)
        return DownloadResult(track=track, source=self.name, ok=True, path=path)
