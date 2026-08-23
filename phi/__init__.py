"""
phi — music library graph for OctopusTracer.

    from phi import PhiLibrary, Track, LIBRARY_ROOT
    from phi import CLAPProjection, MetadataEncoder
    from phi import PhiGraph, PhiGraphSnapshot
    from phi import AudioFeatures, GraphPosition, SongNode, build_window

Merged from samba-gnn-obsidian:
    phi.core       — player, queue, ranker, zaltar, similarity, session
    phi.audio      — audio ingestion / feature extraction
    phi.watch      — vault/library file watcher
    phi.meta       — metadata enrichment
    phi.engine     — forest floor, CAIRRN router/bridge, similarity index
    phi.gnn        — SambaGNN, OctopusTracer, SelectiveSSM (torch)
    phi.topology   — TopologicalGraph, primitives
    phi.data       — Obsidian graph crawlers, dataset builders
    phi.utils      — logging, scheduling, walk utilities
"""
__version__ = "0.3.0"

from phi.library import PhiLibrary, Track, LIBRARY_ROOT
from phi.graph import PhiGraph, PhiGraphSnapshot
from phi.metadata import AudioFeatures, GraphPosition, SongNode, build_window
from phi.models import CLAPProjection, MetadataEncoder, GeminiClipper

__all__ = [
    # library
    "PhiLibrary",
    "Track",
    "LIBRARY_ROOT",
    # graph
    "PhiGraph",
    "PhiGraphSnapshot",
    # metadata
    "AudioFeatures",
    "GraphPosition",
    "SongNode",
    "build_window",
    # models
    "CLAPProjection",
    "MetadataEncoder",
    "GeminiClipper",
    # subpackages (import on demand)
    "core",
    "audio",
    "watch",
    "meta",
    "engine",
    "gnn",
    "topology",
    "data",
    "utils",
]
