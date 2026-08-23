"""Listening-session snapshot used to score candidates."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

from ._constants import SESSION_WINDOW
from ._scoring import _plurality

if TYPE_CHECKING:
    from phi.core.library import Library


@dataclass
class RankContext:
    """Last-window genre/mood/tags plus recent paths."""

    recent_paths: list[str] = field(default_factory=list)
    session_genre: str | None = None
    session_mood: str | None = None
    session_tags: list[str] = field(default_factory=list)
    session_valence: float | None = None
    session_energy: float | None = None
    time_of_day: str = "afternoon"

    @classmethod
    def from_library(
        cls,
        library: "Library",
        current_path: str | None,
        window: int = SESSION_WINDOW,
        exclude: str | None = None,
    ) -> "RankContext":
        """Build context from the last *window* played tracks.

        *exclude* is omitted from the window (use when scoring the track
        that just departed so it does not become its own session match).
        """
        played = [
            (p, s.get("last_played", ""))
            for p, s in library.play_stats.items()
            if s.get("last_played") and p in library.meta_cache and p != exclude
        ]
        played.sort(key=lambda t: t[1], reverse=True)
        recent = [p for p, _ in played[:window]]

        genres: list[str] = []
        moods: list[str] = []
        all_tags: list[str] = []
        valences: list[float] = []
        energies: list[float] = []

        for p in recent:
            meta = library.meta_cache.get(p) or {}
            ann = library.annotations.get(p) or {}
            g = meta.get("genre") or ann.get("genre")
            if g:
                genres.append(str(g).lower())
            for t in (ann.get("mb_genres") or []) + (ann.get("lfm_tags") or []):
                if t:
                    all_tags.append(str(t).lower())
            m = ann.get("spotify_mood") or ann.get("mood") or meta.get("mood")
            if m:
                moods.append(str(m).lower())
            v = ann.get("spotify_valence")
            e = ann.get("spotify_energy")
            if v is not None:
                valences.append(float(v))
            if e is not None:
                energies.append(float(e))

        seen: set[str] = set()
        deduped: list[str] = []
        for t in all_tags:
            if t not in seen:
                seen.add(t)
                deduped.append(t)

        hour = datetime.now().hour
        if hour < 6 or hour >= 22:
            tod = "night"
        elif hour < 12:
            tod = "morning"
        elif hour < 18:
            tod = "afternoon"
        else:
            tod = "evening"

        ctx = cls(
            recent_paths=recent,
            session_genre=_plurality(genres),
            session_mood=_plurality(moods),
            session_tags=deduped,
            session_valence=sum(valences) / len(valences) if valences else None,
            session_energy=sum(energies) / len(energies) if energies else None,
            time_of_day=tod,
        )

        # Attach continuous session vectors when the TagEmbedder is ready.
        # These are read by _genre_affinity / _mood_affinity via __dict__.get().
        try:
            from ._embed import session_vecs
            gv, mv = session_vecs(recent, library)
            if gv:
                ctx._session_genre_vec = gv  # type: ignore[attr-defined]
            if mv:
                ctx._session_mood_vec = mv   # type: ignore[attr-defined]
        except Exception:
            pass  # embedder not ready — heuristic fallbacks remain active

        return ctx
