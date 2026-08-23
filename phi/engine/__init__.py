# -*- coding: utf-8 -*-
"""phi.engine — CAIRRN-backed computation substrate for PHI.

    Pages  are trees.
    Songs  (and their nesting — track → album → genre → mood) are leaves.
    CAIRRN is the forest floor.

Heavy modules (CurveDaemon, ZoneClusterer, playlist studio, hub ring) are
imported lazily so pytest collection of cairrn tests cannot abort the
interpreter via sklearn / PySide6.
"""
from __future__ import annotations

import importlib
from typing import Any

from phi.engine.cairrn import (
    ForestFloor,
    CairnBridge,
    PhiCairrnRouter,
    RequestKind,
    DispatchResult,
    CairrnWorkerWatchdog,
    Leaf,
    Tree,
    PAGE_HUB,
    HUB_PARAMS,
    KAPPA,
    ALPHA,
    COHERENCE_FLOOR,
    EULER_FLOOR,
)
from phi.engine.cairrn.router import REQUEST_HUB as REQUEST_HUB_MAP

_LAZY: dict[str, tuple[str, str]] = {
    "PhiSimilarityIndex": ("phi.engine.similarity_index", "PhiSimilarityIndex"),
    "CurveDaemon": ("phi.engine.curve_daemon", "CurveDaemon"),
    "ZoneClusterer": ("phi.engine.zone_clusterer", "ZoneClusterer"),
    "CurveWalker": ("phi.engine.curve_walker", "CurveWalker"),
    "ArcEngine": ("phi.engine.arc_engine", "ArcEngine"),
    "ArcShape": ("phi.engine.arc_engine", "ArcShape"),
    "PlaylistStudio": ("phi.engine.playlist_studio", "PlaylistStudio"),
    "StudioRequest": ("phi.engine.playlist_studio", "StudioRequest"),
    "StudioResult": ("phi.engine.playlist_studio", "StudioResult"),
    "PhiHubRing": ("phi.engine.hub_ring", "PhiHubRing"),
    "PHI_MUSIC_HUBS": ("phi.engine.hub_ring", "PHI_MUSIC_HUBS"),
    "SHARD_HUB": ("phi.engine.hub_ring", "SHARD_HUB"),
    "PHI_SPOKE_PATHS": ("phi.engine.hub_ring", "PHI_SPOKE_PATHS"),
    "PHI_SPOKE_QUERIES": ("phi.engine.hub_ring", "PHI_SPOKE_QUERIES"),
    "HubInjectionRecord": ("phi.engine.hub_ring", "HubInjectionRecord"),
}


def __getattr__(name: str) -> Any:
    spec = _LAZY.get(name)
    if spec is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    mod_name, attr = spec
    value = getattr(importlib.import_module(mod_name), attr)
    globals()[name] = value
    return value


__all__ = [
    "ForestFloor",
    "CairnBridge",
    "PhiCairrnRouter",
    "RequestKind",
    "DispatchResult",
    "CairrnWorkerWatchdog",
    "Leaf",
    "Tree",
    "PAGE_HUB",
    "HUB_PARAMS",
    "KAPPA",
    "ALPHA",
    "COHERENCE_FLOOR",
    "EULER_FLOOR",
    "REQUEST_HUB_MAP",
    "PhiSimilarityIndex",
    "CurveDaemon",
    "ZoneClusterer",
    "CurveWalker",
    "ArcEngine",
    "ArcShape",
    "PlaylistStudio",
    "StudioRequest",
    "StudioResult",
    "PhiHubRing",
    "PHI_MUSIC_HUBS",
    "SHARD_HUB",
    "PHI_SPOKE_PATHS",
    "PHI_SPOKE_QUERIES",
    "HubInjectionRecord",
]
