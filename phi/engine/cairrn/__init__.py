# -*- coding: utf-8 -*-
"""phi.engine.cairrn — standalone CAIRRN substrate for the phi application.

A self-contained, MCP-independent implementation of the three-layer CAIRRN
pipeline (Ana-Chi → neg_exp → coherence) with harmonic ring propagation,
watchdog health monitoring, forest-floor metaphor, and cold-start persistence.

Quick start
───────────
    from phi.engine.cairrn import ForestFloor

    floor = ForestFloor()
    floor.load_state()                       # restore last session (no-op on first launch)
    floor.warm_from_history(library)         # replay recent listening history

    floor.leaf_falls("/music/track.mp3", completion_rate=0.88)
    floor.root_pulse("genre")
    print(floor.breathe())

Module map
──────────
    _constants.py   canonical physics + hub geometry (single source of truth)
    bridge.py       CairnBridge — three-layer pipeline + harmonic ring
    router.py       PhiCairrnRouter — request routing + subscriber model
    watchdog.py     CairrnWorkerWatchdog — five health conditions
    types.py        Leaf, Tree — pure data structures
    floor.py        ForestFloor — the full substrate with persistence

Shard geometry (φ-specific, formula-derived)
─────────────────────────────────────────────
    shard 0  →  agent-context   χ=0.03   DEFER   background ML writes
    shard 1  →  CODE            χ=0.99   NORMAL  active playback / ranker
    shard 2  →  HOME            χ=1.54   NORMAL  library topology
    shard 3  →  MATH            χ=1.96   NORMAL  embedding / similarity
    shards 4–6  (waveguide)              HIGH    propagation waveguides
    shard 7  →  COMMANDS        χ=2.67   URGENT  enrichment / actions

Physics constants: κ=0.15  α=1.96  coherence_floor=0.50  Euler_floor≈0.567
"""

from phi.engine.cairrn.floor    import ForestFloor
from phi.engine.cairrn.bridge   import CairnBridge, HubState, PipelineResult, WelfordWindow
from phi.engine.cairrn.router   import (
    PhiCairrnRouter,
    RequestKind,
    DispatchResult,
    REQUEST_HUB,
    PAGE_HUB,
)
from phi.engine.cairrn.watchdog import CairrnWorkerWatchdog
from phi.engine.cairrn.types    import Leaf, Tree
from phi.engine.cairrn._constants import (
    HUB_PARAMS,
    KAPPA,
    ALPHA,
    N_SHARDS,
    COHERENCE_FLOOR,
    EULER_FLOOR,
    SHARD_HUB,
    shard_priority,
)

__all__ = [
    # Primary entry point
    "ForestFloor",

    # Physics engine
    "CairnBridge",
    "HubState",
    "PipelineResult",
    "WelfordWindow",

    # Router + request types
    "PhiCairrnRouter",
    "RequestKind",
    "DispatchResult",
    "REQUEST_HUB",
    "PAGE_HUB",

    # Health monitoring
    "CairrnWorkerWatchdog",

    # Value types
    "Leaf",
    "Tree",

    # Constants
    "HUB_PARAMS",
    "KAPPA",
    "ALPHA",
    "N_SHARDS",
    "COHERENCE_FLOOR",
    "EULER_FLOOR",
    "SHARD_HUB",
    "shard_priority",
]
