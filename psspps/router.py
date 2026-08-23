"""
RAG routing for PSSPPS — two decision points.

Pre-routing   — given the raw query, should we retrieve at all?
Post-routing  — given the retrieval scores, did RAG actually help?

Both return a (decision: bool, confidence: float) pair so callers can
propagate uncertainty through the pipeline.
"""
from __future__ import annotations

import re

import numpy as np

# Words that signal an information-seeking query
_SEEK_WORDS = frozenset({
    "what", "how", "why", "where", "when", "explain", "describe",
    "define", "tell", "show", "which", "who", "mean", "means",
    "difference", "compare", "about", "find", "get", "understand",
    "look", "search", "query", "help", "is", "are", "does", "can",
})

# Slash-command pattern — no retrieval needed for these
_CMD_RE = re.compile(r"^\s*/\w+")


def should_retrieve(query: str) -> tuple[bool, float]:
    """
    Pre-routing: decide whether to run retrieval for this query.

    Returns
    -------
    retrieve   : True if retrieval is recommended
    confidence : estimated confidence in that decision ∈ [0, 1]
    """
    q = query.strip()

    if _CMD_RE.match(q):
        return False, 0.97

    tokens = set(re.findall(r"[a-z]+", q.lower()))
    overlap = len(tokens & _SEEK_WORDS)

    # More trigger words → higher confidence retrieval is warranted
    confidence = float(np.clip(0.45 + 0.10 * overlap, 0.0, 0.95))
    return True, confidence


def rag_was_useful(
    max_semantic_score: float,
    mean_semantic_score: float,
    threshold: float = 0.05,
) -> tuple[bool, float]:
    """
    Post-routing: given the retrieval scores, estimate whether RAG helped.

    The lift (max − mean) measures how much the top result stands above the
    noise floor.  A lift of ≥ 0.30 maps to full confidence; zero lift maps
    to zero confidence.

    Returns
    -------
    useful         : True if max score exceeds threshold
    rag_confidence : calibrated usefulness estimate ∈ [0, 1]
    """
    lift = max_semantic_score - mean_semantic_score
    rag_confidence = float(np.clip(lift / 0.30, 0.0, 1.0))
    return max_semantic_score > threshold, rag_confidence
