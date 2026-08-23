# -*- coding: utf-8 -*-
"""pipeline.sources.soundcloud — SoundCloud fallback source.

Searches SoundCloud via yt-dlp's scsearch: extractor.  Useful for
tracks that are unavailable on YouTube Music / YouTube (regional blocks,
copyright takedowns, etc.).

Note: config.yaml sets soundcloud.use_proxy=false because SoundCloud
blocks SOCKS5 in some regions.  The proxy arg is accepted but defaults
to None here to honour that setting at the call site.
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


class SoundCloudSource(Source):
    """Download from SoundCloud by searching title + artists."""

    name = "soundcloud"

    def download(
        self,
        track:      TrackInfo,
        output_dir: Path,
        fmt:        str  = "mp3",
        proxy:      Optional[str] = None,
        timeout_s:  int  = 600,
    ) -> DownloadResult:
        output_dir.mkdir(parents=True, exist_ok=True)
        query   = track.search_query
        outtmpl = str(output_dir / "%(uploader)s - %(title)s.%(ext)s")

        cmd = [
            _YTDLP,
            f"scsearch:1:{query}",
            "--extract-audio",
            "--audio-format", fmt,
            "--audio-quality", "0",
            "--no-overwrites",
            "--add-metadata",
            "--output", outtmpl,
        ]
        # SoundCloud blocks SOCKS5 in some regions; only attach proxy if caller
        # explicitly passes one (use_proxy=true in config).
        if proxy:
            cmd += ["--proxy", proxy]

        log.debug("yt-dlp scsearch: %r → %s", query, output_dir)
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

        log.info("soundcloud ✓  %s → %s", track.search_query, path)
        return DownloadResult(track=track, source=self.name, ok=True, path=path)
