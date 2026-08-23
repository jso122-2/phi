"""phi._loader — JSON metadata parser for Track construction."""
from __future__ import annotations

import json
from pathlib import Path

from phi._track import Track

# Marker directory name that indicates a Spotify playlist subtree.
# Layout: <SPOTIFY_ROOT>/Playlists/<spotify_playlist_id>/<track>.mp3
_PLAYLISTS_DIR = "Playlists"


def _infer_spotify_playlists(audio_path: Path) -> list[str]:
    """
    If *audio_path* lives under a ``Playlists/<spotify_id>/`` directory,
    return ``[spotify_id]``; otherwise return an empty list.
    """
    parts = audio_path.parts
    for i, part in enumerate(parts):
        if part == _PLAYLISTS_DIR and i + 1 < len(parts):
            return [parts[i + 1]]
    return []


def _load_track(audio_path: Path, json_path: Path) -> Track:
    """Parse a JSON metadata file and return a fully-populated Track."""
    try:
        with json_path.open(encoding="utf-8") as f:
            d = json.load(f)
    except Exception:
        return Track(path=audio_path, json_path=json_path)

    clap_npy = audio_path.with_suffix(".npy")
    clap_npy = clap_npy if clap_npy.exists() else None

    def _float(v, default: float = 0.0) -> float:
        try:
            return float(v)
        except (TypeError, ValueError):
            return default

    def _int(v, default: int = 0) -> int:
        try:
            return int(v)
        except (TypeError, ValueError):
            return default

    def _list(v) -> list:
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            return [v]
        return []

    return Track(
        path=audio_path,
        json_path=json_path,
        name=str(d.get("name", audio_path.stem)),
        artist=str(d.get("artist", "")),
        album=str(d.get("album", "")),
        year=str(d.get("year", "")),
        spotify_id=str(d.get("spotify_id", "")),
        explicit=bool(d.get("explicit", False)),
        duration_s=_float(d.get("duration_s")),
        key=str(d.get("key", "")),
        key_camelot=str(d.get("key_camelot", "")),
        key_confidence=_float(d.get("key_confidence")),
        lfm_tags=_list(d.get("lfm_tags")),
        lfm_playcount=_int(d.get("lfm_playcount")),
        lfm_listeners=_int(d.get("lfm_listeners")),
        itunes_genre=str(d.get("itunes_genre", "")),
        discogs_genre=_list(d.get("discogs_genre")),
        discogs_style=_list(d.get("discogs_style")),
        clap_npy=clap_npy,
        spotify_playlists=_infer_spotify_playlists(audio_path),
    )
