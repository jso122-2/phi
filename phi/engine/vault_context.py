# -*- coding: utf-8 -*-
"""phi.engine.vault_context — PSSPPS bridge for Obsidian retrieval.

Queries the Obsidian vault (via the PSSPPS pipeline in Spotify-Rip) whenever
a new track loads.  The retrieval result is converted to a single [0, 1]
signal and injected into the CAIRRN agent-context hub and the music hub ring.

Pipeline (extended)
───────────────────
  track title + artist  +  audio features from meta
        │                         │
        │                         ▼
        │              PhiHubRing.on_track_load(features)
        │                         │
        │              ring.active_spoke_queries()
        │                         │
        ▼                         ▼
  psspps.pipeline.run_psspps(query, ring.activation_vector())
        │
        ▼
  PSPSPSResult → _signal()   (rag_confidence × avg_combined_score × 4)
        │
        ├──▶  CairnBridge.step("agent-context", signal)   [existing]
        └──▶  ring.inject("VAULT", signal)                [new]

Threading
─────────
The PSSPPS query (file I/O + TF-IDF) runs in a daemon thread.
``on_done(signal, top_docs)`` is called from that thread — callers MUST
dispatch any main-thread work via ``schedule(0, ...)``.

Path discovery
──────────────
PSSPPS lives in Spotify-Rip/Spotify-rip/.  We add it to sys.path lazily
on the first call so the phi package doesn't hardcode absolute paths at
import time.
"""
from __future__ import annotations

import logging
import sys
import threading
from pathlib import Path
from typing import Callable, Dict, List, Optional

_log = logging.getLogger("phi.vault_context")

# ── SAMBA_ROOT discovery ──────────────────────────────────────────────────────
# Resolve relative to this file:  phi/engine/vault_context.py
# → up 4 levels lands at  ~/Documents/misc/
# → from there:  Projects/samba-gnn-obsidian  (phi)
#                Spotify-Rip/Spotify-rip       (psspps)

_THIS_FILE   = Path(__file__).resolve()
_MISC_ROOT   = _THIS_FILE.parents[4]          # ~/Documents/misc/
_SAMBA_ROOT  = _MISC_ROOT / "Spotify-Rip" / "Spotify-rip"

_psspps_available: Optional[bool] = None      # None = not yet checked


def _ensure_psspps() -> bool:
    """Add SAMBA_ROOT to sys.path and import-check psspps. Returns True on success."""
    global _psspps_available
    if _psspps_available is not None:
        return _psspps_available

    root_str = str(_SAMBA_ROOT)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)

    try:
        import psspps.pipeline  # noqa: F401
        _psspps_available = True
        _log.info("vault_context: psspps available at %s", _SAMBA_ROOT)
    except ImportError as exc:
        _psspps_available = False
        _log.warning("vault_context: psspps not importable — %s", exc)
    return _psspps_available


# ── Basin sequestration → retrieval locality ──────────────────────────────────

def _t_b_to_alpha(t_b_norm: float) -> float:
    """
    Convert normalised basin sequestration score to a PSSPPS perspective_alpha.

    Expects ``t_b_norm`` = TopologicalInvariant.t_b_norm  (already in (−1, 1)).

        alpha = 0.5 + 0.5 · t_b_norm

    t_b_norm > 0  → deep basin → retrieval stays local  → alpha toward 1.0
    t_b_norm ≈ 0  → neutral                             → alpha = 0.5
    t_b_norm < 0  → open basin → retrieval goes global  → alpha toward 0.0
    """
    return float(0.5 + 0.5 * max(-1.0, min(1.0, t_b_norm)))


# ── signal derivation ─────────────────────────────────────────────────────────

def _signal(result) -> float:
    """
    Collapse a PSPSPSResult into a single [0, 1] CAIRRN metric.

    Formula:
        signal = rag_confidence × avg(combined_scores of top_docs)

    If rag_useful is False the confidence is already low, so no special-casing
    is needed — the signal just stays quiet.
    """
    if not result.top_docs:
        return 0.0
    avg_score = sum(d.combined_score for d in result.top_docs) / len(result.top_docs)
    return float(min(1.0, result.rag_confidence * avg_score * 4.0))
    # ×4 to bring typical low-signal scores (≈0.08) into a visible range


# ── async query ───────────────────────────────────────────────────────────────

def query_async(
    query:       str,
    activations: list[float],
    on_done:     Callable[[float, list], None],
) -> None:
    """
    Spawn a daemon thread to run a PSSPPS vault query.

    Parameters
    ----------
    query       : search text (e.g. track title + " " + artist)
    activations : current 8-shard harmonic index from forest_floor._bridge.index_state()
    on_done     : called from the worker thread with (signal: float, top_docs: list)
                  Callers MUST re-dispatch to the main thread via schedule(0, ...).
    """
    if not query.strip():
        return

    def _worker() -> None:
        if not _ensure_psspps():
            return
        try:
            import numpy as np
            from psspps.pipeline import run_psspps
            arr = np.array(activations, dtype=float)
            result = run_psspps(query, arr)
            signal = _signal(result)
            _log.debug(
                "vault_context: query=%r  triggered=%s  rag_useful=%s  signal=%.3f",
                query[:60], result.retrieval_triggered, result.rag_useful, signal,
            )
            on_done(signal, result.top_docs)
        except Exception as exc:
            _log.warning("vault_context: query failed — %s", exc)

    threading.Thread(target=_worker, daemon=True, name="phi-vault-ctx").start()


# ── Feature extraction ────────────────────────────────────────────────────────

# Keys that AudioFeatures.as_annotation_dict() writes into meta with a
# "spotify_" prefix.  Some models (bpm.py, _derivative_features.py) write
# the bare key directly — we prefer the Spotify value when both exist.
_SPOTIFY_PREFIX = "spotify_"
_BARE_FEATURE_KEYS = frozenset([
    "acousticness", "danceability", "energy", "instrumentalness",
    "liveness", "loudness", "speechiness", "tempo", "valence",
])


def _extract_features(meta: dict) -> Dict[str, float]:
    """
    Pull audio feature floats from a meta dict into bare-key form.

    Handles both ``"spotify_energy"`` (Spotify-enriched) and ``"energy"``
    (BPM/replaygain derived) keys.  Spotify values take precedence.
    Returns only the keys that are actually present and finite.
    """
    import math
    out: Dict[str, float] = {}
    for key in _BARE_FEATURE_KEYS:
        val: Optional[float] = None
        # Prefer the Spotify-prefixed value
        sp_val = meta.get(_SPOTIFY_PREFIX + key)
        if sp_val is not None:
            try:
                v = float(sp_val)
                if math.isfinite(v):
                    val = v
            except (TypeError, ValueError):
                pass
        # Fall back to bare key (from BPM model / librosa)
        if val is None:
            bare_val = meta.get(key)
            if bare_val is not None:
                try:
                    v = float(bare_val)
                    if math.isfinite(v):
                        val = v
                except (TypeError, ValueError):
                    pass
        if val is not None:
            out[key] = val
    return out


# ── Music hub ring singleton ──────────────────────────────────────────────────

_hub_ring: Optional["PhiHubRing"] = None  # type: ignore[name-defined]
_hub_ring_lock = threading.Lock()


def get_hub_ring() -> "PhiHubRing":  # type: ignore[name-defined]
    """
    Return the module-level PhiHubRing singleton, creating it on first call.

    The ring is intentionally lazy so vault_context can be imported at any
    time without pulling in sims.harmonic at module load.
    """
    global _hub_ring
    if _hub_ring is not None:
        return _hub_ring
    with _hub_ring_lock:
        if _hub_ring is None:
            from phi.engine.hub_ring import PhiHubRing
            _hub_ring = PhiHubRing()
            _log.info("vault_context: PhiHubRing singleton created")
    return _hub_ring


# ── Extended query with hub ring ──────────────────────────────────────────────

def query_async_with_ring(
    query:       str,
    meta:        dict,
    on_done:     Callable[[float, list], None],
) -> None:
    """
    Full track-load vault query: inject audio features into the music hub
    ring, then fire a PSSPPS query using the ring's activation vector as
    the harmonic perspective.

    Drop-in replacement for ``query_async`` in ``_vault_query_for_track``.
    The caller's ``on_done(signal, top_docs)`` contract is unchanged.

    Sequence (runs in a daemon thread):
        1. _extract_features(meta) → bare-key audio feature dict
        2. ring.on_track_load(features) → inject + propagate → active spoke queries
        3. run_psspps(query, ring.activation_vector()) — music-domain perspective
        4. signal = _signal(result)
        5. ring.inject("VAULT", signal) — feed confidence back into ring
        6. on_done(signal, top_docs) — caller dispatches to main thread

    Parameters
    ----------
    query    : main PSSPPS query string (track title + artist)
    meta     : track meta dict from library.get_meta() — may contain
               ``"spotify_energy"``, ``"spotify_valence"``, etc.
    on_done  : called from worker thread with (signal: float, top_docs: list)
    """
    if not query.strip():
        return

    ring = get_hub_ring()

    def _worker() -> None:
        # Step 1-2: inject audio features, propagate ring
        features = _extract_features(meta)
        try:
            ring.on_track_load(features, propagate_steps=2, propagate_mode="resonance")
        except Exception as exc:
            _log.warning("vault_context: hub ring injection failed — %s", exc)

        if not _ensure_psspps():
            return

        # Step 3: PSSPPS with music-ring activations + T_B-driven perspective_alpha
        try:
            import numpy as np
            from psspps.pipeline import run_psspps
            activations  = ring._ring.activation_vector()
            t_b_norm     = ring.last_t_b_norm()
            alpha        = _t_b_to_alpha(t_b_norm)
            result       = run_psspps(query, activations, perspective_alpha=alpha)
            signal       = _signal(result)
            _log.debug(
                "vault_context(ring): query=%r  triggered=%s  rag_useful=%s"
                "  signal=%.3f  T_B_norm=%.3f  alpha=%.3f  active_hubs=%s",
                query[:60],
                result.retrieval_triggered,
                result.rag_useful,
                signal,
                t_b_norm,
                alpha,
                ring.active_hubs(),
            )
            # Step 5: feed retrieval confidence back into VAULT hub
            if signal > 0.0:
                try:
                    ring.inject("VAULT", signal)
                except Exception as exc:
                    _log.warning("vault_context: VAULT inject failed — %s", exc)

            on_done(signal, result.top_docs)
        except Exception as exc:
            _log.warning("vault_context(ring): query failed — %s", exc)

    threading.Thread(target=_worker, daemon=True, name="phi-vault-ctx-ring").start()
