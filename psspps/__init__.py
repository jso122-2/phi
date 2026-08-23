"""
PSSPPS — Perspective-Oriented Semantic Scored Personalized Parsing Scored.

A RAG pipeline that:
  1. Infers whether retrieval is worth running  (pre-routing)
  2. Retrieves from the Obsidian knowledge vault
  3. Scores results by semantic similarity + harmonic index perspective
  4. Parses top results into structured output
  5. Infers whether RAG actually helped          (post-routing confidence)

The harmonic index activations act as the "perspective" — which attractor
basins you have been exploring biases retrieval toward related vault documents.
"""

from psspps.pipeline import PSPSPSResult, ScoredDoc, run_psspps
from psspps.scorer import modulate_partridge_beta, partridge_scores, sem_gated_blend
from psspps.traverser import TraversalResult, traverse

__all__ = [
    "run_psspps", "PSPSPSResult", "ScoredDoc",
    "partridge_scores", "modulate_partridge_beta", "sem_gated_blend",
    "traverse", "TraversalResult",
]
