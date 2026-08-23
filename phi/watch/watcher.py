# -*- coding: utf-8 -*-
"""phi.watch.watcher — lightweight folder watcher (polling-based).

FolderWatcher scans a directory and reports newly-arrived audio files.
No threads — called by PhiApp's after() loop.
"""
from __future__ import annotations
import os
from phi.config import AUDIO_EXTS


class FolderWatcher:

    def __init__(self):
        self.folder: str | None = None
        self._seen:  set[str]   = set()   # paths already reported

    # ── control ───────────────────────────────────────────────────────────────

    def start(self, folder: str, already_known: list[str]) -> None:
        """Begin watching folder. already_known paths are not re-reported."""
        self.folder = folder
        self._seen  = set(already_known)

    def stop(self) -> None:
        self.folder = None
        self._seen  = set()

    # ── scanning ──────────────────────────────────────────────────────────────

    def scan(self) -> list[str]:
        """
        Scan for new audio files. Returns paths not previously seen.
        Returns [] if no folder is set or folder no longer exists.
        """
        if not self.folder or not os.path.isdir(self.folder):
            return []

        new = []
        for fname in sorted(os.listdir(self.folder)):
            if os.path.splitext(fname)[1].lower() not in AUDIO_EXTS:
                continue
            full = os.path.join(self.folder, fname)
            if full not in self._seen:
                self._seen.add(full)
                new.append(full)

        return new

    # ── properties ────────────────────────────────────────────────────────────

    @property
    def active(self) -> bool:
        return self.folder is not None

    @property
    def folder_name(self) -> str:
        return os.path.basename(self.folder) if self.folder else ""
