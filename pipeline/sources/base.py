# -*- coding: utf-8 -*-
"""pipeline.sources.base — abstract base for all download sources.

Every concrete source must implement download() and set a unique name.
Results carry enough context for the executor to log and retry.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from pipeline.fetcher.models import TrackInfo


@dataclass
class DownloadResult:
    track:  TrackInfo
    source: str
    ok:     bool
    path:   Optional[str] = None   # absolute path of downloaded file
    error:  Optional[str] = None


class Source(abc.ABC):
    """Abstract download source."""

    name: str  # subclasses must set this as a class attribute

    @abc.abstractmethod
    def download(
        self,
        track:      TrackInfo,
        output_dir: Path,
        fmt:        str  = "mp3",
        proxy:      Optional[str] = None,
        timeout_s:  int  = 600,
    ) -> DownloadResult:
        """
        Download *track* into *output_dir*.

        Parameters
        ----------
        track      : TrackInfo with name, artists, search_query, safe_filename
        output_dir : destination directory (must exist before calling)
        fmt        : output audio format ("mp3", "ogg", "flac", …)
        proxy      : optional SOCKS5 proxy URL e.g. "socks5://127.0.0.1:1080"
        timeout_s  : hard wall-clock timeout (SIGKILL on breach)

        Returns a DownloadResult.  Must never raise.
        """
