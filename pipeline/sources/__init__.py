# -*- coding: utf-8 -*-
"""pipeline.sources — pluggable download backends.

All sources search for a track by title + artists and download via yt-dlp.
None of them pass Spotify URLs to yt-dlp, which would trigger yt-dlp's
Spotify extractor and return only the 30-second preview_url.

Priority order (matches config.yaml sources.priority):
    1. youtube_music   — ytmsearch: (YouTube Music catalogue)
    2. youtube         — ytsearch:  (regular YouTube, "official audio" bias)
    3. soundcloud      — scsearch:
    4. internet_archive — archive.org audio search
"""
from pipeline.sources.base              import Source, DownloadResult
from pipeline.sources.youtube_music    import YouTubeMusicSource
from pipeline.sources.youtube          import YouTubeSource
from pipeline.sources.soundcloud       import SoundCloudSource
from pipeline.sources.internet_archive import InternetArchiveSource

# Ordered list matching config.yaml default priority
DEFAULT_SOURCES: list[Source] = [
    YouTubeMusicSource(),
    YouTubeSource(),
    SoundCloudSource(),
    InternetArchiveSource(),
]

__all__ = [
    "Source", "DownloadResult",
    "YouTubeMusicSource", "YouTubeSource",
    "SoundCloudSource", "InternetArchiveSource",
    "DEFAULT_SOURCES",
]
