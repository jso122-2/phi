# -*- coding: utf-8 -*-
"""
phi.graph.derivative_bridge — bind SongDerivativeModel D4 scores to the PhiGraph.

This module is the seam between the two ML systems:

    SongDerivativeModel (XGBoost, acoustic + social features)
            ↓  {path → {d1, d2, d3, d4}}
    derivative_bridge
            ↓  d4_scores: np.ndarray (N,)  aligned to PhiGraphSnapshot.paths
    PhiGraphSnapshot.d4_scores
            ↓
    cluster_d4_profile()  — per-cluster D4 statistics
    top_k_by_d4()         — rank tracks within a cluster by D4

D4 is the master derivative: the rolling mean of the inbetween mean (D3) across
the sorted library.  It is the primitive handed to subsequent ML systems.

All functions work gracefully if no scores are available (return NaN tensors /
empty profiles), so the topology pipeline keeps running even when the music
library has no phi metadata yet.

Usage
-----
    from phi.graph.derivative_bridge import score_and_attach, cluster_d4_profile

    snapshot = phi_graph.build()
    snapshot = score_and_attach(snapshot)        # attaches d4_scores in-place
    profile  = cluster_d4_profile(clusters, snapshot)
"""
from __future__ import annotations

import logging
import math
from typing import Any, Optional

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Core attachment
# ---------------------------------------------------------------------------

def score_and_attach(
    snapshot: "PhiGraphSnapshot",               # type: ignore[name-defined]
    scores: Optional[dict[str, dict[str, float]]] = None,
) -> "PhiGraphSnapshot":
    """
    Attach D4 scores to a PhiGraphSnapshot.

    If *scores* is None, calls SongDerivativeModel.score_library() for all
    tracks in snapshot.paths.

    The d4_scores tensor is aligned to snapshot.paths (same index ordering).
    Tracks with no D4 entry get NaN.

    Parameters
    ----------
    snapshot : PhiGraphSnapshot  — output of PhiGraph.build()
    scores   : optional pre-computed {path → {d1,d2,d3,d4}} dict.
               Pass this to avoid re-running the XGBoost model when you
               already have the scores from an earlier call.

    Returns
    -------
    The same snapshot object with d4_scores populated (mutated in-place
    for efficiency — the tensor is a new allocation).
    """
    if scores is None:
        scores = _compute_scores(snapshot.paths)

    n = len(snapshot.paths)
    d4 = np.full(n, np.nan, dtype=np.float32)
    for i, path in enumerate(snapshot.paths):
        entry = scores.get(path)
        if entry is not None and entry.get("d4") is not None:
            v = entry["d4"]
            if math.isfinite(v):
                d4[i] = float(v)

    snapshot.d4_scores = d4
    found = int((~np.isnan(d4)).sum())
    logger.info(
        "derivative_bridge: attached d4 scores to %d/%d tracks", found, n
    )
    return snapshot


def _compute_scores(
    paths: list[str],
) -> dict[str, dict[str, float]]:
    """Run SongDerivativeModel on *paths* and return the score dict."""
    try:
        from phi.models.song_derivative import SongDerivativeModel
        return SongDerivativeModel().score_library(paths=paths)
    except Exception as exc:
        logger.warning("derivative_bridge: score_library failed — %s", exc)
        return {}


# ---------------------------------------------------------------------------
# Cluster D4 profiling
# ---------------------------------------------------------------------------

def cluster_d4_profile(
    clusters: list[dict[str, Any]],
    snapshot: "PhiGraphSnapshot",
) -> list[dict[str, Any]]:
    """
    Compute D4 statistics for each cluster.

    Parameters
    ----------
    clusters : list of cluster dicts as returned by SambaOrchestrator.get_clusters()
               Each cluster has {"cluster_id": int, "notes": [{"title", "path", "score"}]}
    snapshot : PhiGraphSnapshot with d4_scores attached via score_and_attach()

    Returns
    -------
    List of dicts — one per cluster — with added fields:
        d4_mean   : mean D4 of embedded tracks in this cluster
        d4_max    : max D4 (top track's score)
        d4_min    : min D4
        d4_spread : d4_max − d4_min  (internal quality dispersion)
        top_track : path of the highest-D4 track in the cluster
        n_scored  : how many cluster notes had a D4 score

    Clusters with no embedded tracks (or no D4 data) get NaN for all metrics.
    """
    if not hasattr(snapshot, "d4_scores") or snapshot.d4_scores is None:
        logger.warning("cluster_d4_profile: snapshot has no d4_scores — call score_and_attach first")
        return [_empty_d4_fields(c) for c in clusters]

    d4 = snapshot.d4_scores           # (N,) float32
    result: list[dict[str, Any]] = []

    for cluster in clusters:
        notes = cluster.get("notes", [])
        vals: list[float] = []
        top_path: Optional[str] = None
        top_val = float("-inf")

        for note in notes:
            path = note.get("path", "")
            idx  = snapshot.index_of(path)
            if idx is None:
                continue
            v = float(d4[idx])
            if not math.isfinite(v):
                continue
            vals.append(v)
            if v > top_val:
                top_val  = v
                top_path = path

        if vals:
            d4_mean   = round(sum(vals) / len(vals), 4)
            d4_max    = round(max(vals), 4)
            d4_min    = round(min(vals), 4)
            d4_spread = round(d4_max - d4_min, 4)
        else:
            d4_mean = d4_max = d4_min = d4_spread = float("nan")
            top_path = None

        result.append({
            **cluster,
            "d4_mean":   d4_mean,
            "d4_max":    d4_max,
            "d4_min":    d4_min,
            "d4_spread": d4_spread,
            "top_track": top_path,
            "n_scored":  len(vals),
        })

    return result


def top_k_by_d4(
    snapshot: "PhiGraphSnapshot",
    k: int = 20,
    cluster_id: Optional[int] = None,
    clusters: Optional[list[dict[str, Any]]] = None,
) -> list[dict[str, Any]]:
    """
    Return the top-k tracks ranked by D4 score.

    If *cluster_id* and *clusters* are given, restricts to tracks in that cluster.

    Parameters
    ----------
    snapshot   : PhiGraphSnapshot with d4_scores attached
    k          : number of top tracks to return
    cluster_id : optional cluster filter
    clusters   : the cluster list from get_clusters() (required if cluster_id set)

    Returns
    -------
    List of dicts: [{path, d4, d1, d2, d3}] sorted D4 descending
    """
    if not hasattr(snapshot, "d4_scores") or snapshot.d4_scores is None:
        return []

    if cluster_id is not None and clusters is not None:
        # filter to paths in the named cluster
        target = next(
            (c for c in clusters if c.get("cluster_id") == cluster_id), None
        )
        candidate_paths = (
            {n["path"] for n in target.get("notes", [])} if target else set()
        )
    else:
        candidate_paths = None  # use all

    d4 = snapshot.d4_scores
    indexed: list[tuple[float, int]] = []
    for i, path in enumerate(snapshot.paths):
        if candidate_paths is not None and path not in candidate_paths:
            continue
        v = float(d4[i])
        if math.isfinite(v):
            indexed.append((v, i))

    indexed.sort(reverse=True)
    out: list[dict[str, Any]] = []
    for v, i in indexed[:k]:
        out.append({"path": snapshot.paths[i], "d4": round(v, 4)})
    return out


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _empty_d4_fields(cluster: dict[str, Any]) -> dict[str, Any]:
    return {
        **cluster,
        "d4_mean":   float("nan"),
        "d4_max":    float("nan"),
        "d4_min":    float("nan"),
        "d4_spread": float("nan"),
        "top_track": None,
        "n_scored":  0,
    }
