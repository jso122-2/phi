# -*- coding: utf-8 -*-
"""phi.core.queue — queue modulation engine.

QueueEngine is pure Python: no Tk, no pygame, no I/O.
It owns the ordered list of playlist indices (queue) and the filtered
view of that list (view), plus shuffle / repeat / sort state.

Index spaces
------------
phi uses three separate index spaces that are easy to confuse:

  playlist_idx  — index into Library.playlist (the master track list).
                  Stable: never changes as long as the track is in the library.

  queue_pos     — index into QueueEngine.queue (the playback order list).
                  queue[queue_pos] == playlist_idx.
                  Changes when tracks are added / removed / shuffled.
                  self.pos is the *current* queue_pos.

  view_idx      — index into QueueEngine.view (the search-filtered queue).
                  view[view_idx] == queue_pos.
                  Shrinks when the user types a search string.

So to get the path of a visible row:
    path = library.playlist[ queue.queue[ queue.view[view_idx] ] ]
"""
from __future__ import annotations
import random
import threading
from typing import TYPE_CHECKING, Optional

from phi.config import REPEAT_STATES

if TYPE_CHECKING:
    from phi.engine.forest_floor import ForestFloor
    from phi.core.library import Library

# ── CAIRRN gate — set by PhiApp after floor is initialised ────────────────────
_floor: Optional["ForestFloor"] = None


def bind_floor(floor: "ForestFloor") -> None:
    """Wire the forest floor into the queue gate.

    When the COMMANDS hub is z-hot (enrichment queue burst, |z| ≥ 2.5),
    ``should_prefetch()`` returns False so the gapless pre-loader backs off
    and reduces disk I/O contention with the enrichment pipeline.

    Called once by PhiApp during init, alongside the other bind_floor() calls.
    """
    global _floor
    _floor = floor


def should_prefetch() -> bool:
    """Return True when it is safe to pre-load the next track into pygame.

    Returns False when the COMMANDS hub is z-hot — indicating a recent burst
    of enrichment I/O pressure (|z_awareness| ≥ z_spawn_threshold) — to
    reduce disk contention with the enrichment pipeline.

    Uses z_awareness rather than raw coherence because the COMMANDS hub
    auto-resets to coherence=1.0 immediately after going incoherent; the
    z-score persists for the rolling window and is the correct "actively
    enriching" signal.

    Falls back to True when no floor is wired (safe default: always prefetch).
    """
    if _floor is None:
        return True
    try:
        hub = _floor._bridge._hubs.get("COMMANDS")
        if hub is None:
            return True
        threshold = _floor._bridge.z_spawn_threshold
        return abs(hub.z_awareness) < threshold
    except Exception:
        return True


_SHUFFLE_MODES = ("off", "random", "cairrn")


class QueueEngine:

    def __init__(self):
        self.queue:        list[int]  = []    # queue[queue_pos] = playlist_idx
        self.view:         list[int]  = []    # view[view_idx]   = queue_pos (filtered subset)
        self.pos:          int        = -1    # current queue_pos (-1 = nothing loaded)
        self.shuffle_mode: str        = "off" # "off" | "random" | "cairrn"
        self.repeat:       str        = "off"
        self.sort_key:     str | None = None  # active sort column, None = insertion order
        self.sort_rev:     bool       = False
        self.curve_walk:   bool       = False  # True when queue is sorted by curve position
        self._nudge_lock               = threading.Lock()

    # ── shuffle compat property ───────────────────────────────────────────────

    @property
    def shuffle(self) -> bool:
        """Backward-compat: True when shuffle_mode != 'off'."""
        return self.shuffle_mode != "off"

    @shuffle.setter
    def shuffle(self, value: bool) -> None:
        """Backward-compat setter: True → 'random', False → 'off'."""
        self.shuffle_mode = "random" if value else "off"

    # ── properties ────────────────────────────────────────────────────────────

    @property
    def current_playlist_idx(self) -> int:
        """Playlist index of the current track, or -1."""
        if 0 <= self.pos < len(self.queue):
            return self.queue[self.pos]
        return -1

    # ── rebuild ───────────────────────────────────────────────────────────────

    def rebuild(self, n: int, keep_current: bool = True) -> None:
        """Rebuild queue for a library of n tracks."""
        if n == 0:
            self.queue = []
            self.view  = []
            self.pos   = -1
            return

        cur = self.current_playlist_idx
        self.queue = (
            random.sample(range(n), n)
            if self.shuffle_mode == "random"
            else list(range(n))
        )

        if keep_current and cur >= 0 and cur in self.queue:
            self.pos = self.queue.index(cur)
        else:
            self.pos = max(0, min(self.pos, len(self.queue) - 1))

    # ── search filter ─────────────────────────────────────────────────────────

    def apply_search(self, q: str, display_names: list[str]) -> None:
        """Rebuild view to only include tracks whose name matches q."""
        if not q:
            self.view = list(range(len(self.queue)))
        else:
            q_lower = q.lower()
            self.view = [
                qi for qi in range(len(self.queue))
                if qi < len(display_names) and q_lower in display_names[qi].lower()
            ]

    # ── navigation ────────────────────────────────────────────────────────────

    def advance(self) -> int | None:
        if self.repeat == "one":
            return self.pos
        nxt = self.pos + 1
        if nxt < len(self.queue):
            return nxt
        if self.repeat == "all":
            return 0
        return None

    def next_user(self) -> int | None:
        nxt = self.pos + 1
        if nxt < len(self.queue):
            return nxt
        if self.repeat == "all":
            return 0
        return None

    def prev(self) -> int | None:
        return self.pos - 1 if self.pos > 0 else None

    # ── modulation ────────────────────────────────────────────────────────────

    def sort_by_curve(self, walker, library, meta_cache) -> None:
        """Sort queue by dragon-curve segment position (forward walk).

        Args:
            walker:     ``CurveWalker`` instance.
            library:    App-wide ``Library``.
            meta_cache: App-wide ``MetaCache``.
        """
        cur = self.current_playlist_idx
        ordered = walker.build_order(library, meta_cache)
        self.queue      = ordered
        self.sort_key   = None
        self.sort_rev   = False
        self.curve_walk = True
        if cur >= 0 and cur in self.queue:
            self.pos = self.queue.index(cur)
        else:
            self.pos = max(0, min(self.pos, len(self.queue) - 1))

    def cycle_shuffle(self, n: int) -> str:
        """Advance shuffle mode: off → random → cairrn → off.

        Rebuilds the queue for 'random' (physical reorder); leaves queue order
        intact for 'cairrn' (arc engine inserts tracks dynamically) and 'off'.

        Returns:
            The new shuffle_mode string.
        """
        idx = _SHUFFLE_MODES.index(self.shuffle_mode)
        self.shuffle_mode = _SHUFFLE_MODES[(idx + 1) % len(_SHUFFLE_MODES)]
        self.curve_walk   = False   # mutually exclusive with curve-walk sort
        if self.shuffle_mode == "random":
            self.rebuild(n, keep_current=True)
        elif self.shuffle_mode in ("off", "cairrn"):
            # cairrn: keep current queue order — arc engine drives next-track selection
            # off:    restore linear order
            if self.shuffle_mode == "off":
                self.rebuild(n, keep_current=True)
        return self.shuffle_mode

    def toggle_shuffle(self, n: int) -> None:
        """Backward-compat alias for cycle_shuffle (skips cairrn step)."""
        self.cycle_shuffle(n)

    def cycle_repeat(self) -> str:
        idx = REPEAT_STATES.index(self.repeat)
        self.repeat = REPEAT_STATES[(idx + 1) % len(REPEAT_STATES)]
        return self.repeat

    # ── sorting ───────────────────────────────────────────────────────────────

    def sort_by(self, key: str, playlist: list[str],
                meta_cache: dict[str, dict]) -> None:
        """
        Sort queue by a metadata key: 'title', 'artist', 'album', 'duration'.
        Toggles reverse order if the same key is clicked twice.
        """
        if self.sort_key == key:
            self.sort_rev = not self.sort_rev
        else:
            self.sort_key = key
            self.sort_rev = False

        cur = self.current_playlist_idx

        def _key(pl_idx: int):
            path = playlist[pl_idx] if pl_idx < len(playlist) else ""
            meta = meta_cache.get(path) or {}
            val  = meta.get(key)
            if val is None:
                return (1, "")            # unknowns after knowns
            if key == "duration":
                return (0, float(val))
            return (0, str(val).lower())

        self.queue.sort(key=_key, reverse=self.sort_rev)

        if cur >= 0 and cur in self.queue:
            self.pos = self.queue.index(cur)

    def clear_sort(self, n: int, keep_current: bool = True) -> None:
        """Reset to default (insertion) order."""
        self.sort_key   = None
        self.sort_rev   = False
        self.curve_walk = False
        self.rebuild(n, keep_current=keep_current)

    # ── queue management ──────────────────────────────────────────────────────

    def move_to_next(self, view_idx: int) -> None:
        """Move the track at view_idx to play immediately after current."""
        if not (0 <= view_idx < len(self.view)):
            return
        qi = self.view[view_idx]
        if qi == self.pos:
            return   # already current

        pl_idx = self.queue.pop(qi)

        # Adjust pos if we removed something before it
        if qi < self.pos:
            self.pos -= 1

        next_pos = self.pos + 1
        self.queue.insert(next_pos, pl_idx)

    def remove_at_view_indices(self, view_indices: list[int]) -> list[int]:
        """
        Remove queue entries by view index.
        Returns the playlist indices that were removed (for library cleanup).
        """
        queue_positions = sorted(
            {self.view[vi] for vi in view_indices if 0 <= vi < len(self.view)},
            reverse=True,
        )
        removed_pl = []
        for qp in queue_positions:
            removed_pl.append(self.queue.pop(qp))
            if qp < self.pos:
                self.pos -= 1
            elif qp == self.pos:
                self.pos = max(0, self.pos - 1)
        return removed_pl

    # ── async GNN nudge ───────────────────────────────────────────────────────

    def nudge(self, ranked_paths: list[str], library: "Library") -> int:
        """Re-sort queue[pos+2:] to match the SCUP-ranked path order.

        Slots 0 (now playing) and 1 (pre-buffered, decoding) are frozen.
        Called from the PhiOrchestrator background thread after each GNN
        write.  *ranked_paths* is F_SCUP_CANONICAL descending (phi_rank is
        S_i inside that score).  Thread-safe via _nudge_lock.

        Returns the number of slots reordered (0 if queue too short or no change).
        """
        lock_from = self.pos + 2
        with self._nudge_lock:
            if lock_from >= len(self.queue):
                return 0

            pending = self.queue[lock_from:]
            # path → playlist_idx for every pending slot
            pending_map: dict[str, int] = {}
            for pidx in pending:
                if 0 <= pidx < len(library.playlist):
                    pending_map[library.playlist[pidx]] = pidx

            reordered: list[int] = []
            seen: set[int] = set()

            # Walk ranked_paths; pick any that are pending
            for path in ranked_paths:
                pidx = pending_map.get(path)
                if pidx is not None and pidx not in seen:
                    reordered.append(pidx)
                    seen.add(pidx)

            # Append remaining pending entries not covered by ranked_paths
            for pidx in pending:
                if pidx not in seen:
                    reordered.append(pidx)
                    seen.add(pidx)

            if reordered == pending:
                return 0

            self.queue[lock_from:] = reordered
            return len(reordered)

    # ── reordering ────────────────────────────────────────────────────────────

    def swap_view_rows(self, va: int, vb: int) -> None:
        """Swap two visible rows by swapping their underlying queue entries."""
        if not (0 <= va < len(self.view) and 0 <= vb < len(self.view)):
            return
        qa, qb = self.view[va], self.view[vb]
        self.queue[qa], self.queue[qb] = self.queue[qb], self.queue[qa]
        if self.pos == qa:
            self.pos = qb
        elif self.pos == qb:
            self.pos = qa
