from .obsidian_graph import ObsidianGraph, NoteNode
from .symbol_node import SymbolNode
from .unified_graph import UnifiedGraph
from .crawler import FilesystemCrawler

# ObsidianGraphDataset requires torch — imported lazily so that
# topology and obsidian_graph can be used in torch-free contexts.
def __getattr__(name: str):
    if name in ("ObsidianGraphDataset", "GraphBatch"):
        from .dataset import ObsidianGraphDataset, GraphBatch  # noqa: F401
        globals()["ObsidianGraphDataset"] = ObsidianGraphDataset
        globals()["GraphBatch"] = GraphBatch
        return globals()[name]
    raise AttributeError(f"module 'data' has no attribute {name!r}")

__all__ = [
    # Legacy Obsidian-only surface (unchanged)
    "ObsidianGraph",
    "NoteNode",
    "ObsidianGraphDataset",
    "GraphBatch",
    # Unified filesystem surface
    "SymbolNode",
    "UnifiedGraph",
    "FilesystemCrawler",
]
