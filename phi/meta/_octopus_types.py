# -*- coding: utf-8 -*-
"""phi.meta._octopus_types — value types and vocabulary for the octopus organiser.

Pure data — no torch, no I/O.  Importable in any context, including TYPE_CHECKING blocks.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from phi.gnn.octopus_tracer import TracerOutput


# ── Tag vocabulary ─────────────────────────────────────────────────────────────
# 64 tags the tag arm can assign, spanning genre / mood / energy / era / context.

TAG_VOCAB: List[str] = [
    # Genres (14)
    "electronic", "rock", "jazz", "classical", "hip-hop",
    "pop", "metal", "folk", "r&b", "ambient", "country",
    "latin", "reggae", "blues",
    # Moods (10)
    "calm", "chill", "focused", "energetic", "happy",
    "sad", "angry", "romantic", "dark", "uplifting",
    # Energy / tempo (10)
    "fast", "mid-tempo", "slow", "driving", "hypnotic",
    "complex", "minimal", "percussive", "atmospheric", "cinematic",
    # Production style (9)
    "lo-fi", "hi-fi", "vintage", "modern", "acoustic",
    "produced", "live", "studio", "raw",
    # Listener context (8)
    "workout", "study", "party", "sleep", "commute",
    "cooking", "meditation", "social",
    # Era (7)
    "60s", "70s", "80s", "90s", "00s", "10s", "2020s",
    # Structural (6)
    "vocal", "instrumental", "long-form", "short-form",
    "favourite", "new-discovery",
]

assert len(TAG_VOCAB) == 64, f"TAG_VOCAB must have 64 entries, got {len(TAG_VOCAB)}"


# ── Decision thresholds ────────────────────────────────────────────────────────

MERGE_THRESHOLD          = 0.80   # merge arm score → near-duplicate candidate
GRAFT_THRESHOLD          = 0.65   # graft arm score → suggested link (informational)
TAG_THRESHOLD            = 0.55   # tag arm probability → include in suggested_tags
PRUNE_WARNING            = 0.75   # prune score → flag as possible bad file
ENRICH_PRIORITY_SPROUT   = 1.00
ENRICH_PRIORITY_RESURFACE = 0.30


# ── EnrichJob ─────────────────────────────────────────────────────────────────

@dataclass
class EnrichJob:
    """One track queued for enrichment, with its organiser scores.

    Attributes
    ----------
    path             Absolute track path.
    priority         Composite enrichment priority ∈ [0, 1+].
    sprout_score     arm_sprout — isolation in the graph.
    resurface_score  arm_resurface — burial signal.
    prune_score      arm_prune — quality concern flag.
    embed_source     How H was built: ``"clap"`` | ``"librosa"`` | ``"random"``.
    arms_flagging    Arms with above-threshold scores for this track.
    """
    path:            str
    priority:        float
    sprout_score:    float
    resurface_score: float
    prune_score:     float
    embed_source:    str
    arms_flagging:   List[str] = field(default_factory=list)

    def __repr__(self) -> str:
        flags = ", ".join(self.arms_flagging) or "none"
        return (
            f"EnrichJob({Path(self.path).name!r}  "
            f"pri={self.priority:.3f}  "
            f"sprout={self.sprout_score:.2f}  "
            f"prune={self.prune_score:.2f}  "
            f"src={self.embed_source}  "
            f"flags=[{flags}])"
        )


# ── OrganizationPlan ──────────────────────────────────────────────────────────

@dataclass
class OrganizationPlan:
    """Full intelligence report from OctopusOrganizer.organise().

    Attributes
    ----------
    enrich_queue     Ordered list of EnrichJobs, highest priority first.
    merge_pairs      Near-duplicate candidates: (path_a, path_b, confidence).
    cluster_map      {cluster_id: [paths]} — soft cluster hard-assignments.
    suggested_tags   {path: [tag_str, ...]} — tag arm suggestions.
    prune_flags      {path: prune_score} — possible corrupt / low-quality files.
    graft_pairs      Suggested connections: (path_a, path_b, score).
    n_clap           Tracks embedded via CLAP projection.
    n_librosa        Tracks embedded via librosa cold-start.
    n_random         Tracks embedded via random stable vector (no features).
    tracer_output    Raw TracerOutput for downstream inspection.
    """
    enrich_queue:   List[EnrichJob]
    merge_pairs:    List[Tuple[str, str, float]]
    cluster_map:    Dict[int, List[str]]
    suggested_tags: Dict[str, List[str]]
    prune_flags:    Dict[str, float]
    graft_pairs:    List[Tuple[str, str, float]]
    n_clap:         int                          = 0
    n_librosa:      int                          = 0
    n_random:       int                          = 0
    tracer_output:  Optional["TracerOutput"]     = None

    @property
    def n_total(self) -> int:
        """Total number of tracks in the plan."""
        return len(self.enrich_queue)

    @property
    def cluster_map_by_path(self) -> Dict[str, int]:
        """Invert cluster_map → {path: cluster_id} for O(1) annotation writes."""
        result: Dict[str, int] = {}
        for cid, paths in self.cluster_map.items():
            for p in paths:
                result[p] = cid
        return result

    @property
    def graft_map_by_path(self) -> Dict[str, List[Tuple[str, float]]]:
        """Build {path: [(linked_path, score), ...]} for the top graft neighbours."""
        result: Dict[str, List[Tuple[str, float]]] = {}
        for pa, pb, score in self.graft_pairs:
            result.setdefault(pa, []).append((pb, score))
            result.setdefault(pb, []).append((pa, score))
        return result

    @property
    def coverage_pct(self) -> float:
        """Percentage of tracks with CLAP-quality embeddings."""
        total = self.n_clap + self.n_librosa + self.n_random
        return round(self.n_clap / max(total, 1) * 100, 1)

    def summary(self) -> str:
        """One-screen textual summary of the plan for logging."""
        lines = [
            f"OrganizationPlan  n={self.n_total}  clap={self.n_clap}"
            f"  librosa={self.n_librosa}  random={self.n_random}"
            f"  clap_coverage={self.coverage_pct}%",
            f"  merge_pairs={len(self.merge_pairs)}"
            f"  graft_pairs={len(self.graft_pairs)}"
            f"  prune_flagged={len(self.prune_flags)}",
            f"  clusters={len(self.cluster_map)}",
            "  top-5 enrich queue:",
        ]
        for job in self.enrich_queue[:5]:
            lines.append(f"    {job}")
        return "\n".join(lines)
