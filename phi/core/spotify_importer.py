# -*- coding: utf-8 -*-
"""phi.core.spotify_importer — import original Spotify playlists into phi.

Reads the downloaded Spotify library layout:

    <spotify_root>/
        library.json                    ← playlist metadata index
        Playlists/
            <spotify_playlist_id>/      ← one dir per downloaded playlist
                Artist - Title.mp3
                Artist - Title.json
                …

Each ``<spotify_playlist_id>/`` directory is matched to its human-readable
name and owner via ``library.json``, then upserted into ``PlaylistStore`` so
the original Spotify playlist structure is preserved inside phi.

Usage
-----
    from phi.core.spotify_importer import import_spotify_playlists
    from phi.core.playlist_store import PlaylistStore
    from pathlib import Path

    store = PlaylistStore(Path("~/.phi/meta.db").expanduser())
    result = import_spotify_playlists(
        playlists_root=Path("/Users/a0/Documents/misc/Spotify/Playlists"),
        library_json=Path("/Users/a0/Documents/misc/Spotify/library.json"),
        store=store,
    )
    print(result)

CLI
---
    python -m phi.core.spotify_importer [--dry-run]
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

AUDIO_EXTS: frozenset[str] = frozenset({".mp3", ".flac", ".wav", ".m4a", ".ogg"})

DEFAULT_SPOTIFY_ROOT = Path("/Users/a0/Documents/misc/Spotify")


@dataclass
class ImportResult:
    created:  list[str] = field(default_factory=list)   # playlist names created
    updated:  list[str] = field(default_factory=list)   # playlist names refreshed
    skipped:  list[str] = field(default_factory=list)   # dirs with no known metadata
    empty:    list[str] = field(default_factory=list)   # dirs with no audio files

    @property
    def total(self) -> int:
        return len(self.created) + len(self.updated)

    def summary(self) -> str:
        lines = [
            f"Spotify playlist import: {self.total} playlist(s) synced",
            f"  created : {len(self.created)}",
            f"  updated : {len(self.updated)}",
        ]
        if self.empty:
            lines.append(f"  empty   : {len(self.empty)} (no audio files)")
        if self.skipped:
            lines.append(f"  skipped : {len(self.skipped)} (not in library.json)")
        return "\n".join(lines)


def _load_library_index(library_json: Path) -> dict[str, dict]:
    """Return {spotify_id: {name, owner, …}} from library.json."""
    try:
        data = json.loads(library_json.read_text(encoding="utf-8"))
    except Exception as exc:
        raise FileNotFoundError(
            f"Cannot read library.json at {library_json}: {exc}"
        ) from exc

    index: dict[str, dict] = {}
    for entry in data.get("playlists", []):
        pid = entry.get("playlist_id", "").strip()
        if pid:
            index[pid] = entry
    return index


def _collect_audio_paths(playlist_dir: Path) -> list[str]:
    """Return sorted absolute audio file paths inside *playlist_dir*."""
    paths = sorted(
        str(p)
        for p in playlist_dir.iterdir()
        if p.is_file() and p.suffix.lower() in AUDIO_EXTS
    )
    return paths


def import_spotify_playlists(
    playlists_root: Path | None = None,
    library_json: Path | None = None,
    store=None,
    *,
    dry_run: bool = False,
) -> ImportResult:
    """
    Scan *playlists_root* for Spotify playlist directories and upsert each one
    into *store* (a :class:`~phi.core.playlist_store.PlaylistStore`).

    Parameters
    ----------
    playlists_root : directory containing ``<spotify_id>/`` subdirectories.
                     Defaults to ``~/Documents/misc/Spotify/Playlists``.
    library_json   : path to ``library.json`` with playlist metadata.
                     Defaults to ``~/Documents/misc/Spotify/library.json``.
    store          : a ``PlaylistStore`` instance.  When *None* a default one
                     is constructed at ``~/.phi/meta.db``.
    dry_run        : if True, report what would happen without writing.
    """
    if playlists_root is None:
        playlists_root = DEFAULT_SPOTIFY_ROOT / "Playlists"
    if library_json is None:
        library_json = DEFAULT_SPOTIFY_ROOT / "library.json"
    if store is None:
        from phi.core.playlist_store import PlaylistStore
        from phi.config import META_DB
        store = PlaylistStore(META_DB)

    index = _load_library_index(library_json)
    result = ImportResult()

    if not playlists_root.is_dir():
        return result

    for playlist_dir in sorted(playlists_root.iterdir()):
        if not playlist_dir.is_dir():
            continue

        spotify_id = playlist_dir.name
        meta = index.get(spotify_id)

        if meta is None:
            result.skipped.append(spotify_id)
            continue

        name  = meta.get("name", spotify_id).strip() or spotify_id
        owner = meta.get("owner", "").strip()
        paths = _collect_audio_paths(playlist_dir)

        if not paths:
            result.empty.append(name)
            continue

        if dry_run:
            existing = store.by_spotify_id(spotify_id)
            action = "update" if existing else "create"
            print(f"  [{action}] {name!r}  ({len(paths)} tracks)  [{spotify_id}]")
            if existing:
                result.updated.append(name)
            else:
                result.created.append(name)
            continue

        _pid, created = store.upsert_spotify_playlist(spotify_id, name, owner, paths)
        if created:
            result.created.append(name)
        else:
            result.updated.append(name)

    return result


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    import argparse

    parser = argparse.ArgumentParser(
        prog="python -m phi.core.spotify_importer",
        description="Import original Spotify playlists into phi's PlaylistStore.",
    )
    parser.add_argument(
        "--playlists-root",
        type=Path,
        default=None,
        help=f"Directory of <spotify_id>/ playlist folders "
             f"(default: {DEFAULT_SPOTIFY_ROOT / 'Playlists'})",
    )
    parser.add_argument(
        "--library-json",
        type=Path,
        default=None,
        help=f"Path to library.json (default: {DEFAULT_SPOTIFY_ROOT / 'library.json'})",
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Show what would be imported without writing anything.",
    )
    args = parser.parse_args(argv)

    result = import_spotify_playlists(
        playlists_root=args.playlists_root,
        library_json=args.library_json,
        dry_run=args.dry_run,
    )
    print(result.summary())
    if result.skipped:
        print(f"\n  Skipped IDs (not in library.json): {', '.join(result.skipped[:5])}"
              + (f" … +{len(result.skipped) - 5} more" if len(result.skipped) > 5 else ""))


if __name__ == "__main__":
    main()
