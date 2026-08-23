"""
Hub classifier — maps session content to a station hub for harmonic injection.

Two independent signals are combined:

  1. Keyword signal — weighted keyword hits across the concatenated session
     text (prompt + thinking + outcome).  Each hub has its own vocabulary.
     Raw hit count is normalised by vocabulary size so large sets don't
     dominate by surface area alone.

  2. Link signal — if a discovered_link stem is a known member of a hub's
     node set, that hub receives a flat bonus per matching link.  This lets
     the PSSPPS-discovered graph topology vote on hub assignment.

The hub with the highest combined score wins.  CODE is the tiebreaker.

Station-hub → shard mapping (fixed at spawn, mirrors server.py):
    HOME          → shard 0          (basin 1.96)
    MATH          → shards 1, 2      (basins 3.92, 5.88)
    CODE          → shards 3, 4      (basins 7.84, 9.80)
    COMMANDS      → shard 5          (basin 11.76)
    agent-context → shards 6, 7      (basins 13.72, 15.68)

Station-hub → Ana-Chi basin mapping (𝒜_χ integration):
    HOME          → true_center  χ = 1.5414   (natural equilibrium)
    MATH          → white_peak   χ = 1.9600   (singularity = ALPHA)
    CODE          → mirror       χ = 0.9900   (stable, slow transitions)
    COMMANDS      → escape       χ = 2.6700   (rapid action)
    agent-context → boundary     χ = 0.0300   (interface layer)
"""
from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Hub vocabulary — keyword → weight
# Higher weight = stronger signal per hit
# ---------------------------------------------------------------------------

_MATH_VOCAB: dict[str, float] = {
    "attractor": 2.0,
    "harmonic": 2.0,
    "shard": 2.0,
    "basin": 1.5,
    "coupling": 1.5,
    "kappa": 1.5,
    "alpha": 1.0,
    "formula": 1.5,
    "lambert": 2.0,
    "wave": 1.0,
    "oscillat": 1.0,
    "eigenvalue": 2.0,
    "gradient": 1.5,
    "potential": 1.5,
    "equilibrium": 1.5,
    "frequency": 1.0,
    "resonance": 1.5,
    "propagat": 1.5,
    "planck": 1.5,
    "mycelial": 1.5,
    "metabol": 1.5,
    "entropy": 1.5,
    "cognitive gravity": 2.0,
    "double.well": 2.0,
    "neg.exp": 1.5,
    "fixed.point": 1.5,
    "sim": 1.0,
    "sweep": 1.0,
    # Ana-Chi terms
    "ana.chi": 3.0,
    "1.5414": 3.0,
    "chameleon.constant": 2.5,
    "rattling.pocket": 2.0,
    "cosine.drape": 2.0,
    "white.peak": 2.0,
    "true.center": 2.0,
    "ssddcs": 2.5,
    "biphasic": 2.0,
}

_CODE_VOCAB: dict[str, float] = {
    "graph": 1.5,
    "logger": 2.0,
    "linker": 2.0,
    "worker": 1.5,
    "mcp": 2.0,
    "psspps": 2.0,
    "retriever": 1.5,
    "scorer": 1.5,
    "router": 1.5,
    "traverser": 1.5,
    "embedder": 1.5,
    "session": 1.0,
    "vault": 1.0,
    "node": 1.0,
    "pipeline": 1.5,
    "test": 1.0,
    "pytest": 2.0,
    "import": 1.0,
    "function": 1.0,
    "class": 1.0,
    "module": 1.0,
    "server": 1.5,
    "hook": 1.5,
    "dom.queue": 2.0,
    "inject": 1.0,
    "ingestion": 2.0,
    "commit": 1.0,
}

_COMMANDS_VOCAB: dict[str, float] = {
    "/sim": 2.0,
    "/sweep": 2.0,
    "/index": 2.0,
    "/inject": 2.0,
    "/propagate": 2.0,
    "/reset": 2.0,
    "/hub": 2.0,
    "/psspps": 2.0,
    "/find": 2.0,
    "/graph": 2.0,
    "/status": 2.0,
    "/health": 2.0,
    "/test": 2.0,
    "slash command": 2.0,
    "command": 1.0,
    "mcp tool": 2.0,
}

_AGENT_CONTEXT_VOCAB: dict[str, float] = {
    "/talk": 2.0,
    "/explain": 2.0,
    "/dev": 2.0,
    "/wire": 2.0,
    "/modular": 2.0,
    "/edit": 2.0,
    "/clean": 2.0,
    "workflow": 1.5,
    "mode": 1.0,
    "behaviour contract": 2.0,
    "agent.context": 2.0,
    "context file": 2.0,
    "context mode": 2.0,
}

# Vocabulary for each hub — order determines tiebreaker priority
_HUB_VOCABS: dict[str, dict[str, float]] = {
    "MATH": _MATH_VOCAB,
    "CODE": _CODE_VOCAB,
    "COMMANDS": _COMMANDS_VOCAB,
    "agent-context": _AGENT_CONTEXT_VOCAB,
    # HOME has no vocabulary — it is the fallback only
}

# ---------------------------------------------------------------------------
# Link signal — known node stems per hub
# ---------------------------------------------------------------------------

_HUB_NODE_MEMBERS: dict[str, set[str]] = {
    "HOME": {"HOME", "live-state", "sessions", "git-log", "README", "keep"},
    "MATH": {
        "MATH", "FORMULAS", "harmonic-index", "attractors", "lambert-w",
        "sims", "dawn-physics-scaffold", "mycelial-layer",
        "temporal-index", "ana-chi",
        # source/ nodes for MATH packages
        "source/sims-harmonic", "sims-harmonic",
        "source/sims-attractors", "sims-attractors",
        "source/sims-temporal", "sims-temporal",
    },
    "CODE": {
        "CODE", "graph", "mcp-server", "psspps", "workers", "sims",
        "graph-index", "graph-logger", "graph-linker", "graph-worker", "graph-node",
        "hub-classifier", "logger", "worker", "topo-hub",
        # source/ nodes — any stem starting with these prefixes resolves here
        # via the prefix_match path in classify_stem(); explicit stems for fast lookup:
        "source/graph-worker", "graph-worker",
        "source/graph-node", "graph-node",
        "source/graph-ingestion", "graph-ingestion",
        "source/mcp-server-server", "mcp-server-server",
        "source/mcp-server-tools-graph", "mcp-server-tools-graph",
        "source/mcp-server-tools-harmonic", "mcp-server-tools-harmonic",
        "source/mcp-server-tools-search", "mcp-server-tools-search",
        "source/mcp-server-tools-system", "mcp-server-tools-system",
        "source/mcp-server-tools-cairrn", "mcp-server-tools-cairrn",
        "source/psspps-pipeline", "psspps-pipeline",
        "source/psspps-scorer", "psspps-scorer",
        "source/psspps-retriever", "psspps-retriever",
        "source/engine-bridge-factory", "engine-bridge-factory",
        "source/engine-cairrn-bridge", "engine-cairrn-bridge",
        # phi topology nodes
        "source/phi-topology-topo-graph", "phi-topology-topo-graph",
        "source/phi-topology-primitives", "phi-topology-primitives",
        "source/phi-topology-init", "phi-topology-init",
        "source/graph-topo-graph", "graph-topo-graph",
        # phi engine / hub nodes
        "source/phi-engine-hub-ring", "phi-engine-hub-ring",
        "source/phi-engine-vault-context", "phi-engine-vault-context",
        "source/phi-engine-cairrn-bridge", "phi-engine-cairrn-bridge",
    },
    "COMMANDS": {"COMMANDS", "source/mcp-server-commands", "mcp-server-commands"},
    "agent-context": {"agent-context"},
}

# Bonus per matching link stem
_LINK_BONUS: float = 1.5

# ---------------------------------------------------------------------------
# Tiebreaker order — first hub in this list wins on a draw
# ---------------------------------------------------------------------------

_TIEBREAKER: list[str] = ["CODE", "MATH", "COMMANDS", "agent-context", "HOME"]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def classify_hub(
    prompt: str,
    thinking: str,
    outcome: str,
    discovered_links: list[str] | None = None,
) -> str:
    """
    Return the station hub that best matches this session's content.

    Parameters
    ----------
    prompt           : user's original message
    thinking         : agent's reasoning summary
    outcome          : what was built/decided/answered
    discovered_links : stems of vault nodes discovered by PSSPPS (may be empty)

    Returns
    -------
    One of: "HOME", "MATH", "CODE", "COMMANDS", "agent-context"
    """
    text = " ".join([prompt, thinking, outcome]).lower()
    links = [lnk.lower() for lnk in (discovered_links or [])]

    scores: dict[str, float] = {hub: 0.0 for hub in list(_HUB_VOCABS) + ["HOME"]}

    # Signal 1 — keyword hits
    for hub, vocab in _HUB_VOCABS.items():
        total_weight = sum(vocab.values())
        raw = 0.0
        for keyword, weight in vocab.items():
            pattern = keyword.replace(".", r"[\s\-_]?")
            if re.search(pattern, text):
                raw += weight
        # Normalise by total vocabulary weight so large vocab sets don't win cheaply
        scores[hub] += raw / total_weight if total_weight > 0 else 0.0

    # Signal 2 — link topology bonus
    for hub, members in _HUB_NODE_MEMBERS.items():
        for link in links:
            if link in {m.lower() for m in members}:
                scores[hub] += _LINK_BONUS

    # Pick winner — resolve ties with tiebreaker order
    best_score = max(scores.values())

    if best_score <= 0.0:
        return "HOME"

    for hub in _TIEBREAKER:
        if scores.get(hub, 0.0) == best_score:
            return hub

    # Fallback: pick any hub with best score
    return max(scores, key=lambda h: scores[h])


# Direct stem → station map for elected WCC hubs (topology fusion).
# TOPOLOGY lives on COMMANDS (shard 5 / basin 11.76) on the MCP ring.
_STEM_STATION: dict[str, str] = {
    "index": "HOME",
    "HOME": "HOME",
    "sessions": "HOME",
    "live-state": "HOME",
    "MATH": "MATH",
    "CODE": "CODE",
    "COMMANDS": "COMMANDS",
    "agent-context": "agent-context",
    "TOPOLOGY": "COMMANDS",
}


# Package-prefix → hub map for source/* stems that share a package root.
# A source node "source/phi-engine-*" inherits from phi → CODE, etc.
_SOURCE_PREFIX_HUB: dict[str, str] = {
    "phi-":    "CODE",
    "graph-":  "CODE",
    "engine-": "CODE",
    "psspps-": "CODE",
    "mcp-":    "CODE",
    "worker":  "CODE",
    "sims-":   "MATH",
    "models-": "MATH",
    "config-": "COMMANDS",
}


def classify_stem(stem: str, spokes: list[str] | None = None) -> str:
    """
    Map an elected vault stem onto a station hub.

    Resolution order:
      1. _STEM_STATION fast-path (exact alias)
      2. _HUB_NODE_MEMBERS exact membership
      3. source/ prefix matching via _SOURCE_PREFIX_HUB
      4. classify_hub() on the stem + spoke sample
    """
    if stem in _STEM_STATION:
        return _STEM_STATION[stem]
    for hub, members in _HUB_NODE_MEMBERS.items():
        if stem in members:
            return hub
    # prefix routing for dense source/ namespace
    bare = stem.removeprefix("source/")
    for prefix, hub in _SOURCE_PREFIX_HUB.items():
        if bare.startswith(prefix):
            return hub
    sample = list(spokes or [])[:8]
    return classify_hub(stem, "", " ".join(sample), discovered_links=[stem, *sample])


def hub_scores(
    prompt: str,
    thinking: str,
    outcome: str,
    discovered_links: list[str] | None = None,
) -> dict[str, float]:
    """
    Return the raw score for every hub — useful for debugging and tests.

    Parameters mirror classify_hub().
    """
    text = " ".join([prompt, thinking, outcome]).lower()
    links = [lnk.lower() for lnk in (discovered_links or [])]

    scores: dict[str, float] = {hub: 0.0 for hub in list(_HUB_VOCABS) + ["HOME"]}

    for hub, vocab in _HUB_VOCABS.items():
        total_weight = sum(vocab.values())
        raw = 0.0
        for keyword, weight in vocab.items():
            pattern = keyword.replace(".", r"[\s\-_]?")
            if re.search(pattern, text):
                raw += weight
        scores[hub] += raw / total_weight if total_weight > 0 else 0.0

    for hub, members in _HUB_NODE_MEMBERS.items():
        for link in links:
            if link in {m.lower() for m in members}:
                scores[hub] += _LINK_BONUS

    return scores


# ---------------------------------------------------------------------------
# Ana-Chi integration
# ---------------------------------------------------------------------------

# Hub → Ana-Chi basin χ value (see sims/ana_chi.py for full basin definitions)
HUB_ANA_CHI: dict[str, float] = {
    "HOME":          1.5414,  # true_center — natural equilibrium
    "MATH":          1.9600,  # white_peak  — singularity (= ALPHA)
    "CODE":          0.9900,  # mirror      — stable, slow transitions
    "COMMANDS":      2.6700,  # escape      — rapid action
    "agent-context": 0.0300,  # boundary    — interface layer
}


def hub_ana_chi_weight(hub_name: str) -> float:
    """
    Return the Ana-Chi coherence weight for a hub.

    Coherence = exp(-|χ_hub - 𝒜_χ| / 0.40)

    1.0  → hub sits exactly at true_center (HOME)
    0.0  → hub is maximally distant from 𝒜_χ

    This is used to bias harmonic injection: sessions at hubs closer to
    𝒜_χ receive higher coherence weighting.
    """
    import math
    chi = HUB_ANA_CHI.get(hub_name, 1.5414)
    return math.exp(-abs(chi - 1.5414) / 0.40)


def classify_hub_full(
    prompt: str,
    thinking: str,
    outcome: str,
    discovered_links: list[str] | None = None,
) -> dict:
    """
    Full classification result including Ana-Chi basin assignment.

    Returns
    -------
    {
        "hub":          str   — winning hub name
        "scores":       dict  — raw score per hub
        "ana_chi":      float — basin χ for winning hub
        "basin_name":   str   — Ana-Chi basin name for winning hub
        "coherence":    float — proximity to 𝒜_χ (0–1)
    }
    """
    hub = classify_hub(prompt, thinking, outcome, discovered_links)
    scores = hub_scores(prompt, thinking, outcome, discovered_links)
    chi = HUB_ANA_CHI.get(hub, 1.5414)

    # Basin name lookup (mirrors sims/ana_chi.HUB_BASIN)
    _basin_names: dict[float, str] = {
        1.5414: "true_center",
        1.9600: "white_peak",
        0.9900: "mirror",
        2.6700: "escape",
        0.0300: "boundary",
    }

    return {
        "hub":        hub,
        "scores":     scores,
        "ana_chi":    chi,
        "basin_name": _basin_names.get(chi, "unknown"),
        "coherence":  hub_ana_chi_weight(hub),
    }
