"""phi.metadata — Three-layer song node schema for OctopusTracer.

    from phi.metadata import AudioFeatures, GraphPosition, SongNode
    from phi.metadata import build_window, update_degrees
    from phi.metadata import extract, extract_or_zero
"""
from phi.metadata.schema import (
    AudioFeatures,
    GraphPosition,
    SongNode,
    WINDOW_SIZE,
)
from phi.metadata.extractor import extract, extract_or_zero
from phi.metadata.node_builder import build_window, update_degrees

__all__ = [
    "AudioFeatures",
    "GraphPosition",
    "SongNode",
    "WINDOW_SIZE",
    "extract",
    "extract_or_zero",
    "build_window",
    "update_degrees",
]
