"""
Semantic Topology Primitives
Algebraic topology primitives for the Obsidian knowledge graph.

    0-simplex  Vertex              — a note node
    1-simplex  Edge                — typed directed connection
    2-simplex  Triangle            — closed triple (transitive cluster seed)
    k-simplex  Simplex             — general k-chain
    TopologicalInvariant           — χ, β₀, β₁ snapshot
    BoundaryOperator               — ∂₁, ∂₂ boundary maps

The primitives are pure Python dataclasses — zero torch, zero networkx dependencies.
They are instantiated by TopologicalGraph from the underlying nx.DiGraph.

Euler-Poincaré formula (dim ≤ 2, β₂ = 0):
    χ  = V − E + T
    β₁ = β₀ − χ       (independent cycles / topological holes)
    ∂₁ ∘ ∂₂ = 0        (fundamental homology identity)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Set, Tuple


# ──────────────────────────────────────────────────────────────────────────────
# 0-simplex
# ──────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Vertex:
    """0-simplex: a single note node in the knowledge graph."""
    node_id: int
    title:   str
    path:    str

    def __repr__(self) -> str:
        return f"Vertex({self.node_id}, {self.title!r})"


# ──────────────────────────────────────────────────────────────────────────────
# 1-simplex
# ──────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Edge:
    """
    1-simplex: a typed directed edge between two vertices.

    edge_type ∈ {'wikilink', 'tag_overlap', 'temporal', 'semantic'}
    """
    src:       int
    dst:       int
    edge_type: str
    weight:    float = 1.0

    @property
    def boundary(self) -> Tuple[int, int]:
        """∂₁(edge) = (dst, src) — oriented endpoint pair."""
        return (self.dst, self.src)

    def __repr__(self) -> str:
        return f"Edge({self.src}→{self.dst}, {self.edge_type}, w={self.weight:.3f})"


# ──────────────────────────────────────────────────────────────────────────────
# 2-simplex
# ──────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Triangle:
    """
    2-simplex: a closed triple — the smallest topological cycle.
    nodes is always stored sorted so (i, j, k) == (j, i, k) is impossible.
    """
    nodes: Tuple[int, int, int]

    @property
    def boundary_edges(self) -> Tuple[Tuple[int, int], Tuple[int, int], Tuple[int, int]]:
        """∂₂(triangle) = its three bounding oriented edge pairs."""
        i, j, k = self.nodes
        return ((i, j), (j, k), (i, k))

    def __repr__(self) -> str:
        return f"Triangle{self.nodes}"


# ──────────────────────────────────────────────────────────────────────────────
# General k-simplex
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class Simplex:
    """
    General k-simplex: an ordered (k+1)-tuple of vertex ids.
    dimension = k = len(vertices) - 1.
    """
    vertices: Tuple[int, ...]

    @property
    def dimension(self) -> int:
        return len(self.vertices) - 1

    @property
    def faces(self) -> List["Simplex"]:
        """All (k-1)-dimensional faces: ∂_k drops one vertex at a time."""
        return [
            Simplex(self.vertices[:i] + self.vertices[i + 1:])
            for i in range(len(self.vertices))
        ]

    def __repr__(self) -> str:
        return f"Simplex({self.vertices}, dim={self.dimension})"


# ──────────────────────────────────────────────────────────────────────────────
# Topological invariant
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class TopologicalInvariant:
    """
    Snapshot of the topological invariants for the knowledge graph at one instant.

    Euler-Poincaré formula (β₂ = 0 for this graph family):
        χ  = V − E + T
        β₁ = β₀ − χ

    Also stores T_B — basin sequestration score — derived via basin_sequestration().
    T_B quantifies how deeply a graph region is topologically "contained":
        positive → deep basin, activation sequestered locally
        negative → open/shallow basin, activation spreads globally

    These values are the targets the CoherenceLayer uses each training step.
    They update whenever TopologicalGraph.build() is called.
    """
    V:      int    # vertex count
    E:      int    # edge count (all types)
    T:      int    # triangle count (2-simplices)
    chi:    float  # Euler characteristic = V − E + T
    beta_0: int    # connected components (0th Betti number)
    beta_1: int    # independent cycles   (1st Betti number)
    t_b:    float = 0.0  # basin sequestration score (auto-set by from_counts)

    @classmethod
    def from_counts(
        cls,
        V: int,
        E: int,
        T: int,
        beta_0: int,
    ) -> "TopologicalInvariant":
        chi    = V - E + T
        beta_1 = max(0, beta_0 - chi)
        inv    = cls(V=V, E=E, T=T, chi=chi, beta_0=beta_0, beta_1=beta_1)
        inv.t_b = inv.basin_sequestration()
        return inv

    def basin_sequestration(self) -> float:
        """
        Compute T_B — the basin sequestration score — from topology primitives.

        Formula (from handwritten derivation):
            T_B = A_xG · |BSH| / max(T, 1) − |BHD − 1|

        Variable mapping onto existing invariant fields:
            D    = V / max(β₀, 1)         graph diameter proxy (avg component size)
            D_M  = E / max(V, 1)          mean degree (modal diameter proxy)
            A_y  = V                       Area-Chi: node count as chi-area proxy
            A_xG = A_y · D · √D_M         cross-graph area
            BSH  = β₁ − D                 Basin Sequestration Height  (H − D)
            Sc   = χ · β₀                 classical sequestration (χ scaled by β₀)
            BHD  = Sc − D                 Basin Hole Depth

        Interpretation:
            T_B > 0  → deep basin, activation sequestered locally
            T_B ≈ 0  → neutral / transitional
            T_B < 0  → open basin, activation diffuses globally

        # TODO: replace D proxy with real nx.diameter() for graphs with V < 1000
        """
        import math
        V  = max(self.V, 1)
        E  = self.E
        T  = max(self.T, 1)          # floor prevents zero-division in dense graphs
        b0 = max(self.beta_0, 1)
        b1 = float(self.beta_1)

        D    = V / b0                               # diameter proxy
        D_M  = E / V                                # mean degree proxy
        A_y  = float(V)
        A_xG = A_y * D * math.sqrt(max(D_M, 0.0))

        BSH = b1 - D                                # β₁ − D
        Sc  = float(self.chi) * b0                  # χ · β₀
        BHD = Sc - D                                # Sc − D

        return A_xG * abs(BSH) / T - abs(BHD - 1.0)

    @property
    def t_b_norm(self) -> float:
        """
        T_B normalised to (−1, 1) via tanh scaled by V².

        Typical T_B grows as O(V²), so dividing by V² keeps the signal
        meaningful regardless of graph size:

            t_b_norm = tanh(T_B / max(V², 1))

        Feed directly into _t_b_to_alpha (which expects a value in this range):
            alpha = 0.5 + 0.5 · t_b_norm
        """
        V2 = max(self.V ** 2, 1)
        import math
        return math.tanh(self.t_b / V2)

    def as_dict(self) -> Dict[str, float]:
        return {
            "V":       float(self.V),
            "E":       float(self.E),
            "T":       float(self.T),
            "chi":     self.chi,
            "beta_0":  float(self.beta_0),
            "beta_1":  float(self.beta_1),
            "t_b":     self.t_b,
            "t_b_norm": self.t_b_norm,
        }

    def __repr__(self) -> str:
        return (
            f"TopologicalInvariant("
            f"V={self.V}, E={self.E}, T={self.T}, "
            f"χ={self.chi:.1f}, β₀={self.beta_0}, β₁={self.beta_1}, "
            f"T_B={self.t_b:.3f})"
        )


# ──────────────────────────────────────────────────────────────────────────────
# Boundary operator
# ──────────────────────────────────────────────────────────────────────────────

class BoundaryOperator:
    """
    Computes the boundary operators ∂₁ and ∂₂ as dense numpy incidence matrices.

    ∂₁ : C₁ → C₀  (V × E signed matrix)
        Entry [v, e] = +1  if v is the destination of edge e
                     = −1  if v is the source of edge e
                     =  0  otherwise

    ∂₂ : C₂ → C₁  (E × T signed matrix)
        Entry [e, t] = ±1 if edge e is a boundary face of triangle t
                     =  0  otherwise

    Fundamental identity: ∂₁ ∘ ∂₂ = 0   (boundary of a boundary is empty).
    verify_homology() checks this numerically.
    """

    def __init__(
        self,
        vertices:  List[Vertex],
        edges:     List[Edge],
        triangles: List[Triangle],
    ) -> None:
        self.vertices  = vertices
        self.edges     = edges
        self.triangles = triangles

        self._vid_to_idx: Dict[int, int] = {v.node_id: i for i, v in enumerate(vertices)}
        # index by (src, dst) pair — undirected lookup falls back to reversed pair
        self._eid_to_idx: Dict[Tuple[int, int], int] = {
            (e.src, e.dst): i for i, e in enumerate(edges)
        }

    def delta_1(self):
        """∂₁ incidence matrix — shape (V, E), dtype float32."""
        import numpy as np
        V, E = len(self.vertices), len(self.edges)
        mat = np.zeros((V, E), dtype=np.float32)
        for j, edge in enumerate(self.edges):
            i_src = self._vid_to_idx.get(edge.src)
            i_dst = self._vid_to_idx.get(edge.dst)
            if i_src is not None:
                mat[i_src, j] = -1.0
            if i_dst is not None:
                mat[i_dst, j] = +1.0
        return mat

    def delta_2(self):
        """∂₂ incidence matrix — shape (E, T), dtype float32."""
        import numpy as np
        E_count, T_count = len(self.edges), len(self.triangles)
        mat = np.zeros((E_count, T_count), dtype=np.float32)
        for j, tri in enumerate(self.triangles):
            a, b, c = tri.nodes
            for sign, (u, v) in zip([+1.0, +1.0, -1.0], [(a, b), (b, c), (a, c)]):
                eid = self._eid_to_idx.get((u, v))
                if eid is None:
                    eid = self._eid_to_idx.get((v, u))
                if eid is not None:
                    mat[eid, j] = sign
        return mat

    def verify_homology(self, atol: float = 1e-6) -> bool:
        """
        Verify the fundamental homology identity: ∂₁ ∘ ∂₂ = 0.
        Returns True if satisfied within numerical tolerance.
        """
        import numpy as np
        d2 = self.delta_2()
        if d2.shape[1] == 0:
            return True
        result = self.delta_1() @ d2
        return bool(np.allclose(result, 0.0, atol=atol))

    def betti_ranks(self):
        """
        Compute Betti numbers via matrix rank:
            β₀ = V − rank(∂₁)
            β₁ = rank(∂₁) − rank(∂₂)   (for dim ≤ 2)
        Returns (beta_0, beta_1).
        """
        import numpy as np
        d1 = self.delta_1()
        d2 = self.delta_2()
        r1 = int(np.linalg.matrix_rank(d1))
        r2 = int(np.linalg.matrix_rank(d2))
        V = len(self.vertices)
        beta_0 = V - r1
        beta_1 = r1 - r2
        return max(0, beta_0), max(0, beta_1)
