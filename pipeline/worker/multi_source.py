# -*- coding: utf-8 -*-
"""pipeline.worker.multi_source — per-track source priority chain.

For each track, tries sources in config priority order until one
succeeds.  Source objects are passed in so the caller controls ordering
and proxy settings per source.

Usage
-----
    from pipeline.worker.multi_source import download_track
    from pipeline.sources import DEFAULT_SOURCES

    result = download_track(
        track,
        output_dir=Path("~/Desktop/Spotify/Liked Songs"),
        fmt="mp3",
        sources=DEFAULT_SOURCES,
        proxy="socks5://127.0.0.1:1080",
        timeout_s=600,
    )
    if result.ok:
        print("saved to", result.path)
    else:
        print("all sources failed:", result.error)
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Sequence

from pipeline.fetcher.models import TrackInfo
from pipeline.sources.base import DownloadResult, Source

log = logging.getLogger(__name__)


def download_track(
    track:      TrackInfo,
    output_dir: Path,
    sources:    Sequence[Source],
    fmt:        str          = "mp3",
    proxy:      Optional[str] = None,
    timeout_s:  int          = 600,
) -> DownloadResult:
    """
    Try each source in *sources* order.  Return on first success.

    If all sources fail, returns a DownloadResult with ok=False and a
    combined error summary.

    Key invariant: no source in this chain passes a Spotify URL to
    yt-dlp.  Each source searches by title + artists so yt-dlp uses
    YouTube Music / YouTube / SoundCloud / Internet Archive — not
    Spotify's 30-second preview_url.
    """
    errors: list[str] = []

    for source in sources:
        log.debug("trying source=%r for %r", source.name, track.search_query)
        result = source.download(
            track=track,
            output_dir=output_dir,
            fmt=fmt,
            proxy=proxy,
            timeout_s=timeout_s,
        )
        if result.ok:
            return result
        errors.append(f"[{source.name}] {result.error or 'unknown error'}")
        log.warning("source %r failed for %r: %s", source.name, track.search_query, result.error)

    combined = " | ".join(errors)
    log.error("all sources failed for %r: %s", track.search_query, combined)
    return DownloadResult(
        track=track,
        source="<all failed>",
        ok=False,
        error=combined,
    )
