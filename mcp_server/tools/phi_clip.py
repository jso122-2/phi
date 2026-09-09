"""phi_clip — MCP tool: gemini_clip (Stage III track clipper via P_sps)."""
from __future__ import annotations

import sys
import threading
from typing import Any, Optional

from mcp_server._gate import requires_init
from mcp_server._state import _dom_queue, mcp

# ---------------------------------------------------------------------------
# Module-level lazy singletons (built once on first call)
# ---------------------------------------------------------------------------

_session: Optional[Any] = None  # PhiTracerSession
_clipper: Optional[Any] = None  # GeminiClipper
_session_lock = threading.Lock()


def _get_session() -> Optional[Any]:
    """
    Build and cache the PhiTracerSession.

    Returns None if LIBRARY_ROOT does not exist on disk (graceful degradation
    when the Liked Songs library has not been ripped yet).
    """
    global _session
    with _session_lock:
        if _session is not None:
            return _session
        from phi.library import LIBRARY_ROOT
        if not LIBRARY_ROOT.exists():
            print(
                f"[phi_clip] LIBRARY_ROOT not found at {LIBRARY_ROOT} — "
                "phi_clip will remain cold until the Liked Songs library is ripped. "
                "Run the rip pipeline or point SPOTIFY_RIP_LIBRARY_ROOT at an existing library.",
                file=sys.stderr,
            )
            return None
        from engine.phi_session import make_phi_session
        _session = make_phi_session()
        _session.build()
        return _session


def _get_clipper(top_k: int, alpha: float) -> Optional[Any]:
    """Return a GeminiClipper wired to the cached session, or None."""
    session = _get_session()
    if session is None:
        return None
    from phi.models.gemini_clipper import GeminiClipper
    return GeminiClipper(
        proj=session.phi_graph._proj,
        encoder=session.phi_graph._encoder,
        top_k=top_k,
        alpha=alpha,
    )


def is_warmed() -> bool:
    """True once the PhiTracerSession has been built and the snapshot is ready."""
    return _session is not None


def warmup_phi_clip() -> Optional[Any]:
    """
    Attempt to build the PhiTracerSession eagerly.

    Safe to call from a background thread at server startup. Returns the session
    on success, None if the library is absent (degraded-but-stable).
    Never raises — exceptions are caught and logged so startup is not blocked.
    """
    try:
        return _get_session()
    except Exception as exc:
        print(
            f"[phi_clip] warmup failed: {exc} — phi_clip will remain cold.",
            file=sys.stderr,
        )
        return None


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------


@mcp.tool()
@requires_init
def gemini_clip(
    query: str,
    top_k: int = 5,
    blend: float = 0.5,
) -> dict[str, Any]:
    """
    Clip the top-K most relevant tracks from the Liked Songs library for a query.

    Uses GeminiClipper (Stage III execution engine) to score all tracks by
    P_sps = (1−blend)·semantic + blend·H-space proximity, returning the top-K
    with their assembled context string.

    Parameters
    ----------
    query : free-text search (e.g. "dark ambient techno", "sad piano in C minor")
    top_k : number of tracks to return (default 5)
    blend : P_sps blend weight — 0.0 = pure TF-IDF, 1.0 = pure H-space (default 0.5)
            Named 'blend' (not 'alpha') to avoid conflict with the harmonic coupling
            constant alpha enforced by the param_bounds_guard hook.
    """
    with _dom_queue.gate("gemini_clip"):
        session = _get_session()
        if session is None:
            return {
                "query": query,
                "n_tracks_searched": 0,
                "blend": float(blend),
                "context": "",
                "tracks": [],
                "library_available": False,
            }

        snap = session.snapshot
        clipper = _get_clipper(top_k=top_k, alpha=blend)
        result = clipper.clip(query, snap)

        tracks_out = [
            {
                "rank": ct.rank,
                "name": ct.track.name,
                "artist": ct.track.artist,
                "tags": ct.track.all_tags[:8],
                "semantic_score": ct.semantic_score,
                "h_space_score": ct.h_space_score,
                "p_sps": ct.p_sps,
            }
            for ct in result.top_k
        ]

        return {
            "query": result.query,
            "n_tracks_searched": result.n_tracks_searched,
            "blend": result.alpha,
            "context": result.context,
            "tracks": tracks_out,
            "library_available": True,
        }
