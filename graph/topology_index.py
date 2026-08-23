"""
Vault topology → MCP harmonic-index fusion.

Two rings share basin centres but not labels. This module feeds the MCP
station ring only (HOME/MATH/CODE/COMMANDS/agent-context). It does not
touch PhiHubRing (PLAYBACK…MEMORY). Shard 5 is COMMANDS here and TOPOLOGY
on the music ring — same basin (11.76), different names.

Fusion sequence (matches music/TOPOLOGY.md + graph_sync_manifest pulse):
    1. χ, β₀, β₁, T_B from the wikilink DiGraph
    2. κ_eff = min(κ_base × (1 + β₁ / V), 0.45)
    3. inject min(1, |χ| / (V+1)) into shard 5 (COMMANDS)
    4. elected WCC hubs → hub_classifier → inject_from_hub
    5. 2 local propagate steps

CAIRRNBridge.ingest_topology remains a third overlay (arm/hash routing).
Do not call it from apply_fusion — keep the seams separate.
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

import networkx as nx

from graph.hub_classifier import classify_stem
from graph.topo_graph import TopoHubReport
from sims.harmonic import HUB_SHARD_MAP, HarmonicIndex

# MCP station shard that coincides with Phi TOPOLOGY (basin 11.76).
TOPOLOGY_SHARD = 5
TOPOLOGY_HUB = "COMMANDS"

BASE_KAPPA = 0.15
KAPPA_MAX = 0.45
HUB_PULSE_SCALE = 0.10
HUB_PULSE_CAP = 2.0
PROPAGATE_STEPS = 2

# Triangle enumeration caps — same as phi.topology.TopologicalGraph.
_MAX_DEGREE = 50
_MAX_TRIANGLES = 50_000


@dataclass(frozen=True)
class VaultInvariant:
    """χ / Betti snapshot of a vault wikilink graph (MCP copy of Phi's invariant)."""

    V: int
    E: int
    T: int
    chi: float
    beta_0: int
    beta_1: int
    t_b: float
    t_b_norm: float

    def as_dict(self) -> dict[str, float]:
        return {
            "V": float(self.V),
            "E": float(self.E),
            "T": float(self.T),
            "chi": float(self.chi),
            "beta_0": float(self.beta_0),
            "beta_1": float(self.beta_1),
            "t_b": float(self.t_b),
            "t_b_norm": float(self.t_b_norm),
        }


def count_triangles(
    G: nx.DiGraph,
    max_degree: int = _MAX_DEGREE,
    max_triangles: int = _MAX_TRIANGLES,
) -> int:
    """
    Bounded undirected triangle count. High-degree hubs are skipped so dense
    auto-linked vaults do not blow up; χ is then a lower bound.
    """
    if G.number_of_nodes() == 0:
        return 0
    G_ud = G.to_undirected()
    seen: set[tuple[str, str, str]] = set()
    for node in G_ud.nodes():
        if len(seen) >= max_triangles:
            break
        nbrs = set(G_ud.neighbors(node))
        if len(nbrs) > max_degree:
            continue
        for nbr in nbrs:
            if len(seen) >= max_triangles:
                break
            nbr_nbrs = set(G_ud.neighbors(nbr))
            if len(nbr_nbrs) > max_degree:
                continue
            for third in nbrs & nbr_nbrs:
                key = tuple(sorted((str(node), str(nbr), str(third))))
                if len(key) == 3:
                    seen.add(key)  # type: ignore[arg-type]
                    if len(seen) >= max_triangles:
                        break
    return len(seen)


def _basin_sequestration(V: int, E: int, T: int, chi: float, beta_0: int, beta_1: int) -> float:
    """T_B — same formula as phi.topology.primitives.TopologicalInvariant."""
    Vn = max(V, 1)
    Tn = max(T, 1)
    b0 = max(beta_0, 1)
    D = Vn / b0
    D_M = E / Vn
    A_xG = float(Vn) * D * math.sqrt(max(D_M, 0.0))
    BSH = float(beta_1) - D
    BHD = float(chi) * b0 - D
    return A_xG * abs(BSH) / Tn - abs(BHD - 1.0)


def compute_invariant(G: nx.DiGraph) -> VaultInvariant:
    """Euler-Poincaré snapshot of a wikilink DiGraph."""
    V = G.number_of_nodes()
    E = G.number_of_edges()
    T = count_triangles(G)
    beta_0 = nx.number_weakly_connected_components(G) if V else 0
    chi = float(V - E + T)
    beta_1 = max(0, beta_0 - int(chi))
    t_b = _basin_sequestration(V, E, T, chi, beta_0, beta_1)
    t_b_norm = math.tanh(t_b / max(V ** 2, 1))
    return VaultInvariant(
        V=V, E=E, T=T, chi=chi, beta_0=beta_0, beta_1=beta_1,
        t_b=t_b, t_b_norm=t_b_norm,
    )


def topology_signal(inv: VaultInvariant) -> float:
    """χ-driven COMMANDS/TOPOLOGY activation, clamped to [0, 1]."""
    return min(1.0, abs(inv.chi) / (inv.V + 1))


def effective_kappa(inv: VaultInvariant, base: float = BASE_KAPPA, cap: float = KAPPA_MAX) -> float:
    """β₁-broadened coupling. Sparse vault → local; cyclic vault → broader."""
    V = max(inv.V, 1)
    return min(base * (1.0 + inv.beta_1 / V), cap)


def t_b_to_alpha(t_b_norm: float) -> float:
    """
    Basin sequestration → PSSPPS perspective_alpha.

    t_b_norm > 0 → deep basin → local retrieval (alpha → 1)
    t_b_norm < 0 → open basin → global retrieval (alpha → 0)
    """
    return float(0.5 + 0.5 * max(-1.0, min(1.0, t_b_norm)))


def hub_injections(report: TopoHubReport) -> dict[str, float]:
    """
    Map elected WCC hubs onto station hubs and pulse like graph_sync_manifest.

    value = min(in_degree × 0.10, 2.0), summed per station then recapped.
    """
    raw: dict[str, float] = defaultdict(float)
    for rec in report.components:
        station = classify_stem(rec.hub, rec.spokes)
        if station not in HUB_SHARD_MAP:
            continue
        raw[station] += min(rec.hub_in_degree * HUB_PULSE_SCALE, HUB_PULSE_CAP)
    return {hub: min(value, HUB_PULSE_CAP) for hub, value in raw.items() if value > 0.0}


def cairrn_snapshot(report: TopoHubReport, injections: dict[str, float]) -> dict[str, Any]:
    """
    graph_snapshot payload for CAIRRNBridge.ingest_topology — not auto-applied.

    Keys are elected stems; values are station routing so a later overlay
    can hash-route without inventing a ninth shard.
    """
    snapshot: dict[str, Any] = {}
    for rec in report.components:
        station = classify_stem(rec.hub, rec.spokes)
        snapshot[rec.hub] = {
            "station": station,
            "in_degree": rec.hub_in_degree,
            "component_size": rec.size,
            "injected": injections.get(station, 0.0),
        }
    return snapshot


def fusion_from_report(report: TopoHubReport, G: nx.DiGraph) -> dict[str, Any]:
    """Serialisable fusion payload for the MCP side-effect channel."""
    inv = compute_invariant(G)
    signal = topology_signal(inv)
    kappa = effective_kappa(inv)
    injections = hub_injections(report)
    return {
        "apply": report.n_nodes > 0,
        "invariant": inv.as_dict(),
        "topology_signal": round(signal, 6),
        "topology_shard": TOPOLOGY_SHARD,
        "topology_hub": TOPOLOGY_HUB,
        "kappa_eff": round(kappa, 6),
        "t_b_norm": round(inv.t_b_norm, 6),
        "t_b_alpha": round(t_b_to_alpha(inv.t_b_norm), 6),
        "hub_injections": {h: round(v, 6) for h, v in injections.items()},
        "cairrn_snapshot": cairrn_snapshot(report, injections),
        "propagate_steps": PROPAGATE_STEPS,
    }


def incremental_fusion(
    index: HarmonicIndex,
    *,
    propagate: bool = True,
) -> dict[str, Any]:
    """
    Lightweight topology refresh triggered after vault-write operations
    (graph_commit, graph_link).

    Loads the current vault wikilink graph, computes invariants, and injects
    the delta between the new β₀ / κ and the values already stored on the
    index — so repeated triggers on a quiet vault are near-no-ops.

    Returns a summary dict; callers may ignore the return value.
    """
    from graph.node import load_vault
    from graph.topo_graph import build as topo_build
    from graph.worker import run_topo_hubs

    nodes = load_vault()
    if not nodes:
        return {"skipped": True, "reason": "empty_vault"}

    G = topo_build(nodes)
    inv = compute_invariant(G)
    new_kappa = effective_kappa(inv)
    new_signal = topology_signal(inv)

    # Bail early when nothing material has changed
    prev_chi = index.last_chi
    prev_t_b = index.last_t_b_norm
    chi_delta = abs(inv.chi - (prev_chi or inv.chi))
    t_b_delta = abs(inv.t_b_norm - (prev_t_b or inv.t_b_norm))
    if prev_chi is not None and chi_delta < 1.0 and t_b_delta < 0.05:
        return {
            "skipped": True,
            "reason": "delta_below_threshold",
            "chi_delta": round(chi_delta, 4),
            "t_b_delta": round(t_b_delta, 4),
        }

    report = run_topo_hubs(vault=nodes, min_component_size=2, write_tags=False, prefix_filter="")
    injections = hub_injections(report)

    index.set_coupling(new_kappa)
    index.last_chi = inv.chi
    index.last_t_b_norm = inv.t_b_norm

    if new_signal > 0.0:
        index.inject(TOPOLOGY_SHARD, new_signal)

    for hub, value in injections.items():
        if hub in HUB_SHARD_MAP and value > 0.0:
            index.inject_from_hub(hub, value)

    if propagate:
        index.propagate(steps=PROPAGATE_STEPS, mode="local")

    return {
        "incremental": True,
        "chi": round(inv.chi, 4),
        "beta_0": inv.beta_0,
        "beta_1": inv.beta_1,
        "t_b_norm": round(inv.t_b_norm, 4),
        "kappa_eff": round(new_kappa, 4),
        "signal": round(new_signal, 6),
        "injections": {h: round(v, 4) for h, v in injections.items()},
    }


def apply_fusion(
    index: HarmonicIndex,
    fusion: dict[str, Any],
    *,
    propagate: bool = True,
) -> dict[str, Any]:
    """
    Apply a fusion payload to the live MCP HarmonicIndex.

    Does not call CAIRRNBridge — that overlay is opt-in via cairrn_snapshot.
    """
    if not fusion.get("apply"):
        return {"applied": False}

    kappa = float(fusion.get("kappa_eff", BASE_KAPPA))
    signal = float(fusion.get("topology_signal", 0.0))
    t_b_norm = float(fusion.get("t_b_norm", 0.0))
    chi = float((fusion.get("invariant") or {}).get("chi", 0.0))
    steps = int(fusion.get("propagate_steps", PROPAGATE_STEPS))

    index.set_coupling(kappa)
    index.last_t_b_norm = t_b_norm
    index.last_chi = chi

    if signal > 0.0:
        index.inject(int(fusion.get("topology_shard", TOPOLOGY_SHARD)), signal)

    for hub, value in (fusion.get("hub_injections") or {}).items():
        if hub in HUB_SHARD_MAP and float(value) > 0.0:
            index.inject_from_hub(hub, float(value))

    if propagate and steps > 0:
        index.propagate(steps=steps, mode="local")

    return {
        "applied": True,
        "kappa_eff": index.coupling,
        "t_b_norm": index.last_t_b_norm,
        "chi": index.last_chi,
        "total_activation": round(index.total_activation(), 6),
    }
