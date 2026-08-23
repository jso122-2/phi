"""
Full PSSPPS pipeline.

  query
    │
    ▼
  Router (pre)          → skip retrieval for slash-commands / trivial queries
    │
    ▼
  Retriever             → load all Obsidian vault .md files
    │
    ▼
  Scorer (semantic)     → TF-IDF cosine similarity
  Scorer (perspective)  → harmonic index activation × basin affinity
  Combined score        → (1−α)·semantic + α·perspective
    │
    ▼
  Router (post)         → was RAG actually useful? (lift over mean)
    │
    ▼
  PSPSPSResult          → ranked docs + all scores + routing signals
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from psspps.retriever import VaultDoc, load_vault_docs
from psspps.router import rag_was_useful, should_retrieve
from psspps.scorer import (
    build_tfidf,
    coherence_scores,
    harmonic_affinity,
    modulate_partridge_beta,
    partridge_scores,
    perspective_scores,
    query_vector,
    sem_gated_blend,
    semantic_scores,
)


# Agent-comment nodes get a scoring bonus so they surface above equal-scoring
# station/session nodes.  Small enough not to override high semantic matches.
_COMMENT_BOOST: float = 0.15
_COMMENT_PATH_TOKEN: str = "sessions/comments/"


@dataclass
class ScoredDoc:
    title: str
    path: str
    semantic_score: float
    perspective_score: float
    partridge_score: float
    combined_score: float
    coherence_score: float
    headings: list[str]
    wikilinks: list[str]
    snippet: str


@dataclass
class PSPSPSResult:
    query: str
    retrieval_triggered: bool
    retrieval_confidence: float
    rag_useful: bool
    rag_confidence: float
    top_docs: list[ScoredDoc]
    n_docs_searched: int
    perspective_alpha: float
    partridge_beta: float


def run_psspps(
    query: str,
    index_activations: np.ndarray,
    top_k: int = 3,
    perspective_alpha: float = 0.5,
    partridge_beta: float | None = None,
) -> PSPSPSResult:
    """
    Execute the full PSSPPS pipeline.

    Parameters
    ----------
    query               : natural-language question or search string
    index_activations   : 8-dim float array of current harmonic shard activations
    top_k               : number of top-ranked documents to return
    perspective_alpha   : blend weight — 0.0 = pure semantic, 1.0 = pure perspective
    partridge_beta      : Partridge bubble-sort weight.  None = auto-derived from
                          ledger history (scales 0–0.20).  0.0 disables it.
                          The three weights are renormalised so they sum to 1.0
                          before combining: (1−α−β)·sem + α·persp + β·part.
    """
    # ---- 1. Pre-routing ------------------------------------------------
    retrieve, route_conf = should_retrieve(query)
    if not retrieve:
        return _empty(query, False, route_conf, perspective_alpha, 0.0)

    # ---- 2. Load vault -------------------------------------------------
    docs: list[VaultDoc] = load_vault_docs()
    if not docs:
        return _empty(query, True, route_conf, perspective_alpha, 0.0)

    # ---- 3. Semantic scoring -------------------------------------------
    tfidf_matrix, vocab = build_tfidf([d["clean_text"] for d in docs])
    q_vec = query_vector(query, vocab)
    sem = semantic_scores(q_vec, tfidf_matrix)

    # ---- 4. Perspective scoring ----------------------------------------
    affinities = [harmonic_affinity(d["numbers"]) for d in docs]
    persp = perspective_scores(affinities, index_activations)
    coh = coherence_scores(affinities, index_activations)

    # ---- 5. Partridge scoring ------------------------------------------
    try:
        from graph.tracker import _load as _load_ledger
        ledger = _load_ledger()
    except Exception:
        ledger = {}
    doc_paths = [d["path"] for d in docs]
    part = partridge_scores(doc_paths, ledger)
    beta = partridge_beta if partridge_beta is not None else modulate_partridge_beta(part)
    beta = float(np.clip(beta, 0.0, 0.20))

    # ---- 6. Combined (renormalised weights, semantic-gated) ----------------
    # sem_gated_blend ensures zero-semantic docs cannot win on perspective
    # alone: perspective/Partridge contributions are gated by the semantic
    # score, ramping from 0 at sem=0 to full weight at sem >= _SEM_GATE_FLOOR.
    alpha = float(np.clip(perspective_alpha, 0.0, 1.0))
    final = sem_gated_blend(sem, persp, alpha=alpha, part=part, beta=beta)

    # ---- 6b. Agent-comment boost ---------------------------------------
    # Comment nodes in sessions/comments/ are the memory layer; give them
    # a lift so they win ties against semantically equivalent station notes.
    for i, doc in enumerate(docs):
        if _COMMENT_PATH_TOKEN in doc["path"].replace("\\", "/"):
            final[i] = min(1.0, final[i] + _COMMENT_BOOST)

    # ---- 7. Post-routing -----------------------------------------------
    max_sem = float(np.max(sem))
    mean_sem = float(np.mean(sem))
    useful, rag_conf = rag_was_useful(max_sem, mean_sem)

    # ---- 8. Rank and slice ---------------------------------------------
    ranked = np.argsort(final)[::-1]
    top_docs: list[ScoredDoc] = []
    for idx in ranked[:top_k]:
        doc = docs[idx]
        snippet_src = doc["clean_text"]
        snippet = snippet_src[:220] + "…" if len(snippet_src) > 220 else snippet_src
        top_docs.append(ScoredDoc(
            title=doc["title"],
            path=doc["path"],
            semantic_score=round(float(sem[idx]), 4),
            perspective_score=round(float(persp[idx]), 4),
            partridge_score=round(float(part[idx]), 4),
            combined_score=round(float(final[idx]), 4),
            coherence_score=round(float(coh[idx]), 4),
            headings=doc["headings"][:5],
            wikilinks=doc["wikilinks"][:8],
            snippet=snippet,
        ))

    try:
        from graph.tracker import record
        for i, d in enumerate(top_docs):
            record(d.path, "accessed")
            if i == 0:
                record(d.path, "used")
    except Exception:
        pass

    return PSPSPSResult(
        query=query,
        retrieval_triggered=True,
        retrieval_confidence=round(route_conf, 4),
        rag_useful=useful,
        rag_confidence=round(rag_conf, 4),
        top_docs=top_docs,
        n_docs_searched=len(docs),
        perspective_alpha=perspective_alpha,
        partridge_beta=round(beta, 4),
    )


def _empty(
    query: str,
    triggered: bool,
    route_conf: float,
    alpha: float,
    beta: float = 0.0,
) -> PSPSPSResult:
    return PSPSPSResult(
        query=query,
        retrieval_triggered=triggered,
        retrieval_confidence=round(route_conf, 4),
        rag_useful=False,
        rag_confidence=0.0,
        top_docs=[],
        n_docs_searched=0,
        perspective_alpha=alpha,
        partridge_beta=round(beta, 4),
    )
