"""phi._track — Track dataclass and key constants."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

CHROMATIC_KEYS: tuple[str, ...] = (
    "C", "C#", "D", "D#", "E", "F",
    "F#", "G", "G#", "A", "A#", "B",
)


@dataclass
class Track:
    """One music track — audio path + rich JSON metadata."""
    path: Path
    json_path: Path

    name: str = ""
    artist: str = ""
    album: str = ""
    year: str = ""
    spotify_id: str = ""
    explicit: bool = False

    duration_s: float = 0.0
    key: str = ""
    key_camelot: str = ""
    key_confidence: float = 0.0

    lfm_tags: list[str] = field(default_factory=list)
    lfm_playcount: int = 0
    lfm_listeners: int = 0

    itunes_genre: str = ""
    discogs_genre: list[str] = field(default_factory=list)
    discogs_style: list[str] = field(default_factory=list)

    clap_npy: Optional[Path] = None

    # Spotify playlist IDs this track appears in (populated at load time
    # when the track lives under a Playlists/<spotify_id>/ directory).
    spotify_playlists: list[str] = field(default_factory=list)

    @property
    def stem(self) -> str:
        return self.path.stem

    @property
    def display_name(self) -> str:
        if self.name and self.artist:
            return f"{self.artist} — {self.name}"
        return self.path.stem

    @property
    def all_tags(self) -> list[str]:
        """Combined tag list: lfm + discogs genre/style + itunes."""
        tags = list(self.lfm_tags)
        tags.extend(self.discogs_genre)
        tags.extend(self.discogs_style)
        if self.itunes_genre:
            tags.append(self.itunes_genre)
        return list(dict.fromkeys(t.lower().strip() for t in tags if t))

    def __hash__(self) -> int:
        return hash(str(self.path))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Track):
            return NotImplemented
        return self.path == other.path
