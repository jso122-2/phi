# -*- coding: utf-8 -*-
"""phi.watch.librosa_worker — background librosa feature extraction.

Processes library tracks one at a time, extracting local audio features
(BPM, key, spectral, MFCC) using librosa via a sandboxed subprocess with
a hard 25s timeout per track.

Each successful extraction:
  - Writes a full feature record to ~/.phi/meta_store.jsonl
  - Pushes librosa_bpm / librosa_key / librosa_key_idx / librosa_enriched
    into Library annotations so bpm_consensus sees the signal immediately

No API keys required. CPU-bound (~1–3s per track for 60s audio).
Pauses automatically while audio is playing.

Usage (in PhiApp.__init__)
--------------------------
    self.librosa_worker = LibrosaWorker(
        library      = self.library,
        is_playing   = _is_playing_fn,
        on_progress  = self._on_librosa_progress,
        schedule     = self.dispatch,
    )
    self.after(20_000, self.librosa_worker.start)  # after OctopusOrganizer init
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Callable, Optional

from phi.meta.batch_extractor import (
    META_STORE,
    _extract_subprocess,
    load_store,
    save_store,
)


@dataclass
class LibrosaProgress:
    total:   int  = 0
    done:    int  = 0
    failed:  int  = 0
    current: str  = ""
    running: bool = False
    paused:  bool = False

    @property
    def pct(self) -> float:
        return (self.done / self.total * 100) if self.total > 0 else 0.0

    def status_line(self) -> str:
        if not self.running:
            return "idle"
        if self.paused:
            return f"paused {self.done}/{self.total}"
        if self.current:
            import os
            return f"{self.done}/{self.total}  {os.path.basename(self.current)}"
        return f"{self.done}/{self.total}"


class LibrosaWorker:
    """
    Background thread that extracts librosa audio features for library tracks.

    Parameters
    ----------
    library        phi Library instance
    is_playing     Callable returning True when audio is actively playing
    on_progress    Callback(LibrosaProgress) — invoked on the main thread
    schedule       Tk.after-compatible scheduler for thread-safe UI callbacks
    inter_track_s  Sleep between tracks (default 2.0s — librosa is CPU-heavy)
    """

    def __init__(
        self,
        library,
        is_playing:  Callable[[], bool],
        on_progress: Callable[["LibrosaProgress"], None],
        schedule:    Callable,
        *,
        inter_track_s: float = 2.0,
    ) -> None:
        self._library      = library
        self._is_playing   = is_playing
        self._on_progress  = on_progress
        self._schedule     = schedule
        self._inter_track  = inter_track_s
        self._progress     = LibrosaProgress()
        self._stop_event   = threading.Event()
        self._store_lock   = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        # Tracks submitted to the main thread this session — prevents same-
        # session duplicate processing (distinct from the annotation flag,
        # which persists across sessions).
        self._submitted: set[str] = set()

    # ── control ───────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the worker (idempotent)."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
            name="phi-librosa",
        )
        self._thread.start()

    def stop(self) -> None:
        """Signal the worker to stop after the current track finishes."""
        self._stop_event.set()

    @property
    def progress(self) -> LibrosaProgress:
        return self._progress

    # ── worker ────────────────────────────────────────────────────────────────

    def _run(self) -> None:
        self._progress.running = True
        self._notify()

        while not self._stop_event.is_set():
            pending = self._pending_paths()

            if not pending:
                self._progress.running = False
                self._progress.current = ""
                self._notify()
                # Idle — check again in 60s in case new tracks were added
                self._stop_event.wait(60)
                if not self._pending_paths():
                    break
                self._progress.running = True
                continue

            self._progress.total = len(pending) + self._progress.done
            self._notify()

            for path in pending:
                if self._stop_event.is_set():
                    break

                while self._is_playing() and not self._stop_event.is_set():
                    self._progress.paused = True
                    self._notify()
                    self._stop_event.wait(2.0)
                self._progress.paused = False

                self._progress.current = path
                self._notify()

                self._process(path)
                self._progress.done += 1
                self._notify()

                if not self._stop_event.is_set():
                    self._stop_event.wait(self._inter_track)

        self._progress.running = False
        self._progress.current = ""
        self._notify()

    def _pending_paths(self) -> list[str]:
        """
        Return paths that still need librosa extraction.

        Semantics of librosa_enriched annotation:
          absent / None  → not yet attempted → include
          True           → successfully extracted → skip always
          False          → prior attempt failed → retry next session;
                           _submitted prevents same-session looping
        """
        result: list[str] = []
        for path in list(self._library.playlist):
            if path in self._submitted:
                continue
            if self._library.get_annotation(path).get("librosa_enriched") is True:
                continue
            result.append(path)
        return result

    def _process(self, path: str) -> None:
        """
        Extract features for *path* and push results to the library.

        Checks the existing meta_store.jsonl first — CLI pre-extracted tracks
        are promoted to annotations without re-running librosa.
        """
        self._submitted.add(path)

        # Check store for a valid existing record (e.g. from CLI batch run)
        with self._store_lock:
            records = load_store(META_STORE)
            existing = records.get(path, {})

        if "bpm" in existing and "error" not in existing:
            self._schedule(0, lambda p=path, r=existing: self._apply_result(p, r))
            return

        # Run fresh subprocess extraction (25s hard timeout)
        result = _extract_subprocess(path)

        with self._store_lock:
            records = load_store(META_STORE)
            records[path] = result
            save_store(records, META_STORE)

        if "bpm" in result:
            self._schedule(0, lambda p=path, r=result: self._apply_result(p, r))
        else:
            # Mark as failed — prevents same-session retry; next session retries
            # (librosa_enriched=False is falsy, so _pending_paths includes it,
            # but _submitted blocks the retry within this session).
            self._schedule(0, lambda p=path: self._library.store_annotation(
                p, {"librosa_enriched": False}
            ))
            self._progress.failed += 1

    def _apply_result(self, path: str, result: dict) -> None:
        """Push key librosa fields into Library annotations (runs on main thread)."""
        ann: dict = {}
        if result.get("bpm") is not None:
            ann["librosa_bpm"] = result["bpm"]
        if result.get("key") is not None:
            ann["librosa_key"] = result["key"]
        if result.get("key_idx") is not None:
            ann["librosa_key_idx"] = result["key_idx"]
        ann["librosa_enriched"] = True
        self._library.store_annotation(path, ann)

    def _notify(self) -> None:
        """Push progress snapshot to the main thread."""
        snap = LibrosaProgress(
            total=self._progress.total,
            done=self._progress.done,
            failed=self._progress.failed,
            current=self._progress.current,
            running=self._progress.running,
            paused=self._progress.paused,
        )
        self._schedule(0, lambda: self._on_progress(snap))
