"""
TopologicalGraph
Algebraic topology wrapper over ObsidianGraph.

Decomposes the underlying nx.DiGraph into the primitive simplex hierarchy:
    0-simplices  → Vertex   (all note nodes)
    1-simplices  → Edge     (typed directed links)
    2-simplices  → Triangle (closed triples — smallest cycles)

Computes and caches the topological invariants:
    χ  = V − E + T      (Euler characteristic)
    β₀                  (connected components, 0th Betti number)
    β₁ = β₀ − χ        (independent cycles, 1st Betti number)

Also builds the boundary operators ∂₁ and ∂₂, and supports the semantic
simplex complex — simplices formed by note embedding cosine similarity
rather than explicit graph edges.

Usage:
    topo = TopologicalGraph(obs_graph)
    topo.build()
    inv = topo.invariant              # TopologicalInvariant
    op  = topo.boundary_operator      # BoundaryOperator (∂₁, ∂₂)
    snap = topo.snapshot()            # dict for HealthLog / MCP

Binding the engine:
    CoherenceDaemon calls topo.build() each cycle, then reads topo.snapshot()
    instead of computing raw V/E/T from NetworkX by hand.

Binding the model:
    CoherenceLayer receives topo.invariant.chi as its Euler χ target.
    SambaOrchestrator.refresh() calls topo.build() after graph.build().
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Dict, List, Optional, Set, Tuple

import networkx as nx
import numpy as np

# ObsidianGraph / NoteNode pulled in only for type checking — avoids triggering
# data/__init__.py's eager torch import when topology is imported standalone.
if TYPE_CHECKING:
    from phi.data.obsidian_graph import NoteNode, ObsidianGraph

from phi.topology.primitives import (
    BoundaryOperator,
    Edge,
    TopologicalInvariant,
    Triangle,
    Vertex,
)

logger = logging.getLogger(__name__)


class TopologicalGraph:
    """
    Builds and caches the full simplicial complex for an ObsidianGraph.

    The topology is recomputed on each call to build(), which is triggered:
      - by SambaOrchestrator.refresh() after every vault change
      - by CoherenceDaemon.run_once() at the start of each cycle

    All derived topology (boundary operators, Betti numbers, snapshots) is
    available immediately after build() returns.
    """

    def __init__(self, graph: "ObsidianGraph") -> None:
        self._graph = graph
        self._vertices:  List[Vertex]   = []
        self._edges:     List[Edge]     = []
        self._triangles: List[Triangle] = []
        self._invariant: Optional[TopologicalInvariant] = None
        self._boundary:  Optional[BoundaryOperator]     = None

    # ──────────────────────────────────────────────────────────────────────────
    # Build
    # ──────────────────────────────────────────────────────────────────────────

    def build(self) -> None:
        """
        Decompose the current nx.DiGraph into topology primitives.
        Safe to call multiple times — each call rebuilds from scratch.
        """
        G = self._graph.nx_graph
        self._build_vertices(G)
        self._build_edges(G)
        self._build_triangles(G)
        self._build_invariant(G)
        self._boundary = BoundaryOperator(self._vertices, self._edges, self._triangles)
        logger.debug(
            "TopologicalGraph built: %s",
            self._invariant,
        )

    def _build_vertices(self, G: nx.DiGraph) -> None:
        self._vertices = []
        for node_id, data in G.nodes(data=True):
            note = data.get("note")   # NoteNode at runtime; no import needed
            self._vertices.append(Vertex(
                node_id=node_id,
                title=note.title if note else str(node_id),
                path=note.path  if note else "",
            ))

    def _build_edges(self, G: nx.DiGraph) -> None:
        self._edges = []
        for src, dst, data in G.edges(data=True):
            self._edges.append(Edge(
                src=src,
                dst=dst,
                edge_type=data.get("edge_type", "unknown"),
                weight=float(data.get("weight", 1.0)),
            ))

    def _build_triangles(self, G: nx.DiGraph, max_degree: int = 50, max_triangles: int = 50_000) -> None:
        """
        Find 2-simplices (closed triples) via undirected triangle enumeration.

        Skips high-degree nodes (degree > max_degree) to avoid O(d²) blowup on dense
        graphs (e.g. unified filesystem graphs with hundreds of edges per node).
        Stops after max_triangles are found.

        For very dense graphs the Euler characteristic estimate degrades gracefully:
        χ = V − E + 0 is still a valid lower bound of the true χ.
        """
        self._triangles = []
        G_ud = G.to_undirected()
        seen: Set[Tuple[int, int, int]] = set()
        for node in G_ud.nodes():
            if len(self._triangles) >= max_triangles:
                break
            nbrs = set(G_ud.neighbors(node))
            if len(nbrs) > max_degree:
                continue        # skip hub nodes — too expensive, skew triangle count
            for nbr in list(nbrs):
                if len(self._triangles) >= max_triangles:
                    break
                nbr_nbrs = set(G_ud.neighbors(nbr))
                if len(nbr_nbrs) > max_degree:
                    continue
                common = nbrs & nbr_nbrs
                for third in common:
                    key = tuple(sorted([node, nbr, third]))
                    if key not in seen:
                        seen.add(key)
                        self._triangles.append(Triangle(nodes=key))
                        if len(self._triangles) >= max_triangles:
                            break
        if len(self._triangles) >= max_triangles:
            logger.debug("Triangle cap reached (%d) — dense graph, χ is a lower bound", max_triangles)

    def _build_invariant(self, G: nx.DiGraph) -> None:
        V      = len(self._vertices)
        E      = len(self._edges)
        T      = len(self._triangles)
        beta_0 = nx.number_weakly_connected_components(G)
        self._invariant = TopologicalInvariant.from_counts(V=V, E=E, T=T, beta_0=beta_0)

    # ──────────────────────────────────────────────────────────────────────────
    # Public accessors
    # ──────────────────────────────────────────────────────────────────────────

    @property
    def vertices(self) -> List[Vertex]:
        return self._vertices

    @property
    def edges(self) -> List[Edge]:
        return self._edges

    @property
    def triangles(self) -> List[Triangle]:
        return self._triangles

    @property
    def edges_by_type(self) -> Dict[str, List[Edge]]:
        result: Dict[str, List[Edge]] = {}
        for e in self._edges:
            result.setdefault(e.edge_type, []).append(e)
        return result

    @property
    def invariant(self) -> TopologicalInvariant:
        if self._invariant is None:
            raise RuntimeError("Call build() before accessing topology.")
        return self._invariant

    @property
    def boundary_operator(self) -> BoundaryOperator:
        if self._boundary is None:
            raise RuntimeError("Call build() before accessing boundary operators.")
        return self._boundary

    # ──────────────────────────────────────────────────────────────────────────
    # Semantic simplex complex
    # ──────────────────────────────────────────────────────────────────────────

    def semantic_simplex_complex(
        self,
        node_embeddings: np.ndarray,
        threshold: float = 0.65,
    ) -> Tuple[List[Edge], List[Triangle]]:
        """
        Build the *semantic* simplicial complex from node embeddings.

        An edge (i, j) exists when cosine_similarity(h_i, h_j) ≥ threshold.
        A triangle (i, j, k) exists when all three pairs exceed the threshold.

        This is the semantic topology layer — conceptual proximity independent
        of wikilinks, tags, or timestamps. Used to:
          - surface implicit connections the graph has not yet encoded
          - detect semantic holes (missing triangles) for bridge-note generation
          - provide a semantic χ_sem for CoherenceLayer targeting

        Returns:
            sem_edges:     List[Edge]     — semantic 1-simplices
            sem_triangles: List[Triangle] — semantic 2-simplices
        """
        norms = np.linalg.norm(node_embeddings, axis=1, keepdims=True).clip(min=1e-8)
        sims  = (node_embeddings / norms) @ (node_embeddings / norms).T
        N     = sims.shape[0]

        sem_edges: List[Edge] = []
        sim_pairs: List[Tuple[int, int]] = []

        for i in range(N):
            for j in range(i + 1, N):
                if sims[i, j] >= threshold:
                    sem_edges.append(Edge(
                        src=i, dst=j,
                        edge_type="semantic",
                        weight=float(sims[i, j]),
                    ))
                    sim_pairs.append((i, j))

        pair_set = set(sim_pairs)
        sem_triangles: List[Triangle] = []
        seen: Set[Tuple[int, int, int]] = set()

        for (i, j) in sim_pairs:
            for k in range(N):
                if k == i or k == j:
                    continue
                p_ik = (min(i, k), max(i, k))
                p_jk = (min(j, k), max(j, k))
                if p_ik in pair_set and p_jk in pair_set:
                    key = tuple(sorted([i, j, k]))
                    if key not in seen:
                        seen.add(key)
                        sem_triangles.append(Triangle(nodes=key))

        return sem_edges, sem_triangles

    def semantic_invariant(
        self,
        node_embeddings: np.ndarray,
        threshold: float = 0.65,
    ) -> TopologicalInvariant:
        """
        Compute TopologicalInvariant for the semantic simplex complex.
        This χ_sem measures the topological shape of the *conceptual* graph,
        separate from the explicit wikilink/tag graph.
        """
        sem_edges, sem_triangles = self.semantic_simplex_complex(node_embeddings, threshold)
        N = node_embeddings.shape[0]
        E = len(sem_edges)
        T = len(sem_triangles)
        # build a temporary undirected graph for component counting
        import networkx as _nx
        G_sem = _nx.Graph()
        G_sem.add_nodes_from(range(N))
        G_sem.add_edges_from((e.src, e.dst) for e in sem_edges)
        beta_0 = _nx.number_connected_components(G_sem)
        return TopologicalInvariant.from_counts(V=N, E=E, T=T, beta_0=beta_0)

    # ──────────────────────────────────────────────────────────────────────────
    # Connected components
    # ──────────────────────────────────────────────────────────────────────────

    def connected_components(self) -> List[Set[int]]:
        """Weakly connected components — each returned as a set of node_ids."""
        G = self._graph.nx_graph
        return [set(c) for c in nx.weakly_connected_components(G)]

    def largest_component_fraction(self) -> float:
        """Fraction of nodes in the largest connected component (connectivity health)."""
        comps = self.connected_components()
        if not comps:
            return 0.0
        return max(len(c) for c in comps) / max(len(self._vertices), 1)

    # ──────────────────────────────────────────────────────────────────────────
    # Snapshot — used by HealthLog and CoherenceDaemon
    # ──────────────────────────────────────────────────────────────────────────

    def snapshot(self) -> dict:
        """
        Full topology snapshot suitable for HealthLog.append() and MCP reporting.
        Replaces the ad-hoc V/E/T computation that was in _graph_snapshot().
        """
        inv    = self.invariant
        by_type = self.edges_by_type
        return {
            **inv.as_dict(),
            "notes":            inv.V,
            "edges":            inv.E,
            "triangles":        inv.T,
            "chi":              inv.chi,
            "wikilink_edges":   len(by_type.get("wikilink",   [])),
            "tag_edges":        len(by_type.get("tag_overlap", [])),
            "temporal_edges":   len(by_type.get("temporal",   [])),
            "semantic_edges":   len(by_type.get("semantic",   [])),
            "largest_component_fraction": self.largest_component_fraction(),
        }
