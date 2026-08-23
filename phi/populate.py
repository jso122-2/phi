# -*- coding: utf-8 -*-
"""phi.populate — seed state.json with every audio file found on disk.

Run without launching the GUI:

    python -m phi.populate                  # scan DEFAULT_SCAN_DIRS
    python -m phi.populate ~/some/dir       # scan a specific directory
    python -m phi.populate --dry-run        # show what would be added

The script merges new paths into the existing playlist (never removes),
then writes state.json back to disk.  Safe to run while phi is closed;
do NOT run while phi is open (file-lock contention on state.json).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Resolve project root so this runs from any working directory
_HERE = Path(__file__).resolve().parent.parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from phi.config import AUDIO_EXTS, META_DB, STATE_FILE
from phi.discovery import DEFAULT_SCAN_DIRS, _DEFAULT_SKIP, auto_discover, find_audio, summarise


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {}


def _save_state(data: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(data, indent=2))


def _merge(existing: list[str], new: list[str]) -> tuple[list[str], list[str]]:
    """Return (merged_playlist, added_paths)."""
    seen = set(existing)
    added = [p for p in new if p not in seen]
    return existing + added, added


# ---------------------------------------------------------------------------
# Core populate logic
# ---------------------------------------------------------------------------

def populate(
    scan_dirs: list[Path] | None = None,
    *,
    dry_run: bool = False,
    verbose: bool = True,
) -> list[str]:
    """
    Scan *scan_dirs* for audio files, merge into state.json, return added paths.
    """
    dirs = scan_dirs if scan_dirs is not None else DEFAULT_SCAN_DIRS

    if verbose:
        print(f"Scanning {len(dirs)} director{'y' if len(dirs) == 1 else 'ies'}:")
        for d in dirs:
            print(f"  {d}")

    found: list[str] = []
    for d in dirs:
        # When scanning from filesystem root, prune OS/system directories
        skip = _DEFAULT_SKIP if str(d) == "/" else frozenset()
        batch = find_audio(d, skip_prefixes=skip)
        if verbose:
            print(f"  ↳ {len(batch):>4} file(s) in {d.name or str(d)}")
        found.extend(batch)

    # Deduplicate within found list
    seen: set[str] = set()
    unique: list[str] = []
    for p in found:
        if p not in seen:
            seen.add(p)
            unique.append(p)

    if not unique:
        if verbose:
            print("No audio files found.")
        return []

    state = _load_state()
    playlist = state.get("playlist", [])
    merged, added = _merge(playlist, unique)

    if verbose:
        print(f"\nFound   : {len(unique):>5} audio files")
        print(f"Already : {len(playlist):>5} in library")
        print(f"New     : {len(added):>5} to add")

    if not added:
        if verbose:
            print("Library already up to date.")
        return []

    if dry_run:
        if verbose:
            print("\n[dry-run] Would add:")
            for p in added[:20]:
                print(f"  {p}")
            if len(added) > 20:
                print(f"  … and {len(added) - 20} more")
        return added

    state["playlist"] = merged
    _save_state(state)

    if verbose:
        print(f"\n✓ Added {summarise(added)}")
        print(f"  Library now has {len(merged)} tracks.")
        print(f"  State saved to: {STATE_FILE}")

    return added


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="python -m phi.populate",
        description="Seed phi's library with audio files found on disk.",
    )
    parser.add_argument(
        "dirs",
        metavar="DIR",
        nargs="*",
        help="Directories to scan. Defaults to ~/Music, ~/Downloads, "
             "and ~/Projects/spotify-pipeline/data/staging.",
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Report what would be added without writing state.json.",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress progress output.",
    )
    parser.add_argument(
        "--import-playlists",
        action="store_true",
        help="After scanning audio, import original Spotify playlists from "
             "~/Documents/misc/Spotify/Playlists/ into phi's PlaylistStore.",
    )
    parser.add_argument(
        "--playlists-root",
        type=Path,
        default=None,
        metavar="DIR",
        help="Override the Spotify Playlists directory used by --import-playlists.",
    )
    parser.add_argument(
        "--library-json",
        type=Path,
        default=None,
        metavar="FILE",
        help="Override the library.json path used by --import-playlists.",
    )
    args = parser.parse_args(argv)

    scan_dirs: list[Path] | None = None
    if args.dirs:
        scan_dirs = [Path(d).expanduser().resolve() for d in args.dirs]
        missing = [d for d in scan_dirs if not d.is_dir()]
        if missing:
            for m in missing:
                print(f"ERROR: not a directory: {m}", file=sys.stderr)
            sys.exit(1)

    populate(
        scan_dirs=scan_dirs,
        dry_run=args.dry_run,
        verbose=not args.quiet,
    )

    if args.import_playlists:
        from phi.core.playlist_store import PlaylistStore
        from phi.core.spotify_importer import import_spotify_playlists

        if not args.quiet:
            print("\nImporting Spotify playlists…")
        store = PlaylistStore(META_DB)
        result = import_spotify_playlists(
            playlists_root=args.playlists_root,
            library_json=args.library_json,
            store=store,
            dry_run=args.dry_run,
        )
        store.close()
        if not args.quiet:
            print(result.summary())


if __name__ == "__main__":
    main()
