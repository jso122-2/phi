# -*- coding: utf-8 -*-
"""
pipeline.worker.fs_organizer — staging → output file organizer with M3U updates.

Responsibility
--------------
After a source downloads a track into the staging directory, FsOrganizer:

    1. Resolves the final destination path (output_dir / safe_filename.ext)
    2. Handles collisions with an integer suffix  (e.g. "Title (2).mp3")
    3. Moves the file atomically (same filesystem) or falls back to copy+delete
    4. Appends an #EXTINF entry to the M3U playlist for the destination directory
       (creates the M3U if it doesn't exist)

M3U format
----------
    #EXTM3U
    #EXTINF:<duration_ms_as_int>,<artists> - <title>
    /absolute/path/to/Artist - Title.mp3

Duration is taken from TrackInfo.duration_ms when available; falls back to -1
(unknown) which is valid per the M3U spec.

Usage
-----
    organizer = FsOrganizer(output_dir=Path("~/Desktop/Spotify/Liked Songs"),
                             staging_dir=Path("data/staging"),
                             m3u_path=Path("~/Desktop/Spotify/liked.m3u"))

    final_path = organizer.organize(result)
    # result.path → staging file moved to output_dir
    # liked.m3u  → new #EXTINF line appended

If staging_dir is None, the source already wrote directly to output_dir and
the move step is skipped — only the M3U is updated.

If m3u_path is None, the playlist update step is skipped.
"""
from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path
from typing import Optional

from pipeline.sources.base import DownloadResult

log = logging.getLogger(__name__)

_M3U_HEADER: str = "#EXTM3U\n"
_COLLISION_LIMIT: int = 99    # max rename attempts before raising


class FsOrganizer:
    """
    Move downloaded files from staging to output and maintain an M3U playlist.

    Parameters
    ----------
    output_dir  : final destination directory for audio files
    staging_dir : where sources write before organization; None = already in output_dir
    m3u_path    : path to the M3U playlist file to maintain; None = skip M3U
    """

    def __init__(
        self,
        output_dir: Path,
        staging_dir: Optional[Path] = None,
        m3u_path: Optional[Path] = None,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.staging_dir = Path(staging_dir) if staging_dir else None
        self.m3u_path = Path(m3u_path) if m3u_path else None

    # ── public API ─────────────────────────────────────────────────────────────
    def organize(self, result: DownloadResult) -> Optional[Path]:
        """
        Organise a completed download result.

        Parameters
        ----------
        result : DownloadResult from a Source.download() call.  Must have ok=True
                 and a non-None path pointing to the downloaded file.

        Returns
        -------
        Path of the final file in output_dir, or None if result is not ok /
        the source file no longer exists.
        """
        if not result.ok or not result.path:
            return None

        src = Path(result.path)
        if not src.exists():
            log.warning("organize: source file gone: %s", src)
            return None

        # ── move staging → output ──────────────────────────────────────────────
        if self.staging_dir and src.is_relative_to(self.staging_dir):
            dest = self._resolve_dest(src)
            dest = self._move(src, dest)
        else:
            # Source already wrote directly to output_dir.
            dest = src

        # ── M3U update ─────────────────────────────────────────────────────────
        if self.m3u_path:
            duration_s = (
                result.track.duration_ms // 1000
                if result.track.duration_ms
                else -1
            )
            label = f"{result.track.artists} - {result.track.name}"
            self.update_m3u(dest, duration_s=duration_s, label=label)

        return dest

    def update_m3u(
        self,
        audio_path: Path,
        *,
        duration_s: int = -1,
        label: str = "",
    ) -> None:
        """
        Append an #EXTINF entry for *audio_path* to the M3U playlist.

        Creates the M3U (with #EXTM3U header) if it doesn't exist.
        Skips silently if m3u_path is None.

        Parameters
        ----------
        audio_path : absolute path to the audio file
        duration_s : track duration in seconds (-1 = unknown)
        label      : display label in the playlist ("Artist - Title")
        """
        if self.m3u_path is None:
            return

        self.m3u_path.parent.mkdir(parents=True, exist_ok=True)

        # Avoid duplicate entries.
        line_path = str(audio_path.resolve())
        if self.m3u_path.exists():
            existing = self.m3u_path.read_text(encoding="utf-8")
            if line_path in existing:
                log.debug("update_m3u: already present: %s", line_path)
                return

        extinf = f"#EXTINF:{duration_s},{label}\n"
        entry = f"{extinf}{line_path}\n"

        if not self.m3u_path.exists():
            self.m3u_path.write_text(_M3U_HEADER + entry, encoding="utf-8")
            log.debug("update_m3u: created %s", self.m3u_path)
        else:
            with self.m3u_path.open("a", encoding="utf-8") as fh:
                fh.write(entry)
            log.debug("update_m3u: appended %s → %s", audio_path.name, self.m3u_path)

    # ── internal helpers ───────────────────────────────────────────────────────
    def _resolve_dest(self, src: Path) -> Path:
        """Build the destination path inside output_dir preserving the filename."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        return self.output_dir / src.name

    def _move(self, src: Path, dest: Path) -> Path:
        """
        Move *src* to *dest*, handling collisions and cross-device moves.

        Returns the final destination path (may differ from *dest* if a
        collision suffix was applied).
        """
        dest = _unique_dest(dest)
        try:
            # os.rename is atomic on POSIX within the same filesystem.
            os.rename(src, dest)
        except OSError:
            # Cross-device link or other error — fall back to copy + delete.
            shutil.copy2(src, dest)
            src.unlink(missing_ok=True)

        log.debug("organize: moved %s → %s", src.name, dest)
        return dest


# ── module-level helpers ───────────────────────────────────────────────────────
def _unique_dest(path: Path) -> Path:
    """
    Return a path that does not exist, appending ` (N)` before the suffix
    if the original path is already taken.

        /output/Artist - Title.mp3      # taken
        /output/Artist - Title (2).mp3  # next
        /output/Artist - Title (3).mp3  # ...
    """
    if not path.exists():
        return path

    stem = path.stem
    suffix = path.suffix
    parent = path.parent

    for n in range(2, _COLLISION_LIMIT + 2):
        candidate = parent / f"{stem} ({n}){suffix}"
        if not candidate.exists():
            return candidate

    raise FileExistsError(
        f"Could not find a unique name for {path.name} after "
        f"{_COLLISION_LIMIT} attempts"
    )
