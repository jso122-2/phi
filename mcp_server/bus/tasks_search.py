"""Bus tasks: vault search — PSSPPS and Find pipelines."""
from __future__ import annotations

from typing import Any

import numpy as np

from mcp_server.bus._task_registry import task


def _ranked_affinity_inject(
    top_docs: list[dict[str, Any]],
    score_key: str = "combined_score",
    scale: float = 0.15,
) -> dict[str, Any] | None:
    """
    Compute a rank-discounted weighted-mean affinity vector from top ranked docs.

    Weight for rank r (0-indexed): score_r / (r + 1).

    The resulting 8-dim vector is the affinity centroid of what was actually
    retrieved — injecting it back into the index closes the search → shard loop.

    Returns None if no doc carries a valid affinity vector.
    """
    weighted_sum = np.zeros(8, dtype=float)
    total_weight = 0.0

    for rank, doc in enumerate(top_docs[:3]):
        aff = doc.get("affinity")
        score = float(doc.get(score_key) or 0.0)
        if not aff or score <= 0:
            continue
        a = np.asarray(aff, dtype=float)
        a_sum = float(a.sum())
        if a_sum < 1e-12:
            continue
        w = score / (rank + 1)
        weighted_sum[:len(a)] += (w / a_sum) * a
        total_weight += w

    if total_weight < 1e-12:
        return None

    mean_aff = (weighted_sum / total_weight).tolist()
    return {"vec": mean_aff, "scale": scale}


@task("search.psspps")
def search_psspps(
    query: str,
    activations: list[float],
    top_k: int = 3,
    perspective_alpha: float = 0.5,
    modulation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    import numpy as np

    from psspps.pipeline import run_psspps

    vec = np.array(activations, dtype=float)
    result = run_psspps(query, vec, top_k=top_k, perspective_alpha=perspective_alpha)

    top_docs_out = [
        {
            "title": d.title,
            "path": d.path,
            "coherence_score": d.coherence_score,
            "semantic_score": d.semantic_score,
            "perspective_score": d.perspective_score,
            "partridge_score": d.partridge_score,
            "combined_score": d.combined_score,
            "headings": d.headings,
            "wikilinks": d.wikilinks,
            "snippet": d.snippet,
            "affinity": d.affinity,  # 8-dim — feeds shard injection in side_effects
        }
        for d in result.top_docs
    ]

    rai = _ranked_affinity_inject(top_docs_out, score_key="combined_score", scale=0.15)

    return {
        "query": result.query,
        "retrieval_triggered": result.retrieval_triggered,
        "retrieval_confidence": result.retrieval_confidence,
        "rag_useful": result.rag_useful,
        "rag_confidence": result.rag_confidence,
        "n_docs_searched": result.n_docs_searched,
        "perspective_alpha": result.perspective_alpha,
        "partridge_beta": result.partridge_beta,
        "modulation": modulation or {},
        "top_docs": top_docs_out,
        # Side-effects: weighted mean affinity of top docs → shard inject
        "ranked_affinity_inject": rai,
        "vault_sim_tool": "psspps_query",
        "vault_sim": {
            "query": query,
            "alpha": perspective_alpha,
            "beta": result.partridge_beta,
            "source": (modulation or {}).get("source"),
            "rag_useful": result.rag_useful,
            "n_docs": result.n_docs_searched,
        },
    }


@task("search.find")
def search_find(
    query: str,
    activations: list[float],
    mode: str = "pericles",
    harmonic_step: int = 0,
    perspective_alpha: float | None = None,
    modulation: dict[str, Any] | None = None,
    dawn_x: float = 0.0,
) -> dict[str, Any]:
    import numpy as np

    from psspps.find import FindCandidate, run_find

    def _candidate_dict(c: FindCandidate) -> dict[str, Any]:
        return {
            "title": c.title,
            "path": c.path,
            "coherence_score": c.coherence_score,
            "perspective_score": c.perspective_score,
            "combined_score": c.combined_score,
            "pericles": {
                "tc_A": c.pericles.tc_A,
                "Adp_At": c.pericles.Adp_At,
                "k": c.pericles.k,
                "N_j": c.pericles.N_j,
                "D": c.pericles.D,
                "x": c.pericles.x,
                "per": c.pericles.per,
            },
            "headings": c.headings,
            "wikilinks": c.wikilinks,
            "snippet": c.snippet,
        }

    vec = np.array(activations, dtype=float)
    result = run_find(
        query, vec,
        harmonic_step=harmonic_step,
        mode=mode,
        perspective_alpha=perspective_alpha,
        dawn_x=dawn_x,
    )
    def _candidate_dict_with_affinity(c: "FindCandidate") -> dict[str, Any]:
        d = _candidate_dict(c)
        d["affinity"] = c.affinity  # 8-dim — feeds shard injection
        return d

    answer_dict = _candidate_dict_with_affinity(result.answer) if result.answer else None
    try:
        from graph.tracker import record
        for c in result.operator_3:
            record(c.path, "accessed")
        if result.answer is not None:
            record(result.answer.path, "used")
    except Exception:
        pass

    # Rank-discounted affinity inject from operator_3 (Pericles-ranked top docs).
    # Weight by Pericles score (per) — higher per = more evidence for those shards.
    op3_dicts = [_candidate_dict_with_affinity(c) for c in result.operator_3]
    for d, c in zip(op3_dicts, result.operator_3):
        d["_pericles_per"] = c.pericles.per   # carry score for weighting
    rai = _ranked_affinity_inject(
        top_docs=op3_dicts,
        score_key="_pericles_per",
        scale=0.12,
    )

    return {
        "query": result.query,
        "mode": mode,
        "n_docs_searched": result.n_docs_searched,
        "modulation": modulation or {},
        "funnel": {
            "stage_1_top5": [_candidate_dict(c) for c in result.candidates_5],
            "stage_2_operator_3": op3_dicts,
            "stage_3_answer": answer_dict,
        },
        "answer": answer_dict,
        # Side-effects: Pericles-weighted affinity of operator_3 → shard inject
        "ranked_affinity_inject": rai,
        "vault_sim_tool": "find_query",
        "vault_sim": {
            "query": query,
            "mode": mode,
            "alpha": perspective_alpha,
            "n_docs": result.n_docs_searched,
        },
    }
