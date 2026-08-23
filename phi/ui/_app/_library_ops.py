# -*- coding: utf-8 -*-
"""phi.ui._app._library_ops — library management and file I/O callbacks."""
from __future__ import annotations
import os
from pathlib import Path


class _LibraryOpsMixin:
    """Add/remove/clean/dedup tracks; watch folder; M3U save/load; playlists."""

    def on_clean(self) -> None:
        """Remove tracks whose files no longer exist on disk."""
        was_playing = (self.library.playlist[self.queue.current_playlist_idx]
                       if self.queue.current_playlist_idx >= 0 else None)
        removed = self.library.remove_missing()
        if removed:
            if was_playing in removed:
                self.player.stop()
                self.transport.set_playing(False)
                self.queue.pos = -1
            self.queue.rebuild(self.library.size, keep_current=True)
            self._rebuild_view()
            self._flash(f"cln Removed {len(removed)} missing file{'s' if len(removed) != 1 else ''}")
        else:
            self._flash("cln All files present")

    def on_dedup(self) -> None:
        """Remove duplicate paths from the library."""
        n = self.library.deduplicate()
        self.queue.rebuild(self.library.size, keep_current=True)
        self._rebuild_view()
        self._flash(f"Removed {n} duplicate{'s' if n != 1 else ''}" if n else "No duplicates found")

    def on_search(self, q: str) -> None:
        self._rebuild_view(search=q)

    def on_add_files(self) -> None:
        from PySide6.QtWidgets import QFileDialog
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Add files — φ",
            "",
            "Audio (*.mp3 *.wav *.ogg *.flac *.m4a *.aac);;All files (*.*)",
        )
        new = self.library.add(list(paths))
        self.queue.rebuild(self.library.size, keep_current=True)
        self._rebuild_view()
        self._bg_meta(new)
        if new and hasattr(self, "art_spider"):
            self.art_spider.kick()

    def on_add_folder(self) -> None:
        from PySide6.QtWidgets import QFileDialog
        folder = QFileDialog.getExistingDirectory(self, "Add folder — φ")
        if not folder:
            return
        self.on_add_folder_path(folder)

    def on_add_folder_path(self, folder: str) -> None:
        """Add all audio files from *folder* to the library."""
        from phi.meta.reader import scan_folder
        new = self.library.add(scan_folder(folder))
        self.queue.rebuild(self.library.size, keep_current=True)
        self._rebuild_view()
        self._bg_meta(new)
        self._flash(f"+ {len(new)} tracks from {os.path.basename(folder)}")
        if new and hasattr(self, "art_spider"):
            self.art_spider.kick()

    def _show_onboarding(self) -> None:
        from phi.ui.qt.onboarding import show_if_empty
        show_if_empty(self)

    def on_clear(self) -> None:
        self.player.stop()
        self.transport.set_playing(False)
        self.transport.reset_seek()
        self.library.clear()
        self.queue.rebuild(0)
        self.duration = 0.0
        self.now_playing.reset()
        self._refresh_playlist()

    def on_toggle_watch(self) -> None:
        if self.watcher.active:
            self.watcher.stop()
            self.playlist_panel.set_watch(False)
        else:
            from PySide6.QtWidgets import QFileDialog
            folder = QFileDialog.getExistingDirectory(self, "Watch folder — φ")
            if not folder:
                return
            self.watcher.start(folder, list(self.library.playlist))
            self.playlist_panel.set_watch(True, self.watcher.folder_name)
            self._do_watch_scan()

    def on_save_queue_as_playlist(self) -> None:
        """Save the current queue as a named playlist in the store."""
        from PySide6.QtWidgets import QInputDialog
        if not self.queue.queue:
            self._flash("Queue is empty")
            return
        name, ok = QInputDialog.getText(self, "Save as Playlist", "Playlist name:")
        if not ok:
            name = None
        if not name or not name.strip():
            return
        paths = [self.library.playlist[pi] for pi in self.queue.queue
                 if pi < len(self.library.playlist)]
        try:
            self.playlist_store.create_from_paths(name.strip(), paths)
            self._flash(f'▤ Saved "{name.strip()}" ({len(paths)} tracks)')
            self.tabs.playlists_view.refresh_playlists()
            self.tabs.switch_to("playlists")
        except Exception as exc:
            self._flash(f"Error: {exc}")

    def _write_m3u(self, path: str) -> None:
        """Write the current queue to an M3U file at *path*.  Flashes result."""
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("#EXTM3U\n")
                for pl_idx in self.queue.queue:
                    p    = self.library.playlist[pl_idx]
                    meta = self.library.get_meta(p) or {}
                    dur  = int(meta.get("duration") or -1)
                    f.write(f"#EXTINF:{dur},{self.library.display_name(p)}\n{p}\n")
            self._flash(f"Saved {len(self.queue.queue)} tracks → {os.path.basename(path)}")
        except Exception as e:
            self._flash(f"Save failed: {e}")

    def on_save_m3u(self) -> None:
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save playlist — φ",
            "",
            "M3U playlist (*.m3u)",
        )
        if not path:
            return
        self._write_m3u(path)

    def on_load_m3u(self) -> None:
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load playlist — φ",
            "",
            "M3U playlist (*.m3u *.m3u8)",
        )
        if not path:
            return
        added: list[str] = []
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and os.path.isfile(line):
                        added.extend(self.library.add([line]))
        except Exception as e:
            self._flash(f"Load failed: {e}")
            return
        self.queue.rebuild(self.library.size, keep_current=True)
        self._rebuild_view()
        self._bg_meta(added)
        self._flash(f"Loaded {len(added)} tracks")

    def on_rescan(self, extra_dirs: list[Path] | None = None) -> None:
        """Re-run discovery. Pass *extra_dirs* to scan additional locations."""
        import threading
        threading.Thread(
            target=self._auto_discover, args=(extra_dirs,), daemon=True
        ).start()
