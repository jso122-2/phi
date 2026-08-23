"""
PhiLibrary — scans the Liked Songs library for Track pairs (.mp3 + .json).

Library root: /Users/a0/Documents/misc/Spotify/Liked Songs/
Each track is a pair:
    <name>.mp3      — audio file
    <name>.json     — enriched metadata (Spotify + Last.fm + Discogs + iTunes)

JSON schema fields used by phi:
    name, artist, album, year, duration_s
    key, key_camelot, key_confidence
    lfm_tags (list[str]), lfm_playcount (int), lfm_listeners (int)
    itunes_genre (str), discogs_genre (list), discogs_style (list)
    explicit (bool), spotify_id (str)
    _audio_path (str, optional — may differ from actual .mp3 path)

Default organisation
--------------------
``PhiLibrary.by_genre()`` is the default view of the library — it groups all
tracks by XGBoost-predicted genre cluster.  Use it as the entry point when
building any library UI or downstream pipeline that needs genre structure:

    lib = PhiLibrary()
    grouped = lib.by_genre()          # dict[genre_label, list[Track]]
    techno  = lib.by_genre("techno")  # list[Track] — single genre
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING

from phi._loader import _load_track
from phi._track import CHROMATIC_KEYS, Track

if TYPE_CHECKING:
    from models.genre_predictor import GenrePredictor

__all__ = ["LIBRARY_ROOT", "CHROMATIC_KEYS", "Track", "PhiLibrary", "_load_track"]

LIBRARY_ROOT: Path = Path("/Users/a0/Documents/misc/Spotify/Liked Songs")


class PhiLibrary:
    """
    Scans a directory for (.mp3 / .flac / .wav) + .json pairs.

    Parameters
    ----------
    library_root : directory containing audio + JSON pairs (default: LIBRARY_ROOT)
    """

    AUDIO_EXTS: frozenset[str] = frozenset({".mp3", ".flac", ".wav", ".m4a", ".ogg"})

    def __init__(self, library_root: Path = LIBRARY_ROOT) -> None:
        self.library_root = Path(library_root)
        self._tracks: list[Track] = []
        self._scanned: bool = False

    def scan(self) -> int:
        """
        Discover all audio+JSON pairs in library_root.

        Returns
        -------
        int  number of tracks loaded
        """
        self._tracks.clear()
        for audio_path in sorted(self.library_root.iterdir()):
            if audio_path.suffix.lower() not in self.AUDIO_EXTS:
                continue
            json_path = audio_path.with_suffix(".json")
            if not json_path.exists():
                self._tracks.append(Track(path=audio_path, json_path=json_path))
                continue
            self._tracks.append(_load_track(audio_path, json_path))
        self._scanned = True
        return len(self._tracks)

    @property
    def tracks(self) -> list[Track]:
        if not self._scanned:
            self.scan()
        return list(self._tracks)

    def __len__(self) -> int:
        return len(self.tracks)

    def __getitem__(self, idx: int) -> Track:
        return self.tracks[idx]

    def by_artist(self, artist: str) -> list[Track]:
        a = artist.lower()
        return [t for t in self.tracks if a in t.artist.lower()]

    def by_tag(self, tag: str) -> list[Track]:
        t = tag.lower()
        return [tr for tr in self.tracks if any(t == x.lower() for x in tr.lfm_tags)]

    def by_genre(
        self,
        genre: str | None = None,
        *,
        predictor: GenrePredictor | None = None,
    ) -> dict[str, list[Track]] | list[Track]:
        """
        Default genre-bound organisation of the library.

        Uses the trained XGBoost cluster model (via ``GenrePredictor``) to
        assign every track a genre label derived from its dominant tag cluster.

        Parameters
        ----------
        genre : str | None
            • ``None``  — return all tracks grouped as ``dict[genre_label, list[Track]]``
            • str       — return ``list[Track]`` matching that genre label exactly

        predictor : GenrePredictor | None
            Pass an already-constructed predictor to avoid reloading the model
            on repeated calls.  A fresh ``GenrePredictor(self)`` is built when
            ``None`` (the common case).

        Examples
        --------
        >>> lib = PhiLibrary()
        >>> grouped = lib.by_genre()              # all tracks, genre-grouped
        >>> techno  = lib.by_genre("techno")      # one genre slice
        >>> lib.by_genre(predictor=my_pred)       # reuse warm predictor
        """
        from models.genre_predictor import GenrePredictor as _GenrePredictor

        if predictor is None and not _GenrePredictor.artifacts_ready():
            return self._genre_groups_from_tags(genre)

        pred = predictor if predictor is not None else _GenrePredictor(self)

        if genre is not None:
            target = genre.lower()
            return [t for t in self.tracks if pred.genre_for(t).lower() == target]

        groups: dict[str, list[Track]] = {}
        for track in self.tracks:
            label = pred.genre_for(track)
            groups.setdefault(label, []).append(track)
        return groups

    def _genre_groups_from_tags(
        self,
        genre: str | None,
    ) -> dict[str, list[Track]] | list[Track]:
        """Fallback when XGBoost cluster artefacts are absent."""
        def _label(track: Track) -> str:
            if track.itunes_genre:
                return track.itunes_genre.lower()
            if track.discogs_genre:
                return str(track.discogs_genre[0]).lower()
            if track.lfm_tags:
                return track.lfm_tags[0].lower()
            return "untagged"

        if genre is not None:
            target = genre.lower()
            return [t for t in self.tracks if _label(t) == target]

        groups: dict[str, list[Track]] = {}
        for track in self.tracks:
            groups.setdefault(_label(track), []).append(track)
        return groups

    def tag_vocabulary(self, top_k: int = 256) -> list[str]:
        """Return the top-k most common lfm_tags across the library, by frequency."""
        c: Counter = Counter()
        for track in self.tracks:
            c.update(tag.lower() for tag in track.lfm_tags)
        return [tag for tag, _ in c.most_common(top_k)]

    def __repr__(self) -> str:
        n = len(self._tracks) if self._scanned else "?"
        return f"<PhiLibrary root={self.library_root.name!r} tracks={n}>"
