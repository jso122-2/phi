# -*- coding: utf-8 -*-
"""phi.ui._app._queue_ops — queue mutation callbacks."""
from __future__ import annotations


class _QueueOpsMixin:
    """Queue-level operations: play/activate/remove/sort/search."""

    def on_play_album(self, paths: list[str], start_path: str | None = None) -> None:
        """
        Scope the queue to these album tracks (in the given order) and play.

        Replaces queue.queue with the album's playlist indices so that
        advance() / next_user() step through the album in order rather than
        jumping to wherever the track sits in the full-library queue.

        Parameters
        ----------
        paths      : album track paths in desired play order (track number order)
        start_path : the specific track to start from; defaults to paths[0]
        """
        # Ensure all tracks are in the library
        self.library.add(paths)

        # Resolve playlist indices, preserving the caller's order
        album_pl_indices: list[int] = []
        seen: set[int] = set()
        for p in paths:
            idx = self.library.playlist_index(p)
            if idx is not None and idx not in seen:
                album_pl_indices.append(idx)
                seen.add(idx)

        if not album_pl_indices:
            return

        # Scope the queue to just these tracks
        self.queue.queue = album_pl_indices

        # Position at start_path, or the first track
        start_pl_idx: int | None = None
        if start_path is not None:
            start_pl_idx = self.library.playlist_index(start_path)

        if start_pl_idx is not None and start_pl_idx in album_pl_indices:
            self.queue.pos = album_pl_indices.index(start_pl_idx)
        else:
            self.queue.pos = 0

        self._rebuild_view()
        self._load_and_play(self.queue.pos)

    def on_play_path(self, path: str) -> None:
        """Play a specific absolute path — used by Album/Artist tab double-click."""
        playlist_idx = self.library.playlist_index(path)
        if playlist_idx is None:
            return
        for queue_pos, pl_idx in enumerate(self.queue.queue):
            if pl_idx == playlist_idx:
                self.playback.load_and_play(queue_pos)
                return
        self.library.add([path])
        self.queue.rebuild(self.library.size, keep_current=True)
        self._rebuild_view()
        for queue_pos, pl_idx in enumerate(self.queue.queue):
            if pl_idx == playlist_idx:
                self.playback.load_and_play(queue_pos)
                return

    def on_activate(self, view_idx: int) -> None:
        if 0 <= view_idx < len(self.queue.view):
            self.playback.load_and_play(self.queue.view[view_idx])

    def on_swap(self, va: int, vb: int) -> None:
        self.queue.swap_view_rows(va, vb)
        self._refresh_playlist()

    def on_remove(self, view_indices: list[int]) -> None:
        if not view_indices:
            return
        current_playlist_idx = self.queue.current_playlist_idx
        playing_path = (self.library.playlist[current_playlist_idx]
                        if current_playlist_idx >= 0 else None)
        playlist_indices = [self.queue.queue[self.queue.view[vi]] for vi in view_indices]
        removed = self.library.remove_by_playlist_indices(playlist_indices)
        if playing_path in removed:
            self.player.stop()
            self.transport.set_playing(False)
            self.queue.pos = -1
        self.queue.rebuild(self.library.size, keep_current=True)
        self._rebuild_view()

    def on_play_next(self, view_idx: int) -> None:
        """Move the selected track (by view index) to play immediately after current."""
        self.queue.move_to_next(view_idx)
        self._rebuild_view()
        self._flash(">| Queued next")

    def on_play_next_path(self, path: str) -> None:
        """Insert *path* into the queue immediately after the current position."""
        playlist_idx = self.library.playlist_index(path)
        if playlist_idx is None:
            new = self.library.add([path])
            playlist_idx = self.library.playlist_index(path)
            if new:
                self.queue.rebuild(self.library.size, keep_current=True)
        if playlist_idx is None:
            return

        insert_at = max(0, self.queue.pos + 1)
        q = self.queue.queue

        if playlist_idx in q:
            old_queue_pos = q.index(playlist_idx)
            q.remove(playlist_idx)
            if old_queue_pos < self.queue.pos:
                self.queue.pos -= 1
            insert_at = max(0, self.queue.pos + 1)

        q.insert(insert_at, playlist_idx)
        self._rebuild_view()
        self._flash(">| Queued next")

    def on_queue_append(self, path: str) -> None:
        """Append *path* to the end of the queue."""
        playlist_idx = self.library.playlist_index(path)
        if playlist_idx is None:
            self.library.add([path])
            playlist_idx = self.library.playlist_index(path)
            self.queue.rebuild(self.library.size, keep_current=True)
        if playlist_idx is not None and playlist_idx not in self.queue.queue:
            self.queue.queue.append(playlist_idx)
        self._rebuild_view()
        self._flash(f"+ {self.library.display_name(path)}")

    def on_queue_append_many(self, paths: list[str]) -> None:
        """Append multiple paths to the end of the queue (skips duplicates)."""
        added = 0
        for path in paths:
            playlist_idx = self.library.playlist_index(path)
            if playlist_idx is None:
                self.library.add([path])
                self.queue.rebuild(self.library.size, keep_current=True)
                playlist_idx = self.library.playlist_index(path)
            if playlist_idx is not None and playlist_idx not in self.queue.queue:
                self.queue.queue.append(playlist_idx)
                added += 1
        if added:
            self._rebuild_view()
            self._flash(f"+ {added} track{'s' if added != 1 else ''} queued")

    def on_play_next_many(self, paths: list[str]) -> None:
        """Insert paths into the queue right after the current position, in order."""
        q = self.queue.queue
        offset = 0
        for path in paths:
            playlist_idx = self.library.playlist_index(path)
            if playlist_idx is None:
                self.library.add([path])
                self.queue.rebuild(self.library.size, keep_current=True)
                playlist_idx = self.library.playlist_index(path)
            if playlist_idx is None:
                continue
            # Remove existing occurrence to avoid duplicates
            if playlist_idx in q:
                old = q.index(playlist_idx)
                q.pop(old)
                if old <= self.queue.pos:
                    self.queue.pos -= 1
            insert_at = max(0, self.queue.pos + 1) + offset
            q.insert(insert_at, playlist_idx)
            offset += 1
        if offset:
            self._rebuild_view()
            self._flash(f">| {offset} track{'s' if offset != 1 else ''} queued next")

    def on_view_artist(self, artist: str) -> None:
        """Navigate to the Artists tab and select *artist*."""
        self.tabs.switch_to("artists")
        self.tabs.artists_view.select_artist(artist)

    def on_view_album(self, artist: str | None, album: str) -> None:
        """Navigate to the Albums tab and select *album*."""
        self.tabs.switch_to("albums")
        self.tabs.albums_view.select_album(artist, album)

    def on_remove_from_library(self, path: str) -> None:
        """Remove *path* from the library entirely (not just the queue)."""
        playlist_idx = self.library.playlist_index(path)
        if playlist_idx is None:
            return
        was_current = (self.queue.current_playlist_idx == playlist_idx)
        self.library.remove_by_playlist_indices([playlist_idx])
        if was_current:
            self.player.stop()
            self.transport.set_playing(False)
            self.queue.pos = -1
        self.queue.rebuild(self.library.size, keep_current=True)
        self._rebuild_view()
        self._flash("✕ Removed from library")

    def on_load_playlist_paths(self, paths: list[str]) -> None:
        """Load *paths* into the queue and start playing the first track."""
        self.library.add(paths)
        self.queue.rebuild(self.library.size)
        self._rebuild_view()
        if paths:
            try:
                playlist_idx = self.library.playlist.index(paths[0])
                queue_pos    = self.queue.queue.index(playlist_idx)
                self._load_and_play(queue_pos)
            except ValueError:
                pass

    def on_add_to_playlist(self, path: str, playlist_id: int) -> None:
        """Add a single track to a named playlist."""
        self.playlist_store.add_track(playlist_id, path)
        pl = self.playlist_store.get(playlist_id)
        name = pl.name if pl else "playlist"
        self._flash(f"▤ Added to {name}")
        self.tabs.playlists_view.refresh_playlists()

    def on_sort(self, key: str) -> None:
        self.queue.sort_by(key, self.library.playlist, self.library.meta_cache)
        self._rebuild_view()
        self.playlist_panel.set_sort(self.queue.sort_key, self.queue.sort_rev)

    def on_sort_clear(self) -> None:
        self.queue.clear_sort(self.library.size)
        self._rebuild_view()
        self.playlist_panel.set_sort(None)

    def on_jump_to_current(self) -> None:
        self.playlist_panel.jump_to_current(self.queue.pos, self.queue.view)

    def on_curve_sort_toggle(self) -> None:
        """Toggle the dragon-curve walk queue order on / off."""
        if self.queue.curve_walk:
            # Return to insertion order
            self.queue.clear_sort(self.library.size)
            self._rebuild_view()
            self._flash("↺ Normal order")
        else:
            walker = getattr(getattr(self, "curve_daemon", None), "walker", None)
            if walker is None:
                self._flash("CurveWalker not ready")
                return
            self.queue.sort_by_curve(walker, self.library, self.meta_cache)
            self._rebuild_view()
            self._flash(f"↺ Curve walk  {len(self.library.playlist)} tracks")
