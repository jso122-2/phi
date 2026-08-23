"""Bus tasks: vault search — PSSPPS and Find pipelines."""
from __future__ import annotations

from typing import Any

from mcp_server.bus._task_registry import task


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
        "top_docs": [
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
            }
            for d in result.top_docs
        ],
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
    answer_dict = _candidate_dict(result.answer) if result.answer else None
    try:
        from graph.tracker import record
        for c in result.operator_3:
            record(c.path, "accessed")
        if result.answer is not None:
            record(result.answer.path, "used")
    except Exception:
        pass
    return {
        "query": result.query,
        "mode": mode,
        "n_docs_searched": result.n_docs_searched,
        "modulation": modulation or {},
        "funnel": {
            "stage_1_top5": [_candidate_dict(c) for c in result.candidates_5],
            "stage_2_operator_3": [_candidate_dict(c) for c in result.operator_3],
            "stage_3_answer": answer_dict,
        },
        "answer": answer_dict,
        "vault_sim_tool": "find_query",
        "vault_sim": {
            "query": query,
            "mode": mode,
            "alpha": perspective_alpha,
            "n_docs": result.n_docs_searched,
        },
    }
