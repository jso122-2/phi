# -*- coding: utf-8 -*-
"""phi.models.registry — model registration and background batch runner.

Usage
-----
    registry = ModelRegistry()
    registry.register(BPMModel())
    registry.register(KeyModel())

    # Run all models on a batch of tracks (background thread)
    registry.run_batch(paths, library, on_progress=cb, on_done=cb)
"""
from __future__ import annotations
import threading
from typing import Callable

from phi.models.base import PhiModel


class ModelRegistry:
    """
    Holds registered PhiModel instances and coordinates batch inference.

    All inference runs on a background daemon thread — never blocks the UI.
    Progress and completion are reported via callbacks scheduled on the
    main thread via a Tk `after(0, cb)` supplied by the caller.
    """

    def __init__(self) -> None:
        self._models: list[PhiModel] = []
        self._running: bool = False

    # ── registration ───────────────────────────────────────────────────────────

    def register(self, model: PhiModel) -> None:
        """Add a model to the registry.  Duplicate names are silently skipped."""
        if not any(m.name == model.name for m in self._models):
            self._models.append(model)

    @property
    def models(self) -> list[PhiModel]:
        return list(self._models)

    @property
    def running(self) -> bool:
        return self._running

    # ── batch inference ────────────────────────────────────────────────────────

    def run_batch(
        self,
        paths: list[str],
        library,
        *,
        schedule: Callable,          # Tk root.after  — schedule_fn(0, cb)
        on_progress: Callable | None = None,   # (done, total, path) → None
        on_done: Callable | None = None,       # () → None
    ) -> None:
        """
        Run all eligible models over *paths* in a background thread.

        *schedule* must be ``root.after`` (or equivalent) so that callbacks
        land on the main thread.
        """
        if self._running:
            return

        self._running = True
        total = len(paths)

        def _worker() -> None:
            for i, path in enumerate(paths):
                meta = library.get_meta(path) or {}
                ann  = library.get_annotation(path)
                merged = {**meta, **ann}   # models see combined context

                for model in self._models:
                    try:
                        if model.can_process(path, merged):
                            result = model.run(path, merged)
                            if result:
                                library.store_annotation(path, result)
                                merged.update(result)
                    except Exception:
                        pass

                if on_progress:
                    schedule(0, lambda p=path, d=i + 1: on_progress(d, total, p))

            self._running = False
            if on_done:
                schedule(0, on_done)

        threading.Thread(target=_worker, daemon=True).start()

    def run_single(self, path: str, library) -> dict:
        """
        Synchronous single-track run (for immediate display).
        Returns merged annotation dict.
        """
        meta   = library.get_meta(path) or {}
        ann    = library.get_annotation(path)
        merged = {**meta, **ann}
        for model in self._models:
            try:
                if model.can_process(path, merged):
                    result = model.run(path, merged)
                    if result:
                        library.store_annotation(path, result)
                        merged.update(result)
            except Exception:
                pass
        return merged

    # ── status ─────────────────────────────────────────────────────────────────

    def status(self, library) -> list[dict]:
        """
        Return a status dict per model:
          { name, version, description, annotated, pending, enabled }
        """
        statuses = []
        for m in self._models:
            annotated = len(library.tracks_annotated_with(m.name))
            total     = library.size
            statuses.append({
                "name":        m.name,
                "version":     m.version,
                "description": m.description,
                "annotated":   annotated,
                "pending":     total - annotated,
                "enabled":     m.can_process("", {}),   # rough proxy
            })
        return statuses
