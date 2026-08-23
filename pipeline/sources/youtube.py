# -*- coding: utf-8 -*-
"""pipeline.sources.youtube — regular YouTube fallback source.

Searches YouTube (not YouTube Music) using ytsearch: when the YouTube
Music source fails or is unavailable.  Prefers "official audio" and
"lyrics" videos over unofficial covers.
"""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Optional

from pipeline.fetcher.models import TrackInfo
from pipeline.sources.base import DownloadResult, Source
from pipeline.sources.youtube_music import _find_downloaded_file

log = logging.getLogger(__name__)

_YTDLP = "yt-dlp"

# Additional words appended to the search query to bias toward official audio.
_AUDIO_BIAS = "official audio"


class YouTubeSource(Source):
    """
    Download from regular YouTube by searching title + artists.

    Uses ytsearch:1: (not a Spotify URL) so yt-dlp finds a full song
    on YouTube, not Spotify's 30-second preview_url.
    """

    name = "youtube"

    def download(
        self,
        track:      TrackInfo,
        output_dir: Path,
        fmt:        str  = "mp3",
        proxy:      Optional[str] = None,
        timeout_s:  int  = 600,
    ) -> DownloadResult:
        output_dir.mkdir(parents=True, exist_ok=True)
        query = f"{track.search_query} {_AUDIO_BIAS}"
        outtmpl = str(output_dir / "%(uploader)s - %(title)s.%(ext)s")

        cmd = [
            _YTDLP,
            f"ytsearch:1:{query}",
            "--extract-audio",
            "--audio-format", fmt,
            "--audio-quality", "0",
            "--no-overwrites",
            "--embed-thumbnail",
            "--add-metadata",
            "--output", outtmpl,
        ]
        if proxy:
            cmd += ["--proxy", proxy]

        log.debug("yt-dlp ytsearch: %r → %s", query, output_dir)
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout_s,
            )
        except subprocess.TimeoutExpired:
            return DownloadResult(
                track=track, source=self.name, ok=False,
                error=f"yt-dlp timed out after {timeout_s}s",
            )
        except FileNotFoundError:
            return DownloadResult(
                track=track, source=self.name, ok=False,
                error=f"{_YTDLP!r} not found",
            )
        except Exception as exc:
            return DownloadResult(track=track, source=self.name, ok=False, error=str(exc))

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

        log.info("youtube ✓  %s → %s", track.search_query, path)
        return DownloadResult(track=track, source=self.name, ok=True, path=path)
