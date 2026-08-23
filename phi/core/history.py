# -*- coding: utf-8 -*-
"""phi.core.history — doubly-linked playback history.

Replaces the brittle ``queue.pos - 1`` back-navigation with a proper
linked-list node chain so that pressing "prev" always returns to the
*actually last played track*, not just the adjacent queue slot.

Why not use a plain list?
    A doubly-linked node chain lets the cursor move back *without*
    destroying the forward branch — if the user presses prev then plays a
    new track, the old forward chain is cleanly truncated at the cursor.
    A deque-based approach would need an extra forward-stack; the linked
    nodes keep both in one structure.

Index spaces match phi.core.queue:
    path         — absolute file path (primary key inside phi)
    queue_pos    — QueueEngine.pos at the time the track was loaded
    playlist_idx — Library.playlist index at that moment

Thread safety:
    ``push`` / ``back`` / ``forward`` are called from the Tk main thread
    only (inside load_and_play / on_prev).  No locking needed.
"""
from __future__ import annotations

import time
from typing import Optional


_MAX_DEPTH = 200   # maximum nodes kept (old tail is GC'd)


class HistoryNode:
    """Single node in the playback history chain."""

    __slots__ = ("path", "queue_pos", "playlist_idx", "timestamp", "prev", "next")

    def __init__(self, path: str, queue_pos: int, playlist_idx: int) -> None:
        self.path:         str               = path
        self.queue_pos:    int               = queue_pos
        self.playlist_idx: int               = playlist_idx
        self.timestamp:    float             = time.time()
        self.prev: Optional["HistoryNode"]   = None
        self.next: Optional["HistoryNode"]   = None

    def __repr__(self) -> str:
        import os
        return f"<HistoryNode {os.path.basename(self.path)!r} q={self.queue_pos}>"


class PlaybackHistory:
    """Doubly-linked playback history.

    Usage::

        history = PlaybackHistory()

        # each time a track starts:
        history.push(path, queue_pos, playlist_idx)

        # on prev:
        node = history.back()
        if node:
            load_and_play_by_path(node.path)

        # on next (after going back):
        node = history.forward()
        if node:
            load_and_play_by_path(node.path)
    """

    def __init__(self, max_depth: int = _MAX_DEPTH) -> None:
        self._cursor: Optional[HistoryNode] = None
        self._size:   int = 0
        self._max:    int = max_depth

    # ── public API ────────────────────────────────────────────────────────────

    def push(self, path: str, queue_pos: int, playlist_idx: int) -> HistoryNode:
        """Record a newly-played track and advance the cursor.

        If the cursor is mid-chain (user pressed back then played something
        new), the forward branch is cleanly truncated first.
        """
        node = HistoryNode(path, queue_pos, playlist_idx)

        if self._cursor is not None:
            # Truncate any forward branch that no longer applies
            self._cursor.next = None
            node.prev = self._cursor
            self._cursor.next = node
        # else: first track ever — node.prev stays None

        self._cursor = node
        self._size += 1
        self._trim()
        return node

    def back(self) -> Optional[HistoryNode]:
        """Move the cursor one step back and return that node.

        Returns None if there is no previous track in the history.
        Does NOT load the track — the caller is responsible for playback.
        """
        if self._cursor is not None and self._cursor.prev is not None:
            self._cursor = self._cursor.prev
            return self._cursor
        return None

    def forward(self) -> Optional[HistoryNode]:
        """Move the cursor one step forward (after going back) and return that node.

        Returns None if there is no forward track (cursor is already at the tip).
        """
        if self._cursor is not None and self._cursor.next is not None:
            self._cursor = self._cursor.next
            return self._cursor
        return None

    def current(self) -> Optional[HistoryNode]:
        """The node for the currently-playing track (tip of the cursor)."""
        return self._cursor

    # ── inspection ────────────────────────────────────────────────────────────

    def depth_back(self) -> int:
        """Number of steps we can go backward from the current cursor."""
        n, node = 0, self._cursor
        while node is not None and node.prev is not None:
            n += 1
            node = node.prev
        return n

    def depth_forward(self) -> int:
        """Number of steps we can go forward from the current cursor."""
        n, node = 0, self._cursor
        while node is not None and node.next is not None:
            n += 1
            node = node.next
        return n

    def recent(self, n: int = 10) -> list[HistoryNode]:
        """Return the last *n* played tracks, most-recent first.

        Walks back from the cursor tip (not from the cursor position — so
        this always reflects global history, not just what's "in front" of
        the cursor when the user has pressed back).
        """
        tip   = self._cursor
        nodes: list[HistoryNode] = []
        # walk to the actual tip of the chain
        while tip is not None and tip.next is not None:
            tip = tip.next
        node = tip
        while node is not None and len(nodes) < n:
            nodes.append(node)
            node = node.prev
        return nodes

    @property
    def size(self) -> int:
        return self._size

    # ── internals ─────────────────────────────────────────────────────────────

    def _trim(self) -> None:
        """Prune the oldest tail node if the chain exceeds max_depth."""
        if self._size <= self._max:
            return
        # Walk to the oldest (tail) node starting from cursor
        tail = self._cursor
        while tail is not None and tail.prev is not None:
            tail = tail.prev
        # Disconnect tail from its successor
        if tail is not None and tail.next is not None:
            tail.next.prev = None
            tail.next = None
        self._size = min(self._size, self._max)
