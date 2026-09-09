# -*- coding: utf-8 -*-
"""phi.engine.studio — singleton bus accessor for playlist building.

Single call path: always through the in-process bus scheduler.
No library serialisation, no PLUGIN_TASKS dict.

The build algorithm lives exclusively in the bus worker
(mcp_server.bus.tasks_phi.studio_build), which loads the current phi session
via restore() so callers never need to pass library state.

Usage
-----
    from phi.engine.studio import build
    from phi.engine.playlist_studio import StudioRequest, ArcShape

    result = build(StudioRequest(seeds=[path], arc_shape=ArcShape.RISING))
    print(result.tracks)

If the scheduler is not running, raises RuntimeError — recover with
``/do restart`` (bus_restart MCP tool).
"""
from __future__ import annotations

from phi.engine.playlist_studio import StudioRequest, StudioResult


def build(request: StudioRequest, *, wait_s: float = 120.0) -> StudioResult:
    """Submit a playlist-build job to the singleton bus and wait for the result.

    Parameters
    ----------
    request : StudioRequest
        Seeds, arc shape, counts, and weights for this build run.
    wait_s  : float
        Seconds to wait before raising TimeoutError (default 120 s).

    Returns
    -------
    StudioResult with ordered tracks, arc scores, and transition scores.

    Raises
    ------
    RuntimeError  — bus scheduler is not running.
    TimeoutError  — result not received within wait_s.
    RuntimeError  — worker returned an error status.
    """
    from mcp_server.bus.client import get_client, worker_alive

    client = get_client()
    if client is None or not worker_alive():
        raise RuntimeError(
            "studio.build: bus scheduler not running — call /do restart to recover"
        )

    payload: dict = {
        "seeds":                list(request.seeds),
        "arc_shape":            request.arc_shape.value,
        "target_count":         request.target_count,
        "max_per_artist":       request.max_per_artist,
        "max_per_genre":        request.max_per_genre,
        "transition_threshold": request.transition_threshold,
        "candidate_pool":       request.candidate_pool,
        "arc_weight":           request.arc_weight,
        "sim_weight":           request.sim_weight,
        "arc_sharpness":        request.arc_sharpness,
    }

    ticket = client.submit("studio.build", payload)
    rec = client.wait(ticket["job_id"], timeout=wait_s)

    if rec is None:
        raise TimeoutError(
            f"studio.build: no result after {wait_s}s "
            f"(job_id={ticket['job_id']}) — call /do bus poll {ticket['job_id']}"
        )
    if rec.get("status") == "error":
        raise RuntimeError(
            f"studio.build failed: {rec.get('error') or rec.get('result')}"
        )

    data = rec.get("result") or {}
    return StudioResult(
        tracks=list(data.get("tracks") or []),
        arc_targets=list(data.get("arc_targets") or []),
        arc_scores=list(data.get("arc_scores") or []),
        transition_scores=list(data.get("transition_scores") or []),
        seed_paths=list(data.get("seed_paths") or request.seeds),
        arc_shape=str(data.get("arc_shape") or request.arc_shape.value),
        n_annotated=int(data.get("n_annotated") or 0),
        n_fallback=int(data.get("n_fallback") or 0),
    )
