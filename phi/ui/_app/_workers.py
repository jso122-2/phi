# -*- coding: utf-8 -*-
"""phi.ui._app._workers — background workers: meta, enrichment, auto-discover, vault."""
from __future__ import annotations
import os
import threading
from pathlib import Path


class _WorkersMixin:
    """Delegate to MetaWorker; run auto-discover; vault PSSPPS queries; watch scan."""

    def _auto_discover(self, extra_dirs: list[Path] | None = None) -> None:
        """Background thread: scan DEFAULT_SCAN_DIRS + extra_dirs and ingest audio."""
        from phi.discovery import DEFAULT_SCAN_DIRS, auto_discover, summarise

        dirs = list(DEFAULT_SCAN_DIRS) + (extra_dirs or [])
        label = "  ·  ".join(d.name for d in dirs[:3])
        self._sched(0, lambda: self._flash(f"? Scanning {label} …", ms=120_000))
        paths = auto_discover(dirs=dirs)
        if not paths:
            self._sched(0, lambda: self._flash("No audio files found"))
            return

        def on_main():
            pre = self.library.size
            new = self.library.add(paths)
            if not new:
                self._flash(f"Library up to date  ({pre} tracks)")
                return
            self.queue.rebuild(self.library.size, keep_current=True)
            self._rebuild_view()
            self._flash(f"✓ Added {summarise(new)}  —  {self.library.size} total")
            music_dir = str(Path.home() / "Music")
            if not self.watcher.active and os.path.isdir(music_dir):
                self.watcher.start(music_dir, list(self.library.playlist))
                self.playlist_panel.set_watch(True, self.watcher.folder_name)
            self._bg_meta(new)
            if hasattr(self, "art_spider"):
                self.art_spider.kick()

        self._sched(0, on_main)

    def _vault_query_for_track(self, path: str, meta: dict) -> None:
        """Fire a PSSPPS vault query for the current track and inject into CAIRRN + hub ring."""
        from phi.engine.vault_context import query_async_with_ring

        title  = meta.get("title")  or ""
        artist = meta.get("artist") or ""
        query  = f"{title} {artist}".strip() or os.path.basename(path)

        def _on_done(signal: float, top_docs: list) -> None:
            # CAIRRN agent-context: existing behaviour, dispatched to main thread
            self._sched(0, lambda: self.floor._bridge.step("agent-context", signal))
            # hub ring VAULT feedback is handled inside query_async_with_ring

        query_async_with_ring(query, meta, _on_done)

    def _async_meta(self, path: str) -> None:
        self.meta_worker.async_meta(path)

    def _fetch_duration(self, path: str) -> None:
        self.meta_worker.fetch_duration(path)

    def _bg_meta(self, paths: list[str]) -> None:
        self.meta_worker.bg_meta(paths)

    def _schedule_model_run(self, paths: list[str]) -> None:
        self.meta_worker.schedule_model_run(paths)

    def _on_meta_ready(self, path: str, meta: dict) -> None:
        """Main-thread callback: apply newly loaded metadata to all UI panels.

        CAIRRN scheduling
        -----------------
        Routes ML_INFERENCE through the floor (metadata arriving = ML write).
        Art is prefed off-thread; sidebar/drawer/lyrics gated by coherence.
        Duration and replaygain apply immediately (transport-critical).
        """
        from phi.engine.cairrn_router import RequestKind
        cur = self.queue.current_playlist_idx
        is_current = cur >= 0 and self.library.playlist[cur] == path
        if is_current:
            # ── CAIRRN route — metadata arrival is an ML write event ──────────
            result = self.floor.router.route(
                RequestKind.ML_INFERENCE,
                metric=1.0,
                payload={"path": path, "reason": "meta_ready"},
            )

            # ── IMMEDIATE — transport-critical ────────────────────────────────
            if meta.get("duration") and self.duration == 0.0:
                self.duration = meta["duration"]
                self.transport.set_end(meta["duration"])

            # ── PREFEED — art grid off-thread, committed via callback ─────────
            art_bytes = meta.get("art_bytes")
            if art_bytes:
                cols = self.now_playing._cols
                rows = self.now_playing._rows
                self.now_playing.prefeed_art(
                    art_bytes, cols, rows,
                    on_ready=lambda: self._sched(0, self.now_playing.commit_art),
                )
            else:
                self.now_playing.set_track(path, meta)

            # ── COHERENT — sidebar, info drawer, lyrics ───────────────────────
            # Proportional deferral: 0ms when fully coherent, up to 400ms when
            # coherence → 0. Uses the raw float so a hub at 0.48 defers ~8ms,
            # not a flat 250ms like a hub at 0.01.
            ann = self.library.get_annotation(path) if hasattr(self.library, "get_annotation") else None
            defer_ms = int((1.0 - result.coherence) * 400)

            def _update():
                self.sidebar.update_info(path, meta, ann)
                self.info_drawer.update(path, meta, ann)
                self.tabs.lyrics_view.load(path, meta)

            self._sched(defer_ms, _update)

        self._schedule_refresh()

    def _on_enrich_progress(self, progress) -> None:
        """Called on the main thread by EnrichDaemon with a progress snapshot."""
        if hasattr(self.tabs, "enrich_view"):
            self.tabs.enrich_view.update_progress(progress)

    def _on_librosa_progress(self, progress) -> None:
        """Called on the main thread by LibrosaWorker with a progress snapshot."""
        if hasattr(self.tabs, "enrich_view"):
            self.tabs.enrich_view.update_librosa_progress(progress)
