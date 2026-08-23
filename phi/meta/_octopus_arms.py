# -*- coding: utf-8 -*-
"""phi.meta._octopus_arms — stateless arm-output extractors for OctopusOrganizer.

Each function takes raw TracerOutput tensors and returns plain Python structures.
No models, no I/O, no state — purely testable in isolation.
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple, TYPE_CHECKING

import numpy as np

from phi.meta._octopus_types import (
    EnrichJob,
    TAG_VOCAB,
    TAG_THRESHOLD,
    PRUNE_WARNING,
    ENRICH_PRIORITY_SPROUT,
    ENRICH_PRIORITY_RESURFACE,
)

if TYPE_CHECKING:
    from phi.gnn.octopus_tracer import TracerOutput


def _to_np(t: Any) -> np.ndarray:
    """Convert torch tensor or numpy array to numpy."""
    if isinstance(t, np.ndarray):
        return t
    if hasattr(t, "detach"):
        return t.detach().cpu().numpy()
    return np.asarray(t)


def _item(v: Any) -> float:
    """Extract a scalar from a tensor element or numpy scalar."""
    if hasattr(v, "item"):
        return float(v.item())
    return float(v)


def build_enrich_queue(
    paths:   List[str],
    sources: Dict[str, str],
    out:     "TracerOutput",
) -> List[EnrichJob]:
    """Sort paths by enrichment priority = sprout×(1−prune) + resurface×0.30.

    CLAP-embedded tracks are de-prioritised (×0.40) since they're already rich.
    Returns list sorted by descending priority.
    """
    jobs = []
    for i, path in enumerate(paths):
        sprout    = _item(out.sprout[i])
        prune_s   = _item(out.prune[i])
        resurface = _item(out.resurface[i])
        source    = sources.get(path, "random")

        priority = (
            sprout * ENRICH_PRIORITY_SPROUT * (1.0 - prune_s)
            + resurface * ENRICH_PRIORITY_RESURFACE
        )
        if source == "clap":
            priority *= 0.40

        arms: List[str] = []
        if sprout    >= 0.60:                 arms.append("sprout")
        if resurface >= 0.60:                 arms.append("resurface")
        if prune_s   >= PRUNE_WARNING:        arms.append("prune!")
        if _item(out.rank[i]) >= 0.80:        arms.append("rank")

        jobs.append(EnrichJob(
            path            = path,
            priority        = round(priority,  5),
            sprout_score    = round(sprout,    4),
            resurface_score = round(resurface, 4),
            prune_score     = round(prune_s,   4),
            embed_source    = source,
            arms_flagging   = arms,
        ))
    jobs.sort(key=lambda j: -j.priority)
    return jobs


def extract_pairs(
    paths:     List[str],
    scores:    Any,
    threshold: float,
) -> List[Tuple[str, str, float]]:
    """Extract (path_a, path_b, score) pairs above threshold from an (N, N) matrix.

    Returns list sorted by descending score.
    """
    pairs: List[Tuple[str, str, float]] = []
    mat = _to_np(scores)
    N   = len(paths)
    for i in range(N):
        for j in range(i + 1, N):
            v = float(mat[i, j])
            if v >= threshold:
                pairs.append((paths[i], paths[j], round(v, 4)))
    pairs.sort(key=lambda t: -t[2])
    return pairs


def build_cluster_map(
    paths:   List[str],
    cluster: Any,
) -> Dict[int, List[str]]:
    """Hard-assign each track to its argmax cluster. Returns {cluster_id: [paths]}."""
    cluster_map: Dict[int, List[str]] = {}
    cids = np.argmax(_to_np(cluster), axis=-1).tolist()
    for path, cid in zip(paths, cids):
        cluster_map.setdefault(int(cid), []).append(path)
    return cluster_map


def build_tag_suggestions(
    paths: List[str],
    tag:   Any,
) -> Dict[str, List[str]]:
    """Return {path: [tag_str, ...]} for all tags above TAG_THRESHOLD."""
    suggestions: Dict[str, List[str]] = {}
    tag_np = _to_np(tag)
    T = min(tag_np.shape[-1], len(TAG_VOCAB))
    for i, path in enumerate(paths):
        row   = tag_np[i, :T]
        above = [(float(row[t]), TAG_VOCAB[t]) for t in range(T) if float(row[t]) >= TAG_THRESHOLD]
        if above:
            above.sort(key=lambda x: -x[0])
            suggestions[path] = [label for _, label in above]
    return suggestions
