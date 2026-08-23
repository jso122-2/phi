# -*- coding: utf-8 -*-
"""phi.core.library — track collection, metadata cache, and organisation tools."""
from __future__ import annotations
import os
from collections import defaultdict
from datetime import datetime
from typing import Iterator

from phi.config import fmt_time


class Library:
    """
    Central store for the track collection.

    Attributes
    ----------
    playlist     : ordered list of absolute paths (insertion order)
    meta_cache   : path → tag dict (title, artist, album, year, duration, art_bytes, …)
    annotations  : path → model annotation dict (bpm, key, mood, embedding, …)
                   Written by phi.models.* — never read by core playback logic.
    """

    def __init__(self) -> None:
        self.playlist:    list[str]        = []
        self.meta_cache:  dict[str, dict]  = {}
        self.annotations: dict[str, dict]  = {}   # model output store
        self.play_stats:  dict[str, dict]  = {}   # path → {plays, last_played, rating, added}

    # ── mutation ───────────────────────────────────────────────────────────────

    def add(self, paths: list[str]) -> list[str]:
        """Add paths not already in the library. Returns newly added paths."""
        added: list[str] = []
        now = datetime.now().isoformat()
        for p in paths:
            if p not in self.playlist:
                self.playlist.append(p)
                added.append(p)
                # Record the add timestamp so smart playlists can filter by "added:7d"
                self.play_stats.setdefault(p, {})["added"] = self.play_stats.get(p, {}).get("added", now)
        return added

    def remove_by_playlist_indices(self, indices: list[int]) -> list[str]:
        removed: list[str] = []
        for i in sorted(set(indices), reverse=True):
            if 0 <= i < len(self.playlist):
                path = self.playlist.pop(i)
                self.meta_cache.pop(path, None)
                self.annotations.pop(path, None)
                # Keep play_stats intentionally — re-adding the file should
                # restore its history rather than resetting it.
                removed.append(path)
        return removed

    def remove_missing(self) -> list[str]:
        missing = [p for p in self.playlist if not os.path.isfile(p)]
        for p in missing:
            self.playlist.remove(p)
            self.meta_cache.pop(p, None)
            self.annotations.pop(p, None)
        return missing

    def deduplicate(self) -> int:
        seen:   set[str]  = set()
        unique: list[str] = []
        for p in self.playlist:
            if p not in seen:
                seen.add(p)
                unique.append(p)
        removed = len(self.playlist) - len(unique)
        self.playlist = unique
        return removed

    def clear(self) -> None:
        self.playlist.clear()
        self.meta_cache.clear()
        self.annotations.clear()
        self.play_stats.clear()

    # ── metadata ───────────────────────────────────────────────────────────────

    def store_meta(self, path: str, meta: dict) -> None:
        self.meta_cache[path] = meta

    def get_meta(self, path: str) -> dict | None:
        return self.meta_cache.get(path)

    def store_annotation(self, path: str, data: dict) -> None:
        """Merge model output *data* into the annotation store for *path*."""
        if path not in self.annotations:
            self.annotations[path] = {}
        self.annotations[path].update(data)

    def get_annotation(self, path: str) -> dict:
        return self.annotations.get(path, {})

    # ── play stats ─────────────────────────────────────────────────────────────

    def record_play(self, path: str) -> None:
        """Increment play count and update last-played timestamp."""
        s = self.play_stats.setdefault(path, {})
        s["plays"]       = s.get("plays", 0) + 1
        s["last_played"] = datetime.now().isoformat()

    def record_play_progress(self, path: str, seconds_played: float) -> None:
        """
        Accumulate *seconds_played* for the current listen session.

        Also updates completion_rate as a rolling average:
            new_rate = (old_rate * (plays-1) + fraction) / plays
        """
        s = self.play_stats.setdefault(path, {})
        s["played_seconds"] = s.get("played_seconds", 0.0) + max(0.0, seconds_played)

        meta = self.meta_cache.get(path) or {}
        duration = float(meta.get("duration") or 0)
        if duration > 0:
            fraction = min(1.0, seconds_played / duration)
            plays    = max(1, s.get("plays", 1))
            old_rate = s.get("completion_rate", 0.0)
            s["completion_rate"] = (old_rate * (plays - 1) + fraction) / plays

    def record_skip(self, path: str) -> None:
        """
        Record a skip event (user moved away before 30% completion).
        Call this from the player before advancing when skip conditions are met.
        """
        s = self.play_stats.setdefault(path, {})
        s["skip_count"] = s.get("skip_count", 0) + 1

    def set_rating(self, path: str, stars: int) -> None:
        """Set star rating (0–5) for *path*."""
        s = self.play_stats.setdefault(path, {})
        s["rating"] = max(0, min(5, int(stars)))

    def get_elo(self, path: str) -> float:
        """Return the ELO score for *path* (default 1500)."""
        return float(self.play_stats.get(path, {}).get("elo_score", 1500.0))

    def set_elo(self, path: str, score: float) -> None:
        """Store an updated ELO score for *path*."""
        s = self.play_stats.setdefault(path, {})
        s["elo_score"] = round(score, 2)

    def get_stats(self, path: str) -> dict:
        """Return the stats dict for *path* (always a dict, never None)."""
        return self.play_stats.get(path, {})

    def top_played(self, n: int = 30) -> list[str]:
        """Paths sorted by descending play count, limited to *n*."""
        scored = [(p, self.play_stats.get(p, {}).get("plays", 0))
                  for p in self.playlist]
        scored.sort(key=lambda t: -t[1])
        return [p for p, _ in scored if _ > 0][:n]

    def top_rated(self, n: int = 30) -> list[str]:
        """Paths with a rating > 0, sorted by descending rating then plays."""
        scored = [
            (p, self.play_stats.get(p, {}).get("rating", 0),
                self.play_stats.get(p, {}).get("plays", 0))
            for p in self.playlist
            if self.play_stats.get(p, {}).get("rating", 0) > 0
        ]
        scored.sort(key=lambda t: (-t[1], -t[2]))
        return [p for p, _, __ in scored][:n]

    def never_heard(self) -> list[str]:
        """Paths that have never been played."""
        return [p for p in self.playlist
                if self.play_stats.get(p, {}).get("plays", 0) == 0]

    def recently_added(self, n: int = 30) -> list[str]:
        """Paths sorted by add-time (most recent first)."""
        def key(p: str) -> str:
            return self.play_stats.get(p, {}).get("added", "")
        return sorted(self.playlist, key=key, reverse=True)[:n]

    def stars_str(self, path: str) -> str:
        """Return a 5-char star string like ★★★☆☆."""
        r = self.play_stats.get(path, {}).get("rating", 0)
        return "★" * r + "☆" * (5 - r)

    # ── library index queries ──────────────────────────────────────────────────

    def artists(self) -> list[str]:
        """Sorted unique artist names (tracks with no artist → 'Unknown Artist')."""
        names: set[str] = set()
        for p in self.playlist:
            m = self.meta_cache.get(p)
            names.add((m or {}).get("artist") or "Unknown Artist")
        return sorted(names)

    def albums(self) -> list[tuple[str, str, str]]:
        """
        Sorted unique (artist, album, year) triples.
        Unknown values substituted with readable defaults.
        """
        triples: set[tuple[str, str, str]] = set()
        for p in self.playlist:
            m = self.meta_cache.get(p) or {}
            triples.add((
                m.get("artist") or "Unknown Artist",
                m.get("album")  or "Unknown Album",
                m.get("year")   or "",
            ))
        return sorted(triples)

    def tracks_by_artist(self, artist: str) -> list[str]:
        """Ordered paths for all tracks by *artist*."""
        return [
            p for p in self.playlist
            if ((self.meta_cache.get(p) or {}).get("artist") or "Unknown Artist") == artist
        ]

    def tracks_by_album(self, artist: str, album: str) -> list[str]:
        """Paths for all tracks on a specific album, sorted by track number."""
        tracks = [
            p for p in self.playlist
            if (m := self.meta_cache.get(p))
            and (m.get("artist") or "Unknown Artist") == artist
            and (m.get("album")  or "Unknown Album")  == album
        ]
        tracks.sort(key=lambda p: (
            int((self.meta_cache.get(p) or {}).get("track") or 0) or 999,
            os.path.basename(p).lower(),
        ))
        return tracks

    def artist_stats(self, artist: str) -> dict:
        """
        Return {tracks, albums, duration} for an artist.
        """
        tracks  = self.tracks_by_artist(artist)
        al_set: set[str] = set()
        dur     = 0.0
        for p in tracks:
            m = self.meta_cache.get(p) or {}
            al_set.add(m.get("album") or "Unknown Album")
            dur += float(m.get("duration") or 0)
        return {"tracks": len(tracks), "albums": len(al_set), "duration": dur}

    def album_stats(self, artist: str, album: str) -> dict:
        tracks = self.tracks_by_album(artist, album)
        dur    = sum(float((self.meta_cache.get(p) or {}).get("duration") or 0)
                     for p in tracks)
        return {"tracks": len(tracks), "duration": dur}

    def tracks_annotated_with(self, key: str) -> list[str]:
        """Paths whose model annotation has *key* set."""
        return [p for p, ann in self.annotations.items() if key in ann]

    # ── display helpers ────────────────────────────────────────────────────────

    def display_name(self, path: str) -> str:
        meta = self.meta_cache.get(path)
        if meta:
            artist = meta.get("artist")
            title  = meta.get("title")
            if artist and title:
                return f"{artist} — {title}"
            if title:
                return title
        return os.path.splitext(os.path.basename(path))[0]

    def playlist_index(self, path: str) -> int | None:
        """Return index of *path* in playlist, or None if absent."""
        try:
            return self.playlist.index(path)
        except ValueError:
            return None

    # ── stats ──────────────────────────────────────────────────────────────────

    @property
    def size(self) -> int:
        return len(self.playlist)

    def total_duration(self) -> float:
        total = 0.0
        for p in self.playlist:
            meta = self.meta_cache.get(p)
            if meta:
                dur = meta.get("duration")
                if dur:
                    total += float(dur)
        return total

    def stats_str(self) -> str:
        n   = self.size
        dur = self.total_duration()
        trk = f"{n} track{'s' if n != 1 else ''}"
        if dur < 1:
            return trk
        h = int(dur) // 3600
        m = (int(dur) % 3600) // 60
        return f"{trk} · {h}h {m}m" if h else f"{trk} · {m}m"

    def path_at(self, playlist_idx: int) -> str:
        return self.playlist[playlist_idx]

    def all_display_names_by_queue(self, queue: list[int]) -> list[str]:
        return [self.display_name(self.playlist[qi]) for qi in queue]
