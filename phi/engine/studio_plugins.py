# -*- coding: utf-8 -*-
"""phi.engine.studio_plugins — studio plugin loader on the mmap/celery bus.

Studio is a plugin host. Heavy builds go through BusClient; if the bus is
down the playlist_build plugin falls back to in-process PlaylistStudio.
"""
from __future__ import annotations

from typing import Any

from phi.engine.arc_engine import ArcShape
from phi.engine.playlist_studio import PlaylistStudio, StudioRequest, StudioResult

PLUGIN_TASKS: dict[str, str] = {
    "playlist_build": "studio.build",
}


def run_plugin(
    name: str,
    payload: dict[str, Any],
    *,
    library: Any = None,
    floor: Any = None,
    wait_s: float = 120.0,
) -> StudioResult:
    """Run a named studio plugin. Bus first, in-process fallback."""
    task = PLUGIN_TASKS.get(name)
    if task is None:
        raise KeyError(f"unknown studio plugin: {name}")

    if name == "playlist_build" and library is not None:
        payload = dict(payload)
        payload.setdefault("playlist", list(getattr(library, "playlist", []) or []))
        payload.setdefault("annotations", dict(getattr(library, "annotations", {}) or {}))
        payload.setdefault("meta_cache", dict(getattr(library, "meta_cache", {}) or {}))

    bus_payload = payload
    try:
        from mcp_server._guard import json_safe
        bus_payload = json_safe(dict(payload))
        if not isinstance(bus_payload, dict):
            bus_payload = payload
    except Exception:
        bus_payload = payload

    try:
        from mcp_server.bus.client import BusClient, get_client, worker_alive

        client = get_client() or BusClient.connect(create=False)
        if client is None or not worker_alive():
            raise RuntimeError("bus worker not running")
        ticket = client.submit(task, bus_payload)
        rec = client.wait(ticket["job_id"], timeout=wait_s)
        if rec is not None and rec.get("status") == "done" and isinstance(rec.get("result"), dict):
            built = _result_from_dict(rec["result"], payload)
            if built.tracks or library is None:
                return built
    except Exception:
        pass

    if library is None:
        raise RuntimeError(f"studio plugin {name!r}: bus unavailable and no library")
    return _playlist_build_local(payload, library, floor)


def _playlist_build_local(payload: dict[str, Any], library: Any, floor: Any) -> StudioResult:
    try:
        shape = ArcShape(payload.get("arc_shape", "flat"))
    except ValueError:
        shape = ArcShape.FLAT
    studio = PlaylistStudio(library=library, floor=floor)
    return studio.build(StudioRequest(
        seeds=list(payload.get("seeds") or []),
        arc_shape=shape,
        target_count=int(payload.get("target_count", 20)),
        max_per_artist=int(payload.get("max_per_artist", 2)),
        max_per_genre=int(payload.get("max_per_genre", 3)),
        transition_threshold=float(payload.get("transition_threshold", 0.60)),
        candidate_pool=int(payload.get("candidate_pool", 15)),
        arc_weight=float(payload.get("arc_weight", 0.60)),
        sim_weight=float(payload.get("sim_weight", 0.40)),
        arc_sharpness=float(payload.get("arc_sharpness", 20.0)),
    ))


def _result_from_dict(data: dict[str, Any], payload: dict[str, Any]) -> StudioResult:
    return StudioResult(
        tracks=list(data.get("tracks") or []),
        arc_targets=list(data.get("arc_targets") or []),
        arc_scores=list(data.get("arc_scores") or []),
        transition_scores=list(data.get("transition_scores") or []),
        seed_paths=list(data.get("seed_paths") or payload.get("seeds") or []),
        arc_shape=str(data.get("arc_shape") or payload.get("arc_shape") or "flat"),
        n_annotated=int(data.get("n_annotated") or 0),
        n_fallback=int(data.get("n_fallback") or 0),
    )
