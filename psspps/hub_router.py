# -*- coding: utf-8 -*-
"""
psspps.hub_router — PSSPPS result → CAIRRN hub → Notion shard routing.

This module closes the feedback loop between PSSPPS retrieval and the
harmonic sharding process.  It is the return path of the pipeline:

    harmonic activations
          │
          ▼ (α modulation)
       PSSPPS retrieval
          │
          ▼ (hub_router — this module)
     hub_distribution          →  harmonic injection (side_effects.pulse_hubs)
     notion_tick_shards         →  Notion Reservoir tick (singleton bus)

Design
------
Every retrieved doc has an 8-dim basin affinity vector (computed in
psspps.scorer.harmonic_affinity).  The peak affinity shard determines the
doc's "home hub" via the reverse of sims.harmonic.HUB_SHARD_MAP.

Docs are aggregated into a hub distribution (vote count per hub) which the
harmonic ring uses for targeted injection.  The hub distribution is also
translated to Notion Reservoir shard names for the stateful identity tick.

No MCP, no bus — pure routing math.  Import freely from both worker and
MCP-process contexts.
"""
from __future__ import annotations

import numpy as np

# ---------------------------------------------------------------------------
# Static maps — kept in sync with sims.harmonic.HUB_SHARD_MAP
# ---------------------------------------------------------------------------

# Reverse of HUB_SHARD_MAP: shard index → CAIRRN hub name
SHARD_TO_HUB: dict[int, str] = {
    0: "HOME",
    1: "MATH",
    2: "MATH",
    3: "CODE",
    4: "CODE",
    5: "COMMANDS",
    6: "agent-context",
    7: "agent-context",
}

# CAIRRN hub → Notion Reservoir shard name
# Mirrors notion_reservoir.CAIRRN_HUB_TO_SHARD so both sides stay consistent.
HUB_TO_NOTION_SHARD: dict[str, str] = {
    "HOME":          "dawn-fragments",
    "MATH":          "recursive-thought",
    "CODE":          "novel-fragments",
    "COMMANDS":      "valence-high",
    "agent-context": "schema-fragments",
}

_ALL_HUBS: frozenset[str] = frozenset(HUB_TO_NOTION_SHARD)


# ---------------------------------------------------------------------------
# Core routing functions
# ---------------------------------------------------------------------------

def shard_to_hub(shard_idx: int) -> str:
    """Return the CAIRRN hub name for a harmonic shard index (0–7)."""
    return SHARD_TO_HUB.get(shard_idx % 8, "HOME")


def affinity_to_hub(affinity_vec: np.ndarray) -> str:
    """
    Return the CAIRRN hub most aligned with a doc's basin affinity vector.

    Selects the hub whose shards collectively hold the most affinity mass.
    Falls back to 'HOME' on empty or zero vectors.
    """
    aff = np.asarray(affinity_vec, dtype=float)
    if aff.size == 0 or float(aff.sum()) < 1e-12:
        return "HOME"
    # Aggregate affinity mass per hub
    hub_mass: dict[str, float] = {}
    for shard_idx, hub in SHARD_TO_HUB.items():
        if shard_idx < len(aff):
            hub_mass[hub] = hub_mass.get(hub, 0.0) + float(aff[shard_idx])
    return max(hub_mass, key=lambda h: hub_mass[h])


def activations_to_hub(activations: np.ndarray) -> str:
    """
    Return the CAIRRN hub with the highest combined shard activation.

    Used to route a retrieval query to a hub when individual doc affinities
    are not available (e.g. session-open grounding from raw ring state).
    """
    acts = np.asarray(activations, dtype=float)
    if acts.size == 0 or float(np.abs(acts).sum()) < 1e-12:
        return "HOME"
    hub_mass: dict[str, float] = {}
    for shard_idx, hub in SHARD_TO_HUB.items():
        if shard_idx < len(acts):
            hub_mass[hub] = hub_mass.get(hub, 0.0) + float(abs(acts[shard_idx]))
    return max(hub_mass, key=lambda h: hub_mass[h])


def hub_to_notion_shard(hub_name: str) -> str | None:
    """Map a CAIRRN hub name to its Notion Reservoir shard name, or None."""
    return HUB_TO_NOTION_SHARD.get(hub_name)


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------

def docs_to_hub_distribution(
    doc_affinities: list[np.ndarray],
) -> dict[str, int]:
    """
    Count hub votes across a list of doc affinity vectors.

    Each doc votes for one hub (its peak-mass hub).  Returns a dict of
    ``{hub_name: vote_count}`` for hubs with at least one vote, sorted by
    vote count descending.
    """
    counts: dict[str, int] = {}
    for aff in doc_affinities:
        hub = affinity_to_hub(np.asarray(aff, dtype=float))
        counts[hub] = counts.get(hub, 0) + 1
    # Return sorted by count descending so callers can take the top N
    return dict(sorted(counts.items(), key=lambda kv: -kv[1]))


def docs_to_notion_shards(
    doc_affinities: list[np.ndarray],
    *,
    max_shards: int = 3,
) -> list[str]:
    """
    Map a list of doc affinities to unique Notion Reservoir shard names.

    Returns up to ``max_shards`` shard names for the top hubs, by vote count.
    """
    distribution = docs_to_hub_distribution(doc_affinities)
    shards: list[str] = []
    seen: set[str] = set()
    for hub in distribution:
        if len(shards) >= max_shards:
            break
        shard = hub_to_notion_shard(hub)
        if shard and shard not in seen:
            shards.append(shard)
            seen.add(shard)
    return shards


def activations_to_notion_shards(
    activations: np.ndarray,
    *,
    top_n: int = 2,
) -> list[str]:
    """
    Map raw harmonic activations to Notion Reservoir shard names.

    Used when doc affinities are not available — routes via the peak
    activation hub(s) instead.  Returns up to ``top_n`` shard names.
    """
    acts = np.asarray(activations, dtype=float)
    if acts.size == 0 or float(np.abs(acts).sum()) < 1e-12:
        return [HUB_TO_NOTION_SHARD["HOME"]]

    # Aggregate per hub, take top_n
    hub_mass: dict[str, float] = {}
    for shard_idx, hub in SHARD_TO_HUB.items():
        if shard_idx < len(acts):
            hub_mass[hub] = hub_mass.get(hub, 0.0) + float(abs(acts[shard_idx]))

    top_hubs = sorted(hub_mass, key=lambda h: -hub_mass[h])[:top_n]
    shards: list[str] = []
    seen: set[str] = set()
    for hub in top_hubs:
        shard = hub_to_notion_shard(hub)
        if shard and shard not in seen:
            shards.append(shard)
            seen.add(shard)
    return shards
