"""
OrphanDetector — identifies notes that are semantically adrift.

A note is an "orphan" if its maximum soft-assignment score across all K cluster
prototypes falls below `threshold`. These notes don't belong clearly to any
coherent topic region; they are the primary targets for link patching.

Public API:
    OrphanDetector(orchestrator, threshold=0.15)
    .scan(top_k_links=5) -> List[OrphanResult]

Each OrphanResult contains:
    title       Note title
    path        Absolute path to the .md file
    max_score   Highest cluster affinity (the closer to 0.0, the more adrift)
    best_cluster_id  Which cluster this note weakly belongs to
    suggestions  Link suggestions from suggest_links (may be empty)
"""
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class OrphanResult:
    title: str
    path: str
    max_score: float
    best_cluster_id: int
    suggestions: List[Dict] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "title": self.title,
            "path": self.path,
            "max_score": round(self.max_score, 4),
            "best_cluster_id": self.best_cluster_id,
            "suggestions": self.suggestions,
        }


class OrphanDetector:
    """
    Scans the vault for notes with weak cluster membership.

    Args:
        orchestrator: A loaded SambaOrchestrator instance.
        threshold:    Notes with max cluster score below this are orphans.
    """

    def __init__(self, orchestrator, threshold: float = 0.15) -> None:
        self.orch = orchestrator
        self.threshold = threshold

    def scan(self, top_k_links: int = 5) -> List[OrphanResult]:
        """
        Run a full orphan scan.

        Calls get_clusters() once to retrieve all soft assignments, then
        calls suggest_links() for each identified orphan.

        Returns:
            List of OrphanResult sorted by max_score ascending (most adrift first).
        """
        import torch

        logger.info("Running orphan scan (threshold=%.2f)", self.threshold)

        with torch.no_grad():
            # (N, K) soft assignment matrix
            assignments = self.orch.model.cluster(self.orch._h)

        num_notes = assignments.size(0)
        max_scores, best_clusters = assignments.max(dim=1)

        orphans: List[OrphanResult] = []
        for node_id in range(num_notes):
            score = max_scores[node_id].item()
            if score >= self.threshold:
                continue

            note = self.orch._id_to_note(node_id)
            if note is None:
                continue

            cluster_id = best_clusters[node_id].item()
            orphans.append(OrphanResult(
                title=note.title,
                path=note.path,
                max_score=score,
                best_cluster_id=int(cluster_id),
            ))

        # Sort most adrift first
        orphans.sort(key=lambda o: o.max_score)

        logger.info("Found %d orphan notes", len(orphans))

        # Fetch link suggestions for each orphan
        for orphan in orphans:
            try:
                orphan.suggestions = self.orch.suggest_links(orphan.title, top_k=top_k_links)
            except Exception as e:
                logger.warning("suggest_links failed for '%s': %s", orphan.title, e)
                orphan.suggestions = []

        return orphans

    def summary(self, orphans: List[OrphanResult]) -> Dict:
        """Return a compact summary dict for logging or reporting."""
        if not orphans:
            return {"orphan_count": 0, "mean_max_score": None, "top_orphans": []}
        scores = [o.max_score for o in orphans]
        return {
            "orphan_count": len(orphans),
            "mean_max_score": round(sum(scores) / len(scores), 4),
            "top_orphans": [o.to_dict() for o in orphans[:10]],
        }
