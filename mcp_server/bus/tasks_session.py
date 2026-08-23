"""Bus tasks: graph session — commit, traverse, topo-hubs."""
from __future__ import annotations

from typing import Any

from mcp_server.bus._task_registry import task


@task("graph.commit")
def graph_commit(
    prompt: str,
    thinking: str,
    outcome: str,
    activations: list[float] | None = None,
    perspective_alpha: float = 0.3,
) -> dict[str, Any]:
    import numpy as np

    from graph.logger import log_session

    vec = np.array(activations if activations is not None else [0.0] * 8, dtype=float)
    result = log_session(
        prompt=prompt,
        thinking=thinking,
        outcome=outcome,
        index_activations=vec,
        perspective_alpha=perspective_alpha,
    )
    result["touch_commit"] = True
    return result


@task("graph.traverse")
def graph_traverse(
    seed: str,
    max_hops: int = 8,
    context_budget: int = 4_000,
    top_k: int = 3,
    sim_floor: float = 0.10,
) -> dict[str, Any]:
    from psspps.embedder import embed_docs
    from psspps.retriever import load_vault_docs
    from psspps.traverser import traverse

    docs = load_vault_docs()
    if not docs:
        return {"error": "No vault documents found."}
    embeddings = embed_docs(docs)  # type: ignore[arg-type]
    result = traverse(
        seed, docs, embeddings,  # type: ignore[arg-type]
        max_hops=max_hops, context_budget=context_budget,
        top_k=top_k, sim_floor=sim_floor,
    )
    out = result.to_dict()
    try:
        from graph.tracker import record_stems
        record_stems(list(result.path), "accessed")
    except Exception:
        pass
    out["traverse_seed"] = seed
    out["traverse_path"] = list(result.path)
    return out


@task("graph.topo_hubs")
def graph_topo_hubs(
    min_component_size: int = 2,
    write_tags: bool = False,
    prefix_filter: str = "",
    apply_cairrn: bool = False,
) -> dict[str, Any]:
    from graph.node import load_vault
    from graph.topo_graph import build as topo_build
    from graph.topology_index import fusion_from_report
    from graph.worker import run_topo_hubs

    nodes = load_vault()
    if prefix_filter:
        nodes = [n for n in nodes if n.stem.startswith(prefix_filter)]
    report = run_topo_hubs(
        vault=nodes,
        min_component_size=min_component_size,
        write_tags=write_tags,
        prefix_filter="",
    )
    G = topo_build(nodes)
    fusion = fusion_from_report(report, G)
    if apply_cairrn:
        fusion = dict(fusion, apply_cairrn=True)
    top_hubs = sorted(
        report.components,
        key=lambda c: (c.hub_in_degree, c.hub_total_degree),
        reverse=True,
    )[:20]
    return {
        "beta_0": report.n_components,
        "n_nodes": report.n_nodes,
        "n_edges": report.n_edges,
        "n_elected": report.n_elected,
        "n_singletons": report.n_singletons,
        "tags_written": write_tags,
        "prefix_filter": prefix_filter or "(none — full vault)",
        "top_hubs": [
            {
                "hub": c.hub,
                "in_degree": c.hub_in_degree,
                "total_degree": c.hub_total_degree,
                "component_size": c.size,
                "n_spokes": len(c.spokes),
                "already_tagged": c.already_hub_tagged,
                "spokes_sample": c.spokes[:20],
            }
            for c in top_hubs
        ],
        "topology_fusion": fusion,
        "touch_harmonic": True,
    }
