# -*- coding: utf-8 -*-
"""phi.discovery — automatic music library ingestion.

Scans the system's standard music locations for audio files and reports
what it finds.  Designed to be called once on first launch (empty library)
and optionally on a background thread thereafter.

Discovery is purely read-only: it returns paths and never touches the
Library or QueueEngine directly — that stays the caller's job.
"""
from __future__ import annotations
import os
from pathlib import Path

from phi.config import AUDIO_EXTS

# Directories scanned in order.  Subdirectories are walked recursively.
# Hidden dirs (name starts with '.') are always skipped.
_EXTRA_SCAN_DIRS: list[Path] = [
    Path.home() / "Documents" / "misc" / "Spotify",
    Path.home() / "Documents" / "misc" / "Projects" / "spotify-pipeline" / "data" / "staging",
    Path.home() / "Projects" / "spotify-pipeline" / "data" / "staging",
    Path.home() / "Desktop",
]

DEFAULT_SCAN_DIRS: list[Path] = [
    Path.home() / "Music",
    Path.home() / "Downloads",
    *[d for d in _EXTRA_SCAN_DIRS if d.is_dir()],
]

# Hard cap so a rogue scan of / doesn't hang forever.
MAX_FILES = 50_000


_DEFAULT_SKIP: frozenset[str] = frozenset({
    "/System",
    "/Library",
    "/private",
    "/dev",
    "/proc",
    "/sbin",
    "/bin",
    "/usr",
    "/etc",
    "/tmp",
    "/var",
    "/cores",
    "/opt/homebrew/Cellar",   # homebrew internals, not music
})


def find_audio(
    directory: Path,
    *,
    recursive: bool = True,
    skip_prefixes: frozenset[str] | None = None,
) -> list[str]:
    """
    Return sorted absolute paths of all audio files under *directory*.
    Returns [] if the directory doesn't exist.

    *skip_prefixes*: absolute path prefixes to prune during the walk.
    When scanning from /, pass _DEFAULT_SKIP to avoid system dirs.
    """
    if not directory.is_dir():
        return []

    skip = skip_prefixes if skip_prefixes is not None else frozenset()
    found: list[str] = []

    if recursive:
        for root, dirs, files in os.walk(str(directory)):
            # Skip hidden dirs and any user-supplied prefix paths
            dirs[:] = sorted(
                d for d in dirs
                if not d.startswith(".")
                and not any(
                    os.path.join(root, d).startswith(pfx) for pfx in skip
                )
            )
            for fname in sorted(files):
                if os.path.splitext(fname)[1].lower() in AUDIO_EXTS:
                    found.append(os.path.join(root, fname))
                    if len(found) >= MAX_FILES:
                        return found
    else:
        for fname in sorted(os.listdir(str(directory))):
            if os.path.splitext(fname)[1].lower() in AUDIO_EXTS:
                found.append(str(directory / fname))

    return found


def auto_discover(
    dirs: list[Path] | None = None,
    *,
    recursive: bool = True,
) -> list[str]:
    """
    Scan *dirs* (defaults to DEFAULT_SCAN_DIRS) and return all audio paths,
    deduped and sorted.
    """
    if dirs is None:
        dirs = DEFAULT_SCAN_DIRS

    seen:   set[str]  = set()
    result: list[str] = []
    for d in dirs:
        for p in find_audio(d, recursive=recursive):
            if p not in seen:
                seen.add(p)
                result.append(p)

    return result


def summarise(paths: list[str]) -> str:
    """Return a human-readable summary: '42 tracks across 3 folders'."""
    folders = {os.path.dirname(p) for p in paths}
    n = len(paths)
    f = len(folders)
    return f"{n} track{'s' if n != 1 else ''} across {f} folder{'s' if f != 1 else ''}"
