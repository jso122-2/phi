# -*- coding: utf-8 -*-
"""phi.graph.phi_tracer_bridge — write OctopusTracer arm outputs to Library.annotations.

The bridge is the final step of each PhiOrchestrator cycle.  It takes a
`TracerOutput` and the ordered track `paths` list and writes actionable signals
back into the Phi Library as annotation keys so that the enrichment pipeline,
UI, and smart playlists can act on them.

Written annotation keys (all prefixed `phi_`):
    phi_cluster        int      — argmax cluster assignment (ClusterArm)
    phi_rank           float    — within-cluster relevance score (RankArm)
    phi_prune          float    — deletion candidacy score in [0, 1] (PruneArm)
    phi_resurface      float    — burial score in [0, 1] (ResurfaceArm)
    phi_sprout         float    — structural gap score in [0, 1] (SproutArm)
    phi_tags           list[str] — suggested tags above TAG_THRESHOLD (TagArm)
    phi_graft          list[str] — paths of high-probability missing links (GraftArm)
    phi_merge_candidate str|None — path of nearest near-duplicate (MergeArm)
    phi_topo_chi       float    — Euler characteristic from TopologicalGraph
    phi_topo_beta0     int      — connected components
    phi_topo_beta1     int      — independent cycles

The topology fields are written from the TopologicalGraph invariant so that
the Phi UI and smart playlists can surface topology health alongside arm scores.

Design
──────
`PhiTracerBridge` uses the *stateless* arm extractors in
`phi.meta._octopus_arms` to decode tensors into Python structures, then
writes directly to `library.annotations[path]`.  It does NOT run the tracer —
it only interprets and persists the output.

Usage
─────
    bridge = PhiTracerBridge(library, tag_vocab=TAG_VOCAB)
    bridge.write(tracer_out, snap, topo)
    # library.annotations["/.../track.mp3"]["phi_cluster"] → 3
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable, List, Optional

from phi.meta._octopus_types import (
    TAG_VOCAB,
    MERGE_THRESHOLD,
    GRAFT_THRESHOLD,
    TAG_THRESHOLD,
    PRUNE_WARNING,
)
from phi.meta._octopus_arms import (
    build_cluster_map,
    build_tag_suggestions,
    extract_pairs,
)

if TYPE_CHECKING:
    from phi.core.library import Library
    from phi.graph.phi_graph import PhiGraphSnapshot
    from phi.gnn.octopus_tracer import TracerOutput
    from phi.topology.topo_graph import TopologicalGraph

logger = logging.getLogger(__name__)


class PhiTracerBridge:
    """
    Persists OctopusTracer arm outputs to Library.annotations.

    All writes are additive — existing non-phi annotation keys are preserved.
    Call write() once per PhiOrchestrator cycle after the tracer forward pass.

    Args:
        library:       Phi Library instance (annotations are written here)
        tag_vocab:     Tag vocabulary list (default: TAG_VOCAB from _octopus_types)
        prune_floor:   Prune score above which phi_prune is written (default 0)
        graft_top_k:   Max graft suggestions per track (default 5)
        merge_top_k:   Max merge candidates per track (default 1 nearest)
    """

    def __init__(
        self,
        library:    "Library",
        tag_vocab:  Optional[List[str]] = None,
        prune_floor: float = 0.0,
        graft_top_k: int   = 5,
        merge_top_k: int   = 1,
        on_write: Optional[Callable[[List[str]], None]] = None,
    ) -> None:
        self._library    = library
        self._tag_vocab  = tag_vocab or TAG_VOCAB
        self._prune_floor = prune_floor
        self._graft_top_k = graft_top_k
        self._merge_top_k = merge_top_k
        # Called after every write() with paths sorted by SCUP descending.
        # Wire queue.nudge() here for 0-latency async GNN enrichment.
        self._on_write   = on_write

    # ── public write ──────────────────────────────────────────────────────────

    def write(
        self,
        out:  "TracerOutput",
        snap: "PhiGraphSnapshot",
        topo: Optional["TopologicalGraph"] = None,
    ) -> dict:
        """
        Write all arm outputs and optional topology invariants to library.annotations.

        Args:
            out:  TracerOutput from OctopusTracer.forward()
            snap: PhiGraphSnapshot — provides the ordered paths list
            topo: Optional TopologicalGraph — if supplied, writes phi_topo_* fields

        Returns:
            Summary dict with per-arm write counts for logging / MCP reporting.
        """
        paths = snap.paths
        N     = len(paths)

        if N == 0:
            logger.warning("PhiTracerBridge.write: empty paths — nothing to write.")
            return {}

        # ── Decode arm outputs ─────────────────────────────────────────────────

        # Scalar arms — per-node float in [0, 1]
        # Support both torch tensors (OctopusTracer) and plain numpy arrays
        def _to_array(t):
            if hasattr(t, "cpu"):
                return t.cpu().float()
            return t
        prune_cpu     = _to_array(out.prune)
        rank_cpu      = _to_array(out.rank)
        resurface_cpu = _to_array(out.resurface)
        sprout_cpu    = _to_array(out.sprout)

        # Cluster arm → hard assignment
        cluster_map = build_cluster_map(paths, out.cluster)      # {cid: [paths]}
        path_to_cid = {p: cid for cid, ps in cluster_map.items() for p in ps}

        # Tag arm → suggested tags above threshold
        tag_suggestions = build_tag_suggestions(paths, out.tag)  # {path: [tags]}

        # Graft arm → suggested missing links
        graft_pairs = extract_pairs(paths, out.graft, threshold=GRAFT_THRESHOLD)
        graft_map: dict[str, list[str]] = {}
        for pa, pb, _score in graft_pairs:
            graft_map.setdefault(pa, []).append(pb)
            graft_map.setdefault(pb, []).append(pa)

        # Merge arm → near-duplicate pairs (nearest candidate only per track)
        merge_pairs = extract_pairs(paths, out.merge, threshold=MERGE_THRESHOLD)
        merge_map: dict[str, str] = {}
        for pa, pb, _score in merge_pairs:
            if pa not in merge_map:
                merge_map[pa] = pb
            if pb not in merge_map:
                merge_map[pb] = pa

        # Topology invariants — attached once if topo is supplied
        topo_fields: dict = {}
        if topo is not None:
            try:
                inv = topo.invariant
                topo_fields = {
                    "phi_topo_chi":   round(float(inv.chi),    4),
                    "phi_topo_beta0": int(inv.beta_0),
                    "phi_topo_beta1": int(inv.beta_1),
                }
            except RuntimeError:
                pass   # topo not built yet — skip topology fields

        # ── Write per-track annotations ────────────────────────────────────────
        counts = {
            "prune": 0, "rank": 0, "resurface": 0, "sprout": 0,
            "cluster": 0, "tags": 0, "graft": 0, "merge": 0, "topo": 0,
        }

        for i, path in enumerate(paths):
            ann = self._library.annotations.setdefault(path, {})

            # Scalar arms
            ann["phi_prune"]     = round(float(prune_cpu[i]),     4)
            ann["phi_rank"]      = round(float(rank_cpu[i]),      4)
            ann["phi_resurface"] = round(float(resurface_cpu[i]), 4)
            ann["phi_sprout"]    = round(float(sprout_cpu[i]),    4)
            counts["prune"]     += 1
            counts["rank"]      += 1
            counts["resurface"] += 1
            counts["sprout"]    += 1

            # Cluster
            cid = path_to_cid.get(path)
            if cid is not None:
                ann["phi_cluster"] = int(cid)
                counts["cluster"] += 1

            # Tags
            suggested = tag_suggestions.get(path)
            if suggested:
                ann["phi_tags"] = suggested
                counts["tags"] += 1

            # Graft suggestions (top-k missing links)
            grafts = graft_map.get(path, [])[:self._graft_top_k]
            if grafts:
                ann["phi_graft"] = grafts
                counts["graft"] += 1

            # Merge candidate
            merge_c = merge_map.get(path)
            ann["phi_merge_candidate"] = merge_c
            if merge_c:
                counts["merge"] += 1

            # Topology invariants (same for every track in this snapshot)
            if topo_fields:
                ann.update(topo_fields)
                counts["topo"] += 1

        # ── CAIRRN coherence metadata on TracerOutput ──────────────────────────
        for path in paths:
            ann = self._library.annotations.setdefault(path, {})
            ann["phi_coherence_score"] = round(out.coherence_score, 4)
            ann["phi_write_gated"]     = bool(out.write_gated)

        logger.info(
            "PhiTracerBridge wrote %d tracks: prune=%d cluster=%d tags=%d "
            "graft=%d merge=%d topo=%d",
            N, counts["prune"], counts["cluster"], counts["tags"],
            counts["graft"], counts["merge"], counts["topo"],
        )

        # Fire on_write with paths sorted by F_SCUP_CANONICAL descending.
        # phi_rank is S_i inside SCUP; skip pressure and TP-RAR move the queue.
        # queue.nudge() freezes now-playing and the pre-buffered slot.
        if self._on_write is not None:
            try:
                from phi.core.ranker import TrackRanker
                ranked = TrackRanker().rank_by_scup(paths, self._library)
            except Exception:
                logger.debug(
                    "PhiTracerBridge: SCUP rank failed — falling back to phi_rank",
                    exc_info=True,
                )
                ranked = sorted(
                    paths,
                    key=lambda p: self._library.annotations.get(p, {}).get("phi_rank", 0.5),
                    reverse=True,
                )
            try:
                self._on_write(ranked)
            except Exception:
                logger.debug("PhiTracerBridge.on_write callback failed", exc_info=True)

        return {
            "n_tracks":  N,
            "arm_counts": counts,
            "topo_attached": bool(topo_fields),
        }

    # ── read-back helpers (for testing / MCP reporting) ───────────────────────

    def get_prune_candidates(self, threshold: float = PRUNE_WARNING) -> List[str]:
        """Return paths with phi_prune ≥ threshold."""
        return [
            p for p in self._library.playlist
            if self._library.annotations.get(p, {}).get("phi_prune", 0.0) >= threshold
        ]

    def get_resurface_candidates(self, threshold: float = 0.60) -> List[str]:
        """Return paths with phi_resurface ≥ threshold."""
        return [
            p for p in self._library.playlist
            if self._library.annotations.get(p, {}).get("phi_resurface", 0.0) >= threshold
        ]

    def get_sprout_candidates(self, threshold: float = 0.60) -> List[str]:
        """Return paths with phi_sprout ≥ threshold — structural gap nodes."""
        return [
            p for p in self._library.playlist
            if self._library.annotations.get(p, {}).get("phi_sprout", 0.0) >= threshold
        ]

    def get_merge_pairs(self) -> List[tuple]:
        """Return (path_a, path_b) pairs from phi_merge_candidate annotations."""
        seen: set = set()
        pairs: List[tuple] = []
        for p in self._library.playlist:
            candidate = self._library.annotations.get(p, {}).get("phi_merge_candidate")
            if candidate and candidate in self._library.annotations:
                key = tuple(sorted([p, candidate]))
                if key not in seen:
                    seen.add(key)
                    pairs.append(key)
        return pairs

    def annotation_summary(self, path: str) -> dict:
        """Return all phi_* annotation fields for a single track."""
        ann = self._library.annotations.get(path, {})
        return {k: v for k, v in ann.items() if k.startswith("phi_")}
