# -*- coding: utf-8 -*-
"""phi.core.session_manager — session persistence (save / restore / annotations)."""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import phi.session as _session_io

if TYPE_CHECKING:
    from phi.core.library import Library
    from phi.core.queue import QueueEngine
    from phi.meta.cache import MetaCache
    from phi.watch.watcher import FolderWatcher


@dataclass
class RestoredSession:
    """Decoded session snapshot before it is applied to app components."""

    playlist: list[str] = field(default_factory=list)
    queue: list[int] = field(default_factory=list)
    queue_pos: int = 0
    shuffle: bool = False           # backward-compat (True ↔ shuffle_mode != "off")
    shuffle_mode: str = "off"       # "off" | "random" | "cairrn"
    repeat: str = "off"
    volume: float = 0.7
    watch_folder: str | None = None
    play_stats: dict = field(default_factory=dict)
    ranker_enabled: bool = True
    picker_enabled: bool = False
    smart_playlists: list[dict] = field(default_factory=list)

    def __post_init__(self) -> None:
        # If only the legacy bool was provided (old session file or direct ctor),
        # derive shuffle_mode from it so callers never see an inconsistency.
        if self.shuffle_mode == "off" and self.shuffle:
            self.shuffle_mode = "random"


class SessionManager:
    """Serialize and deserialize phi session state to/from disk.

    All I/O is delegated to ``phi.session``; this class owns the schema mapping
    between the raw JSON dict and the typed ``RestoredSession`` dataclass.
    """

    def save(
        self,
        library: "Library",
        queue: "QueueEngine",
        transport,
        watcher: "FolderWatcher",
        smart_playlists: list,
        ranker_enabled: bool,
        picker_enabled: bool,
    ) -> None:
        """Persist current session to disk. Raises on I/O error."""
        _session_io.save({
            "playlist":        library.playlist,
            "queue":           queue.queue,
            "queue_pos":       queue.pos,
            "shuffle_mode":    queue.shuffle_mode,
            "shuffle":         queue.shuffle,          # legacy field
            "repeat":          queue.repeat,
            "volume":          transport._vol_var.get(),
            "watch_folder":    watcher.folder,
            "play_stats":      library.play_stats,
            "smart_playlists": [pl.as_dict() for pl in smart_playlists],
            "ranker_enabled":  ranker_enabled,
            "picker_enabled":  picker_enabled,
        })

    def load(self) -> RestoredSession | None:
        """Read persisted session; returns None if absent or empty playlist."""
        data = _session_io.restore()
        if not data:
            return None

        playlist = _session_io.filter_existing(data.get("playlist", []))
        if not playlist:
            return None

        raw_q = [i for i in data.get("queue", []) if i < len(playlist)]
        queue = raw_q if len(raw_q) == len(playlist) else list(range(len(playlist)))
        q_pos = max(0, min(data.get("queue_pos", 0), len(queue) - 1))

        # Merge crash-recovery sidecar (written after every departure) so ELO
        # survives unclean shutdowns.  sidecar keys win: it is always >= state.json.
        play_stats: dict = data.get("play_stats", {})
        sidecar = _session_io.load_play_stats()
        if sidecar:
            play_stats = {**play_stats, **sidecar}

        return RestoredSession(
            playlist=playlist,
            queue=queue,
            queue_pos=q_pos,
            shuffle_mode=data.get("shuffle_mode",
                          "random" if data.get("shuffle", False) else "off"),
            shuffle=data.get("shuffle", False),
            repeat=data.get("repeat", "off"),
            volume=float(data.get("volume", 0.7)),
            watch_folder=data.get("watch_folder"),
            play_stats=play_stats,
            ranker_enabled=bool(data.get("ranker_enabled", True)),
            picker_enabled=bool(data.get("picker_enabled", False)),
            smart_playlists=data.get("smart_playlists", []),
        )

    def restore_annotations_bg(self, library: "Library", meta_cache: "MetaCache") -> None:
        """Spawn daemon thread to bulk-load persisted annotations into *library*."""
        threading.Thread(
            target=self._restore_annotations_worker,
            args=(library, meta_cache),
            daemon=True,
        ).start()

    def _restore_annotations_worker(self, library: "Library", meta_cache: "MetaCache") -> None:
        stored = meta_cache.get_many_annotations(library.playlist)
        for path, ann in stored.items():
            library.annotations[path] = ann
        from phi.core.ranker._learn import fit_from_play_stats, has_checkpoint
        if library.play_stats and not has_checkpoint():
            fit_from_play_stats(library)
        # Fit / load TagEmbedder and write genre_vec + mood_vec to annotations.
        # Runs after stored annotations are loaded so existing CLAP vecs are
        # preserved (TagEmbedder only writes keys that are not already present).
        try:
            from phi.core.ranker._embed import maybe_fit_and_annotate
            maybe_fit_and_annotate(library)
        except Exception:
            pass  # non-fatal — heuristic ranker fallbacks remain

        # Build co-play graph and write phi_rank scores from listening history.
        try:
            from phi.models.coplay_rank import maybe_rank_and_annotate
            maybe_rank_and_annotate(library)
        except Exception:
            pass  # non-fatal — _phi_rank falls back to 0.5

        # Fit CompletionPredictor on historical play data and pre-annotate all tracks
        # with "predicted_completion".  Runs last so genre_vec, mood_vec, phi_rank
        # are already written (they are features of the Ridge regression).
        # TrackRanker.score() reads predicted_completion first; falls back to
        # heuristic weighted sum when this annotation is absent.
        try:
            from phi.models.completion_predictor import maybe_predict_and_annotate
            maybe_predict_and_annotate(library)
        except Exception:
            pass  # non-fatal — heuristic ranker fallback remains active

    def flush_annotations(self, library: "Library", meta_cache: "MetaCache") -> None:
        """Flush in-memory annotations to SQLite. Safe to call at any time."""
        meta_cache.put_many_annotations(library.annotations)
