# -*- coding: utf-8 -*-
"""phi.models.base — abstract base for all phi inference models.

The interface is intentionally thin: one method to check eligibility, one to
run.  Models return a plain dict that is merged into Library.annotations[path].
They never touch playback state — they are pure annotation engines.

Dropping in a new model:
    1. Subclass PhiModel, set name / version.
    2. Implement can_process() and run().
    3. Register with ModelRegistry.register(MyModel()).

The system handles threading, error isolation, and progress reporting.
"""
from __future__ import annotations
from abc import ABC, abstractmethod


class PhiModel(ABC):
    """
    Abstract base for a phi annotation model.

    Annotations returned by run() are arbitrary key/value pairs.
    Suggested convention:
        bpm       : float   beats per minute
        key       : str     musical key, e.g. "C# minor"
        mood      : str     inferred mood label
        energy    : float   perceived energy [0, 1]
        embedding : list    float vector for similarity search
        tags      : list    auto-generated tag strings
    """

    #: Human-readable identifier shown in the Models tab
    name:    str = ""
    version: str = "0.0.0"

    #: Short description shown in the Models tab
    description: str = ""

    @abstractmethod
    def can_process(self, path: str, meta: dict) -> bool:
        """
        Return True if this model should process *path*.

        Typically used to skip tracks that already have this annotation
        or that are in unsupported formats.
        """

    @abstractmethod
    def run(self, path: str, meta: dict) -> dict:
        """
        Analyse *path* and return a dict of annotations.

        Must be safe to call from a background thread.
        Must not raise — catch internal errors and return partial results.
        """

    def batch(self, items: list[tuple[str, dict]]) -> list[dict]:
        """
        Process a list of (path, meta) pairs.
        Default: sequential run().  Override for true batch inference.
        """
        results = []
        for path, meta in items:
            try:
                results.append(self.run(path, meta))
            except Exception:
                results.append({})
        return results

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r} v{self.version}>"
