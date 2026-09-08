"""
prefeed_shuffle — MCP tools for the CAIRRN-bound prefeed shuffle.

Three tools:

    shuffle_seed   — bootstrap: build session + force initial commit
    shuffle_step   — one scheduler clock tick (gate check + auto prefeed/commit)
    shuffle_next   — advance cursor and return the next track
    shuffle_state  — inspect the full shuffle + gate state
"""
from __future__ import annotations

import threading
from typing import Any, Optional

from mcp_server._gate import requires_init
from mcp_server._state import _dom_queue, mcp

# Module-level lazy singleton — shared across all tool calls this process.
_shuffle: Optional[Any] = None  # CAIRRNPrefeedShuffle
_shuffle_lock = threading.Lock()


def _get_shuffle() -> Optional[Any]:
    """
    Build and cache the CAIRRNPrefeedShuffle singleton.

    Returns None if LIBRARY_ROOT does not exist (graceful degradation).
    The PhiTracerSession inside reuses _state._phi_session when available
    via a direct import from phi_clip (avoids double-building the library).
    """
    global _shuffle
    with _shuffle_lock:
        if _shuffle is not None:
            return _shuffle

        from phi.library import LIBRARY_ROOT
        if not LIBRARY_ROOT.exists():
            return None

        from mcp_server.tools.phi_clip import _get_session
        session = _get_session()
        if session is None:
            return None

        from engine.prefeed_shuffle import make_prefeed_shuffle
        _shuffle = make_prefeed_shuffle(
            session=session,
            exploration=0.15,
            tau=10.0,
            refresh_every=0,
            rng_seed=7,
        )
        return _shuffle


# ---------------------------------------------------------------------------
# shuffle_seed
# ---------------------------------------------------------------------------


@requires_init
def shuffle_seed() -> dict[str, Any]:
    """
    Bootstrap the CAIRRN-bound prefeed shuffle.

    Builds the PhiTracerSession if not already warm, forces an immediate
    prefeed + commit (bypassing the coherence gate), and returns a peek at
    the first 5 tracks in the new active shuffle.

    Call this once before using shuffle_step or shuffle_next.
    """
    with _dom_queue.gate("shuffle_seed"):
        s = _get_shuffle()
        if s is None:
            return {"error": "library_not_available", "seeded": False, "tracks": []}

        peek = s.seed()
        tracks_out = _peek_tracks(s, peek)

        return {
            "seeded": True,
            "active_len": s.shuffle.active_len,
            "tracks": tracks_out,
            "state": s.state(),
        }


# ---------------------------------------------------------------------------
# shuffle_step
# ---------------------------------------------------------------------------


# Slash-only — Cursor catalog cap 60. Call via run_command("/shuffle-step").
@requires_init
def shuffle_step() -> dict[str, Any]:
    """
    One CAIRRN scheduler clock tick.

    Checks coherence against the CODE hub state (shards 3 + 4).

    Gate closed (coherence < 0.5671):
        Prefeed runs in the background — next shuffle computed from current
        shard activations, stored in the pending buffer.
        Active shuffle unchanged — no disruption to playback.

    Gate open (coherence ≥ 0.5671):
        PhiTracerSession.tick() fires — OctopusTracer arm scores update
        the harmonic index.
        Pending shuffle commits — becomes the new active order instantly
        (zero latency, already computed).

    Returns ShuffleStepResult + peek at next 3 active tracks.
    """
    with _dom_queue.gate("shuffle_step"):
        s = _get_shuffle()
        if s is None:
            return {"error": "library_not_available"}

        if not s.shuffle.has_active:
            return {"error": "not_seeded", "hint": "call shuffle_seed first"}

        result = s.step()
        peek = s.peek_active(3)

        return {
            **result.as_dict(),
            "upcoming": _peek_tracks(s, peek),
            "state": s.state(),
        }


# ---------------------------------------------------------------------------
# shuffle_next
# ---------------------------------------------------------------------------


@mcp.tool()
@requires_init
def shuffle_next(peek_ahead: int = 3) -> dict[str, Any]:
    """
    Advance the shuffle cursor and return the current track.

    Parameters
    ----------
    peek_ahead : number of upcoming tracks to include after the current one

    Returns
    -------
    current_track : the track at the new cursor position
    upcoming      : next peek_ahead tracks (without advancing cursor again)
    """
    with _dom_queue.gate("shuffle_next"):
        s = _get_shuffle()
        if s is None:
            return {"error": "library_not_available"}

        if not s.shuffle.has_active:
            return {"error": "not_seeded", "hint": "call shuffle_seed first"}

        track_idx = s.next()
        snap = s._session.snapshot
        track = snap.tracks[track_idx] if snap else None

        current_out: dict[str, Any] = {
            "index": track_idx,
            "cursor": s.shuffle.cursor,
        }
        if track is not None:
            current_out.update({
                "name":   track.name or track.stem,
                "artist": track.artist,
                "album":  track.album,
                "tags":   track.all_tags[:6],
                "key":    track.key_camelot or track.key,
            })

        peek = s.peek_active(peek_ahead)
        return {
            "current": current_out,
            "upcoming": _peek_tracks(s, peek),
            "gate_open": s.gate_open,
            "coherence": round(s.coherence, 4),
            "pending_ready": s.shuffle.has_pending,
        }


# ---------------------------------------------------------------------------
# shuffle_state
# ---------------------------------------------------------------------------


@mcp.tool()
@requires_init
def shuffle_state() -> dict[str, Any]:
    """
    Full state snapshot of the CAIRRN prefeed shuffle.

    Returns coherence, gate status, buffer sizes, cursor, tick count,
    CODE hub activation, and the next 5 upcoming tracks.
    """
    with _dom_queue.gate("shuffle_state"):
        s = _get_shuffle()
        if s is None:
            return {"error": "library_not_available", "seeded": False}

        peek = s.peek_active(5)
        return {
            "seeded": s.shuffle.has_active,
            "upcoming": _peek_tracks(s, peek),
            "state": s.state(),
        }


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------


def _peek_tracks(s: Any, peek: Any) -> list[dict[str, Any]]:
    """Format a ShufflePeek into a list of track dicts."""
    snap = s._session.snapshot
    if snap is None or not peek.indices:
        return []
    out = []
    for i, idx in enumerate(peek.indices):
        if idx >= snap.N:
            continue
        t = snap.tracks[idx]
        out.append({
            "position":  i,
            "index":     idx,
            "name":      t.name or t.stem,
            "artist":    t.artist,
            "tags":      t.all_tags[:5],
            "key":       t.key_camelot or t.key,
        })
    return out
