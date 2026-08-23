# -*- coding: utf-8 -*-
"""phi.meta.review_queue — thread-safe queue for low-confidence enrichment matches.

Items that scored below the auto-accept threshold are placed here for the
user to review.  The EnrichPanel polls pending_count() and renders items
for Accept / Reject / Edit actions.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional


class ReviewStatus(Enum):
    PENDING  = auto()
    ACCEPTED = auto()
    REJECTED = auto()
    EDITED   = auto()


@dataclass
class ReviewItem:
    """One candidate match awaiting user action."""
    path:         str                    # absolute path to the audio file
    original_meta: dict                  # tags as they were before enrichment
    proposed_meta: dict                  # what MB/AcoustID suggest
    score:        float                  # AcoustID confidence [0.0, 1.0]
    acoustid:     str   = ""             # AcoustID identifier
    mbid:         str   = ""             # MusicBrainz recording MBID
    release_mbid: str   = ""
    status:       ReviewStatus = ReviewStatus.PENDING
    chosen_meta:  dict  = field(default_factory=dict)  # set by user on EDITED

    def display_label(self) -> str:
        """Short human-readable label for the review list."""
        import os
        orig_title  = self.original_meta.get("title") or os.path.basename(self.path)
        prop_artist = self.proposed_meta.get("artist", "?")
        prop_title  = self.proposed_meta.get("title",  "?")
        pct         = int(self.score * 100)
        return f"[{pct}%]  {orig_title}  →  {prop_artist} — {prop_title}"


class ReviewQueue:
    """
    Thread-safe collection of ReviewItems.

    Producers (EnrichDaemon) add items via push().
    Consumers (EnrichPanel) read via pending_items() and resolve via resolve().
    """

    def __init__(self) -> None:
        self._lock:  threading.Lock      = threading.Lock()
        self._items: list[ReviewItem]    = []

    # ── producer API ──────────────────────────────────────────────────────────

    def push(self, item: ReviewItem) -> None:
        """Add a new pending review item (called from background thread)."""
        with self._lock:
            # Don't duplicate paths already in the queue
            existing_paths = {it.path for it in self._items}
            if item.path not in existing_paths:
                self._items.append(item)

    # ── consumer API ──────────────────────────────────────────────────────────

    def pending_items(self) -> list[ReviewItem]:
        """Return a snapshot of all PENDING items."""
        with self._lock:
            return [it for it in self._items if it.status == ReviewStatus.PENDING]

    def all_items(self) -> list[ReviewItem]:
        """Return a snapshot of all items regardless of status."""
        with self._lock:
            return list(self._items)

    def pending_count(self) -> int:
        with self._lock:
            return sum(1 for it in self._items if it.status == ReviewStatus.PENDING)

    def resolve(
        self,
        item:   ReviewItem,
        action: ReviewStatus,
        edited_meta: Optional[dict] = None,
    ) -> None:
        """
        Mark *item* as resolved.

        action      ACCEPTED  — accept proposed_meta as-is
                    REJECTED  — discard the suggestion
                    EDITED    — use edited_meta (caller supplies merged dict)
        """
        with self._lock:
            for it in self._items:
                if it.path == item.path and it.status == ReviewStatus.PENDING:
                    it.status = action
                    if action == ReviewStatus.EDITED and edited_meta:
                        it.chosen_meta = edited_meta
                    break

    def remove(self, path: str) -> None:
        """Remove all items for *path* from the queue."""
        with self._lock:
            self._items = [it for it in self._items if it.path != path]

    def clear_resolved(self) -> None:
        """Prune accepted/rejected/edited items to keep the list lean."""
        with self._lock:
            self._items = [it for it in self._items
                           if it.status == ReviewStatus.PENDING]
