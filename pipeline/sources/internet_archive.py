# -*- coding: utf-8 -*-
"""pipeline.sources.internet_archive — Internet Archive fallback source.

Searches the Internet Archive (archive.org) for audio recordings.
Useful as a last resort for very old or obscure tracks.

yt-dlp's internetarchive extractor requires a search URL format:
    https://archive.org/search?query=...&and[]=mediatype:audio
"""
from __future__ import annotations

import logging
import subprocess
import urllib.parse
from pathlib import Path
from typing import Optional

from pipeline.fetcher.models import TrackInfo
from pipeline.sources.base import DownloadResult, Source
from pipeline.sources.youtube_music import _find_downloaded_file

log = logging.getLogger(__name__)

_YTDLP     = "yt-dlp"
_SEARCH_BASE = "https://archive.org/search?query={q}&and[]=mediatype:audio&output=json"


class InternetArchiveSource(Source):
    """Download from Internet Archive (last-resort fallback)."""

    name = "internet_archive"

    def download(
        self,
        track:      TrackInfo,
        output_dir: Path,
        fmt:        str  = "mp3",
        proxy:      Optional[str] = None,
        timeout_s:  int  = 600,
    ) -> DownloadResult:
        output_dir.mkdir(parents=True, exist_ok=True)

        # Build an Internet Archive audio search URL
        q       = urllib.parse.quote(track.search_query)
        url     = f"https://archive.org/search?query={q}&and[]=mediatype:audio"
        outtmpl = str(output_dir / "%(uploader)s - %(title)s.%(ext)s")

        cmd = [
            _YTDLP,
            url,
            "--playlist-items", "1",     # only the first result
            "--extract-audio",
            "--audio-format", fmt,
            "--audio-quality", "0",
            "--no-overwrites",
            "--add-metadata",
            "--output", outtmpl,
        ]
        if proxy:
            cmd += ["--proxy", proxy]

        log.debug("yt-dlp internet_archive: %r → %s", track.search_query, output_dir)
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

        log.info("internet_archive ✓  %s → %s", track.search_query, path)
        return DownloadResult(track=track, source=self.name, ok=True, path=path)
