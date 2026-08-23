"""
BridgeFactory — detects isolated cluster pairs and generates bridge note specs.

Two clusters are "isolated" if there are fewer explicit inter-cluster wikilinks
than `min_bridges`. For each such pair, the factory proposes a bridge note that
can be written to the vault by VaultWriter.create_bridge_note().

Public API:
    BridgeFactory(orchestrator, min_bridges=1)
    .scan() -> List[BridgeSpec]

Each BridgeSpec contains:
    cluster_a_id     First cluster index
    cluster_b_id     Second cluster index
    title            Proposed title for the bridge note
    cluster_a_note   Title of the top note in cluster A (becomes a wikilink)
    cluster_b_note   Title of the top note in cluster B (becomes a wikilink)
    body             Short connecting sentence, constructed without an LLM
    inter_link_count Number of existing explicit links between the two clusters
"""
import logging
from dataclasses import dataclass
from itertools import combinations
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class BridgeSpec:
    cluster_a_id: int
    cluster_b_id: int
    title: str
    cluster_a_note: str
    cluster_b_note: str
    body: str
    inter_link_count: int

    def to_dict(self) -> Dict:
        return {
            "cluster_a_id": self.cluster_a_id,
            "cluster_b_id": self.cluster_b_id,
            "title": self.title,
            "cluster_a_note": self.cluster_a_note,
            "cluster_b_note": self.cluster_b_note,
            "body": self.body,
            "inter_link_count": self.inter_link_count,
        }


class BridgeFactory:
    """
    Scans for isolated cluster pairs and produces bridge note specs.

    Args:
        orchestrator:     A loaded SambaOrchestrator instance.
        min_bridges:      Pairs with fewer existing inter-cluster wikilinks
                          than this value are considered isolated.
        min_cluster_score: Minimum cluster assignment score for a note to be
                          considered a cluster representative.
    """

    def __init__(
        self,
        orchestrator,
        min_bridges: int = 1,
        min_cluster_score: float = 0.20,
    ) -> None:
        self.orch = orchestrator
        self.min_bridges = min_bridges
        self.min_cluster_score = min_cluster_score

    def scan(self) -> List[BridgeSpec]:
        """
        Return bridge specs for all cluster pairs with insufficient cross-links.

        Process:
        1. Retrieve cluster soft assignments.
        2. For each cluster, identify the top-scoring representative note.
        3. For each pair of clusters that both have a representative, count
           how many explicit wikilink edges cross between them in the graph.
        4. Emit a BridgeSpec for pairs below the min_bridges threshold.

        Returns:
            List of BridgeSpec sorted by inter_link_count ascending.
        """
        import torch

        logger.info("Running bridge scan (min_bridges=%d)", self.min_bridges)

        with torch.no_grad():
            assignments = self.orch.model.cluster(self.orch._h)  # (N, K)

        K = assignments.size(1)

        # Map each cluster to its best-scoring note (if above threshold)
        cluster_reps: Dict[int, Tuple[int, str, float]] = {}  # k -> (node_id, title, score)
        for k in range(K):
            scores = assignments[:, k]
            best_id = scores.argmax().item()
            best_score = scores[best_id].item()
            if best_score < self.min_cluster_score:
                continue
            note = self.orch._id_to_note(best_id)
            if note is None:
                continue
            cluster_reps[k] = (best_id, note.title, best_score)

        active_clusters = list(cluster_reps.keys())
        if len(active_clusters) < 2:
            logger.info("Fewer than 2 active clusters — no bridges needed")
            return []

        # Build a set of wikilink edges for fast lookup
        wikilink_edges = self._wikilink_edge_set()

        # Assign each node to its argmax cluster (hard assignment for edge counting)
        hard_assignments = assignments.argmax(dim=1).cpu().tolist()

        specs: List[BridgeSpec] = []
        for ka, kb in combinations(active_clusters, 2):
            count = self._inter_cluster_links(
                ka, kb, hard_assignments, wikilink_edges
            )
            if count < self.min_bridges:
                _, title_a, _ = cluster_reps[ka]
                _, title_b, _ = cluster_reps[kb]
                bridge_title = f"Bridge — {self._short(title_a)} · {self._short(title_b)}"
                body = (
                    f"Connects concepts from cluster {ka} ([[{title_a}]]) "
                    f"and cluster {kb} ([[{title_b}]])."
                )
                specs.append(BridgeSpec(
                    cluster_a_id=ka,
                    cluster_b_id=kb,
                    title=bridge_title,
                    cluster_a_note=title_a,
                    cluster_b_note=title_b,
                    body=body,
                    inter_link_count=count,
                ))

        specs.sort(key=lambda s: s.inter_link_count)
        logger.info("Found %d cluster pairs needing bridges", len(specs))
        return specs

    # ──────────────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _wikilink_edge_set(self) -> set:
        """Return set of (src_node_id, dst_node_id) for wikilink edges only."""
        edges = set()
        G = self.orch.graph.nx_graph
        for src, dst, data in G.edges(data=True):
            if data.get("edge_type") == "wikilink":
                edges.add((src, dst))
                edges.add((dst, src))  # treat as undirected
        return edges

    def _inter_cluster_links(
        self,
        ka: int,
        kb: int,
        hard_assignments: List[int],
        wikilink_edges: set,
    ) -> int:
        """Count existing wikilink edges that cross between cluster ka and kb."""
        nodes_a = {i for i, c in enumerate(hard_assignments) if c == ka}
        nodes_b = {i for i, c in enumerate(hard_assignments) if c == kb}
        count = 0
        for src, dst in wikilink_edges:
            if (src in nodes_a and dst in nodes_b) or (src in nodes_b and dst in nodes_a):
                count += 1
        return count

    @staticmethod
    def _short(title: str, max_words: int = 4) -> str:
        """Return a shortened version of a title for use in bridge note names."""
        words = title.split()
        if len(words) <= max_words:
            return title
        return " ".join(words[:max_words]) + "…"
