# -*- coding: utf-8 -*-
"""phi.engine.cairrn.types — Leaf, Tree, and RiderState value types for the ForestFloor.

Pure data structures with no I/O or network dependencies.  Separated from
floor.py so other modules can import the types without pulling in the full
CAIRRN substrate or its persistence layer.

    Leaf        — one track event (a song that fell from the canopy)
    Tree        — one UI page    (a standing tree rooted in a CAIRRN hub)
    RiderState  — the user's active position and velocity in the forest
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List

from phi.engine.cairrn._constants import PAGE_HUB, HUB_PARAMS


# ── Hub τ lookup (re-derived from HUB_PARAMS for convenience) ─────────────────

_HUB_TAU: Dict[str, float] = {name: p["tau"] for name, p in HUB_PARAMS.items()}


# ── Leaf ──────────────────────────────────────────────────────────────────────

@dataclass
class Leaf:
    """
    One track event falling onto the forest floor.

    Carries identity (path), position in the canopy (album, genre, mood —
    the nesting), and the signal from its tree (completion_rate).

    completion_rate ∈ [0, 1]:
        1.0  gentle landing — track played all the way through
        0.0  torn off early — track skipped immediately
        0.5  ambiguous — fell midway; absorbed as neutral signal
    """
    path:            str
    completion_rate: float
    album:           str   = ""
    genre:           str   = ""
    mood:            str   = ""
    timestamp:       float = field(default_factory=time.monotonic)

    @property
    def skip_pressure(self) -> float:
        """Inverse completion — how hard the wind tore this leaf off."""
        return max(0.0, 1.0 - self.completion_rate)

    @property
    def nesting_depth(self) -> int:
        """Depth in the canopy: 0=bare path, 1=+album, 2=+genre, 3=+mood."""
        return sum(1 for v in (self.album, self.genre, self.mood) if v)

    def __str__(self) -> str:
        short   = self.path[-40:] if len(self.path) > 40 else self.path
        nesting = " > ".join(v for v in (self.album, self.genre, self.mood) if v) or "(bare)"
        return (
            f"Leaf  {short}\n"
            f"  nesting:       {nesting}\n"
            f"  completion:    {self.completion_rate:.2f}"
            f"  skip_pressure: {self.skip_pressure:.2f}"
        )


# ── Tree ──────────────────────────────────────────────────────────────────────

@dataclass
class Tree:
    """
    A UI page — a standing tree whose roots reach into one CAIRRN hub.

    When the Rider (user cursor) enters this page, the tree fires a root pulse
    into the floor.  The floor propagates the signal to adjacent shards so
    other trees feel the stir through the shared mycelium (harmonic ring).

    The Rider is always located in exactly one tree — the current active page.
    Moving between trees (root_pulse) is the Rider's primary steering signal.
    The tree's mean_completion and total_skip_pressure track how the Rider
    behaved while present: relaxed listening vs restless skipping.

    Attributes
    ----------
    name   : page name ("playing", "library", "genre", "playlist", "mixer")
    hub    : CAIRRN hub this tree is rooted in
    tau    : coherence time constant of the hub (its characteristic lifetime)
    leaves : leaf events that occurred while the Rider was in this tree
    """
    name:   str
    hub:    str
    tau:    float
    leaves: List[Leaf] = field(default_factory=list)

    @classmethod
    def from_page(cls, page_name: str) -> "Tree":
        """Construct a Tree for *page_name*, resolving hub and τ automatically."""
        hub = PAGE_HUB.get(page_name, "HOME")
        return cls(name=page_name, hub=hub, tau=_HUB_TAU.get(hub, 30.0))

    def catch(self, leaf: Leaf) -> None:
        """Catch a falling leaf in this tree's canopy."""
        self.leaves.append(leaf)

    @property
    def leaf_count(self) -> int:
        return len(self.leaves)

    @property
    def mean_completion(self) -> float:
        if not self.leaves:
            return 0.5
        return sum(lf.completion_rate for lf in self.leaves) / len(self.leaves)

    @property
    def total_skip_pressure(self) -> float:
        """Accumulated skip pressure across all leaves in this tree."""
        return sum(lf.skip_pressure for lf in self.leaves)

    def __str__(self) -> str:
        return (
            f"Tree '{self.name}'  hub={self.hub}  τ={self.tau}"
            f"  leaves={self.leaf_count}  mean_completion={self.mean_completion:.2f}"
        )


# ── RiderState ────────────────────────────────────────────────────────────────

_VELOCITY_ALPHA: float = 0.6    # EMA memory factor for skip-pressure velocity
_ACTIVE_WINDOW:  float = 30.0   # seconds — Rider is "active" within this window


@dataclass
class RiderState:
    """
    The Rider's current position and velocity in the forest.

    The Rider is the user's active intent — every button press and cursor
    movement updates this state.  Background signals (heartbeat, CLAP, enrichment)
    never touch it.

    Attributes
    ----------
    location        : current tree / page name ("playing", "library", etc.)
    velocity        : EMA of recent skip pressure [0, 1] — 0=at rest, 1=frantic
    impulse_count   : total direct Rider steering impulses this session
    last_impulse_ts : monotonic timestamp of last Rider signal
    last_action     : short label of the last Rider action ("root_pulse:genre", "skip", …)
    """
    location:        str   = "playing"
    velocity:        float = 0.0
    impulse_count:   int   = 0
    last_impulse_ts: float = field(default_factory=time.monotonic)
    last_action:     str   = ""

    def record(self, location: str, pressure: float, action: str) -> None:
        """
        Record a Rider impulse: update location, apply EMA to velocity.

        Args
        ----
        location : tree/page where the impulse occurred
        pressure : skip/action pressure for this impulse [0, 1]
        action   : short label ("root_pulse:library", "skip", "rider:play", …)
        """
        self.location        = location
        self.velocity        = _VELOCITY_ALPHA * self.velocity + (1.0 - _VELOCITY_ALPHA) * pressure
        self.impulse_count  += 1
        self.last_impulse_ts = time.monotonic()
        self.last_action     = action

    def decay(self, factor: float = 0.85) -> None:
        """Gently decay velocity toward rest — call on heartbeat ticks."""
        self.velocity = max(0.0, self.velocity * factor)

    @property
    def is_active(self) -> bool:
        """True if the Rider sent an impulse within the last 30 seconds."""
        return (time.monotonic() - self.last_impulse_ts) < _ACTIVE_WINDOW

    @property
    def restless(self) -> bool:
        """True when skip pressure EMA is high — Rider pushing away from context."""
        return self.velocity >= 0.60

    def __str__(self) -> str:
        active = "active" if self.is_active else "idle"
        motion = "restless" if self.restless else "at_rest"
        return (
            f"Rider  loc='{self.location}'  vel={self.velocity:.3f}"
            f"  [{motion}]  impulses={self.impulse_count}  {active}"
            f"  last='{self.last_action}'"
        )
