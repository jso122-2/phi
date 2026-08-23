"""
topology — Semantic Topology Primitives and Topological Graph

Public surface:

    Primitives (pure Python, zero-dependency):
        from topology import Vertex, Edge, Triangle, Simplex
        from topology import TopologicalInvariant
        from topology import BoundaryOperator

    Topological graph (wraps ObsidianGraph):
        from topology import TopologicalGraph

Typical usage:
    obs_graph = ObsidianGraph(vault_path=...)
    obs_graph.build()

    topo = TopologicalGraph(obs_graph)
    topo.build()

    inv = topo.invariant        # TopologicalInvariant: χ, β₀, β₁, V, E, T
    op  = topo.boundary_operator  # BoundaryOperator: ∂₁ (V×E), ∂₂ (E×T)
    ok  = op.verify_homology()  # True iff ∂₁ ∘ ∂₂ = 0

    snap = topo.snapshot()      # dict for HealthLog / engine reporting
"""
from .primitives import (
    BoundaryOperator,
    Edge,
    Simplex,
    TopologicalInvariant,
    Triangle,
    Vertex,
)
from .topo_graph import TopologicalGraph

__all__ = [
    "Vertex",
    "Edge",
    "Triangle",
    "Simplex",
    "TopologicalInvariant",
    "BoundaryOperator",
    "TopologicalGraph",
]
