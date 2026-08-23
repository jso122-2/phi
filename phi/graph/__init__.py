"""phi graph — PhiGraph, PhiGraphSnapshot, window pipeline, and GNN graph."""
from phi.graph.phi_graph import PhiGraph, PhiGraphSnapshot, SongNode
from phi.graph._window_pipeline import (
    WindowTensors,
    WindowResult,
    build_window_tensors,
    run_window,
)

# GNN-side graph (torch, OctopusTracer-compatible) — import only when torch present
try:
    from phi.graph.phi_graph_gnn import PhiGraph as PhiGraphGNN  # noqa: F401
    from phi.graph.phi_graph_builder import PhiGraphBuilder  # noqa: F401
    from phi.graph.phi_orchestrator import PhiOrchestrator  # noqa: F401
    from phi.graph.phi_tracer_bridge import PhiTracerBridge  # noqa: F401
    from phi.graph.derivative_bridge import DerivativeBridge  # noqa: F401
    _GNN_AVAILABLE = True
except ImportError:
    _GNN_AVAILABLE = False

__all__ = [
    "PhiGraph",
    "PhiGraphSnapshot",
    "SongNode",
    "WindowTensors",
    "WindowResult",
    "build_window_tensors",
    "run_window",
    # GNN graph (torch)
    "PhiGraphGNN",
    "PhiGraphBuilder",
    "PhiOrchestrator",
    "PhiTracerBridge",
    "DerivativeBridge",
    "_GNN_AVAILABLE",
]
