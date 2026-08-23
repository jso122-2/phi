"""Bus tasks: phi studio build and warmup tasks."""
from __future__ import annotations

from typing import Any

from mcp_server.bus._task_registry import task


@task("studio.build")
def studio_build(
    seeds: list[str],
    arc_shape: str = "flat",
    target_count: int = 20,
    max_per_artist: int = 2,
    max_per_genre: int = 3,
    transition_threshold: float = 0.60,
    candidate_pool: int = 15,
    arc_weight: float = 0.60,
    sim_weight: float = 0.40,
    arc_sharpness: float = 20.0,
    playlist: list[str] | None = None,
    annotations: dict[str, Any] | None = None,
    meta_cache: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from phi.core.library import Library
    from phi.engine.arc_engine import ArcShape
    from phi.engine.playlist_studio import PlaylistStudio, StudioRequest
    from phi.session import filter_existing, restore

    lib = Library()
    paths = playlist if playlist is not None else []
    if not paths:
        state = restore() or {}
        paths = list(state.get("playlist") or [])
    lib.add(filter_existing(paths))
    if annotations:
        lib.annotations.update(annotations)
    if meta_cache:
        lib.meta_cache.update(meta_cache)

    try:
        shape = ArcShape(arc_shape)
    except ValueError:
        shape = ArcShape.FLAT

    studio = PlaylistStudio(library=lib, floor=None)
    result = studio.build(StudioRequest(
        seeds=seeds,
        arc_shape=shape,
        target_count=target_count,
        max_per_artist=max_per_artist,
        max_per_genre=max_per_genre,
        transition_threshold=transition_threshold,
        candidate_pool=candidate_pool,
        arc_weight=arc_weight,
        sim_weight=sim_weight,
        arc_sharpness=arc_sharpness,
    ))
    return {
        "tracks": result.tracks,
        "arc_targets": result.arc_targets,
        "arc_scores": result.arc_scores,
        "transition_scores": result.transition_scores,
        "seed_paths": result.seed_paths,
        "arc_shape": result.arc_shape,
        "n_annotated": result.n_annotated,
        "n_fallback": result.n_fallback,
        "mean_arc_score": result.mean_arc_score,
        "mean_transition": result.mean_transition,
    }


@task("warmup.corpus")
def warmup_corpus() -> dict[str, Any]:
    from psspps.retriever import get_vault_corpus

    corpus = get_vault_corpus()
    n = getattr(corpus, "n_docs", None)
    return {"warmed": "corpus", "n_docs": n}


@task("warmup.phi")
def warmup_phi() -> dict[str, Any]:
    """Phi session stays in the MCP process. Worker only confirms the plugin bus."""
    return {"warmed": "phi", "host": "mcp"}
