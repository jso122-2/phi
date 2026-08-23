"""
Minecart graph traversal — semantic rail-riding through the vault.

Metaphor
--------
The vault is a mine.  Each document is a chamber connected by rails whose
gauge is cosine similarity.  The minecart:

  1. Starts at a seed (query string or vault note title).
  2. At each hop embeds its *current context window* (all text accumulated
     so far), then finds the nearest unvisited chamber.
  3. Loads the new chamber's content into the context window.
  4. Stops when it runs out of track (max_hops) or its context budget is
     exhausted (context_budget chars).

The context window is the "minecart" — it carries meaning as it travels,
so later hops are biased toward documents relevant to the *accumulated
journey*, not just the starting point.

Public surface
--------------
    traverse(seed, docs, embeddings, *, max_hops, context_budget, top_k)
    -> TraversalResult
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from typing import Callable

from psspps.embedder import cosine_matrix, embed as _default_embed


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class Hop:
    index: int
    title: str
    similarity: float
    chars_added: int
    budget_remaining: int


@dataclass
class TraversalResult:
    seed: str
    path: list[str] = field(default_factory=list)
    hops: list[Hop] = field(default_factory=list)
    full_text: str = ""
    total_chars: int = 0
    stopped_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "seed": self.seed,
            "path": self.path,
            "n_hops": len(self.hops),
            "hops": [
                {
                    "index": h.index,
                    "title": h.title,
                    "similarity": round(h.similarity, 6),
                    "chars_added": h.chars_added,
                    "budget_remaining": h.budget_remaining,
                }
                for h in self.hops
            ],
            "total_chars": self.total_chars,
            "stopped_reason": self.stopped_reason,
        }


# ---------------------------------------------------------------------------
# Core traversal
# ---------------------------------------------------------------------------


def traverse(
    seed: str,
    docs: list[dict],
    embeddings: np.ndarray,
    *,
    max_hops: int = 8,
    context_budget: int = 4_000,
    top_k: int = 3,
    sim_floor: float = 0.10,
    embed_fn: Callable[[list[str]], np.ndarray] | None = None,
) -> TraversalResult:
    """
    Ride the semantic rail from `seed` through vault documents.

    Parameters
    ----------
    seed:
        Query string or a vault note title (matched case-insensitively).
        If a title match is found the minecart boards there; otherwise the
        seed string is embedded directly.
    docs:
        List of VaultDoc dicts (from psspps.retriever.load_vault_docs).
    embeddings:
        Precomputed corpus embeddings, shape (N, 384).
    max_hops:
        Maximum number of chambers to visit.
    context_budget:
        Maximum total characters the minecart can carry.  When adding the
        next doc would exceed this, the cart stops.
    top_k:
        At each hop, consider the top-k nearest neighbours and pick the
        first one that still has budget room.
    sim_floor:
        Minimum cosine similarity to keep riding.  Below this the rail ends.

    Returns
    -------
    TraversalResult
    """
    _embed = embed_fn if embed_fn is not None else _default_embed

    result = TraversalResult(seed=seed)
    visited: set[int] = set()
    context_text = seed
    budget_left = context_budget

    # ── Resolve seed to a starting doc if title matches ──────────────────────
    seed_lower = seed.lower()
    start_idx: int | None = None
    for i, d in enumerate(docs):
        if d["title"].lower() == seed_lower:
            start_idx = i
            break

    if start_idx is not None:
        # Board the matching doc first (hop 0)
        doc = docs[start_idx]
        chunk = doc["clean_text"][:context_budget]
        result.path.append(doc["title"])
        result.hops.append(
            Hop(
                index=start_idx,
                title=doc["title"],
                similarity=1.0,
                chars_added=len(chunk),
                budget_remaining=budget_left - len(chunk),
            )
        )
        visited.add(start_idx)
        context_text = chunk
        budget_left -= len(chunk)
        result.total_chars += len(chunk)
        result.full_text = chunk

        if budget_left <= 0:
            result.stopped_reason = "budget_exhausted_at_seed"
            return result

    # ── Ride the rails ───────────────────────────────────────────────────────
    for _ in range(max_hops):
        # Embed the current context (what the minecart is carrying)
        query_vec = _embed([context_text])[0]

        sims = cosine_matrix(query_vec, embeddings)
        # Mask visited
        sims[list(visited)] = -1.0

        # Pick top-k candidates
        top_indices = np.argsort(sims)[::-1][:top_k]
        if len(top_indices) == 0:
            result.stopped_reason = "no_candidates"
            break
        chosen: int | None = None
        chosen_sim: float = 0.0

        for idx in top_indices:
            sim = float(sims[idx])
            if sim < sim_floor:
                break
            doc_len = len(docs[idx]["clean_text"])
            if doc_len <= budget_left:
                chosen = int(idx)
                chosen_sim = sim
                break

        if chosen is None:
            result.stopped_reason = (
                "sim_floor_reached"
                if float(sims[top_indices[0]]) < sim_floor
                else "budget_exhausted"
            )
            break

        doc = docs[chosen]
        chunk = doc["clean_text"][:budget_left]
        visited.add(chosen)

        result.path.append(doc["title"])
        budget_left -= len(chunk)
        result.total_chars += len(chunk)
        result.full_text += "\n\n" + chunk
        result.hops.append(
            Hop(
                index=chosen,
                title=doc["title"],
                similarity=chosen_sim,
                chars_added=len(chunk),
                budget_remaining=budget_left,
            )
        )

        # Update minecart context
        context_text = result.full_text[-context_budget:]

        if budget_left <= 0:
            result.stopped_reason = "budget_exhausted"
            break
    else:
        result.stopped_reason = "max_hops_reached"

    return result


# ---------------------------------------------------------------------------
# Convenience: resolve seed title → first doc index (or -1)
# ---------------------------------------------------------------------------


def find_doc_by_title(docs: list[dict], title: str) -> int:
    t = title.lower()
    for i, d in enumerate(docs):
        if d["title"].lower() == t:
            return i
    return -1
