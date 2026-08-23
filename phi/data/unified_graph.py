"""
UnifiedGraph — generalised knowledge graph for the Samba GNN.

Accepts a list of SymbolNode objects (from any extractor) and builds a
NetworkX DiGraph with 7 edge types:

    wikilink    (0)   [[link]] between markdown notes
    tag_overlap (1)   shared tags / decorators
    temporal    (2)   files modified within the same time window
    semantic    (3)   cosine similarity of embeddings (added post-encode)
    import      (4)   Python/JS import edges between symbols
    co_file     (5)   symbols in the same source file
    co_repo     (6)   symbols in the same git repo

Public interface mirrors ObsidianGraph so dataset.py and the MCP coherence
tools require no changes. The existing ObsidianGraph is left untouched.
"""
import logging
import os
import time
from typing import Dict, List, Optional, Set, Tuple

import networkx as nx
import numpy as np

from .symbol_node import SymbolNode

logger = logging.getLogger(__name__)

EDGE_TYPES = {
    "wikilink":    0,
    "tag_overlap": 1,
    "temporal":    2,
    "semantic":    3,
    "import":      4,   # also used for call-graph edges (same structural role)
    "co_file":     5,
    "co_repo":     6,
    # Depth edges — mapped to existing ids to avoid retraining model
    "calls":       4,   # function A calls function B → import slot (structural dep)
    "inherits":    1,   # class A inherits class B → tag_overlap slot (hierarchy)
    "subheading":  5,   # note → section → co-file slot (structural proximity)
}

_UBIQUITOUS_TAGS = {"keep", "imported", "session", "prompt", "agent-log"}


class UnifiedGraph:
    """
    Build a NetworkX DiGraph from a list of SymbolNode objects.

    Usage:
        graph = UnifiedGraph()
        graph.build(symbols)          # from FilesystemCrawler output
        graph.add_semantic_edges(embs)
    """

    def __init__(
        self,
        semantic_threshold: float = 0.65,
        temporal_window_days: float = 1.0,    # reduced from 7d → 1d to avoid O(N²) blowup
        temporal_max_per_node: int = 8,        # cap per-node temporal edges
    ) -> None:
        self.semantic_threshold = semantic_threshold
        self.temporal_window = temporal_window_days * 86400
        self.temporal_max_per_node = temporal_max_per_node

        self.nx_graph: nx.DiGraph = nx.DiGraph()
        # Primary key: absolute path → SymbolNode
        # Multiple symbols per file → path is NOT unique; use node_id as key
        self.notes: Dict[str, SymbolNode] = {}   # node_id (str) → SymbolNode
        self.path_to_ids: Dict[str, List[int]] = {}  # path → list of node_ids
        self._last_build_ts: float = 0.0
        self._name_index: Dict[str, int] = {}    # qualified name → node_id

    # ──────────────────────────────────────────────────────────────────────────
    # Build
    # ──────────────────────────────────────────────────────────────────────────

    def build(self, symbols: List[SymbolNode]) -> None:
        """Construct graph from a flat list of SymbolNode objects."""
        self.nx_graph.clear()
        self.notes.clear()
        self.path_to_ids.clear()
        self._name_index.clear()

        admitted = [s for s in symbols if s.admitted]
        for idx, sym in enumerate(admitted):
            sym.node_id = idx
            self.notes[str(idx)] = sym
            self.path_to_ids.setdefault(sym.path, []).append(idx)
            self._name_index[sym.name] = idx
            # Also index bare function/class name without class prefix
            if "." in sym.name:
                bare = sym.name.split(".")[-1]
                self._name_index.setdefault(bare, idx)
            self.nx_graph.add_node(idx, note=sym)

        self._add_wikilink_edges()
        self._add_import_edges()
        self._add_call_edges()
        self._add_inheritance_edges()
        self._add_co_file_edges()
        self._add_co_repo_edges()
        self._add_tag_overlap_edges()
        self._add_temporal_edges()
        self._last_build_ts = time.time()

        logger.info(
            "UnifiedGraph built: %d nodes, %d edges (%d symbols admitted)",
            self.nx_graph.number_of_nodes(),
            self.nx_graph.number_of_edges(),
            len(admitted),
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Edge builders
    # ──────────────────────────────────────────────────────────────────────────

    def _add_wikilink_edges(self) -> None:
        title_to_id: Dict[str, int] = {
            sym.name.lower(): sym.node_id for sym in self.notes.values()
        }
        for sym in self.notes.values():
            for link in sym.outlinks:
                target_id = title_to_id.get(link.lower())
                if target_id is not None and target_id != sym.node_id:
                    self.nx_graph.add_edge(
                        sym.node_id, target_id,
                        edge_type="wikilink",
                        edge_type_id=EDGE_TYPES["wikilink"],
                        weight=1.0,
                    )

    def _add_import_edges(self) -> None:
        """Connect symbols to other symbols whose name matches an import."""
        for sym in self.notes.values():
            for imp in sym.imports:
                target_id = self._name_index.get(imp)
                if target_id is not None and target_id != sym.node_id:
                    self.nx_graph.add_edge(
                        sym.node_id, target_id,
                        edge_type="import",
                        edge_type_id=EDGE_TYPES["import"],
                        weight=1.0,
                    )

    def _add_call_edges(self) -> None:
        """
        Call-graph edges: function A calls function B → directed edge A→B.

        Uses the `calls` field populated by PythonExtractor (and others).
        Mapped to edge_type_id=4 (import slot) — same structural role.
        """
        for sym in self.notes.values():
            for called_name in sym.calls:
                target_id = self._name_index.get(called_name)
                if target_id is not None and target_id != sym.node_id:
                    if not self.nx_graph.has_edge(sym.node_id, target_id):
                        self.nx_graph.add_edge(
                            sym.node_id, target_id,
                            edge_type="calls",
                            edge_type_id=EDGE_TYPES["calls"],
                            weight=0.9,
                        )

    def _add_inheritance_edges(self) -> None:
        """
        Inheritance edges: class A inherits from class B → directed edge A→B.

        Uses the `bases` field populated by PythonExtractor.
        Mapped to edge_type_id=1 (tag_overlap slot) — hierarchy signal.
        """
        for sym in self.notes.values():
            for base_name in sym.bases:
                target_id = self._name_index.get(base_name)
                if target_id is not None and target_id != sym.node_id:
                    self.nx_graph.add_edge(
                        sym.node_id, target_id,
                        edge_type="inherits",
                        edge_type_id=EDGE_TYPES["inherits"],
                        weight=1.0,
                    )

    def _add_co_file_edges(self) -> None:
        """Symbols that live in the same source file get a lightweight edge."""
        for path, ids in self.path_to_ids.items():
            if len(ids) < 2:
                continue
            for i in range(len(ids)):
                for j in range(i + 1, len(ids)):
                    self.nx_graph.add_edge(
                        ids[i], ids[j],
                        edge_type="co_file",
                        edge_type_id=EDGE_TYPES["co_file"],
                        weight=0.5,
                    )

    def _add_co_repo_edges(self) -> None:
        """Symbols in the same git repo get a weak co-repo edge (max 5 per node)."""
        repo_to_ids: Dict[str, List[int]] = {}
        for sym in self.notes.values():
            if sym.repo:
                repo_to_ids.setdefault(sym.repo, []).append(sym.node_id)

        for repo, ids in repo_to_ids.items():
            # To avoid O(N²) on large repos, only connect to nearest 5 peers
            for i, src in enumerate(ids):
                for dst in ids[max(0, i - 5): i]:
                    if src != dst:
                        self.nx_graph.add_edge(
                            src, dst,
                            edge_type="co_repo",
                            edge_type_id=EDGE_TYPES["co_repo"],
                            weight=0.3,
                        )

    def _add_tag_overlap_edges(self) -> None:
        syms = list(self.notes.values())
        for i in range(len(syms)):
            for j in range(i + 1, len(syms)):
                ti = set(syms[i].tags) - _UBIQUITOUS_TAGS
                tj = set(syms[j].tags) - _UBIQUITOUS_TAGS
                overlap = ti & tj
                if overlap:
                    w = len(overlap) / max(len(ti), len(tj), 1) * 0.6
                    self.nx_graph.add_edge(
                        syms[i].node_id, syms[j].node_id,
                        edge_type="tag_overlap",
                        edge_type_id=EDGE_TYPES["tag_overlap"],
                        weight=w,
                    )

    def _add_temporal_edges(self) -> None:
        """
        Connect nodes modified within the same time window.

        Window is capped at 1 day (was 7 days) to avoid the O(N²) blowup
        that occurred when thousands of files all had recent mtimes.
        Each node is also capped at temporal_max_per_node outgoing temporal
        edges (closest-in-time neighbors first).
        """
        syms = sorted(
            [s for s in self.notes.values() if s.modified_ts > 0],
            key=lambda s: s.modified_ts,
        )
        # Track per-node temporal edge count
        edge_counts: Dict[int, int] = {}

        for i, src in enumerate(syms):
            if edge_counts.get(src.node_id, 0) >= self.temporal_max_per_node:
                continue
            # Only check nearby-in-time candidates (syms is sorted by mtime)
            for j in range(i + 1, len(syms)):
                dst = syms[j]
                dt = dst.modified_ts - src.modified_ts  # always >= 0 (sorted)
                if dt >= self.temporal_window:
                    break  # all subsequent are even further away
                if edge_counts.get(src.node_id, 0) >= self.temporal_max_per_node:
                    break
                if edge_counts.get(dst.node_id, 0) >= self.temporal_max_per_node:
                    continue
                w = 0.4 * (1 - dt / self.temporal_window)
                self.nx_graph.add_edge(
                    src.node_id, dst.node_id,
                    edge_type="temporal",
                    edge_type_id=EDGE_TYPES["temporal"],
                    weight=w,
                )
                edge_counts[src.node_id] = edge_counts.get(src.node_id, 0) + 1
                edge_counts[dst.node_id] = edge_counts.get(dst.node_id, 0) + 1

    def add_semantic_edges(self, node_embs: np.ndarray, threshold: Optional[float] = None) -> int:
        """Add cosine-similarity edges after embeddings are computed."""
        thresh = threshold if threshold is not None else self.semantic_threshold
        norms = np.linalg.norm(node_embs, axis=1, keepdims=True).clip(min=1e-8)
        sims = (node_embs / norms) @ (node_embs / norms).T
        added = 0
        N = sims.shape[0]
        for i in range(N):
            for j in range(i + 1, N):
                if sims[i, j] >= thresh and not self.nx_graph.has_edge(i, j):
                    self.nx_graph.add_edge(
                        i, j,
                        edge_type="semantic",
                        edge_type_id=EDGE_TYPES["semantic"],
                        weight=float(sims[i, j]) * 0.8,
                    )
                    added += 1
        return added

    # ──────────────────────────────────────────────────────────────────────────
    # ObsidianGraph-compatible interface (used by dataset.py and MCP tools)
    # ──────────────────────────────────────────────────────────────────────────

    @property
    def num_nodes(self) -> int:
        return self.nx_graph.number_of_nodes()

    @property
    def all_texts(self) -> List[str]:
        return [
            s.encoding_text
            for s in sorted(self.notes.values(), key=lambda s: s.node_id)
        ]

    def get_ordered_neighbors(
        self,
        node_id: int,
        strategy: str = "recency",
        max_neighbors: int = 16,
    ) -> List[Tuple[int, int, float]]:
        from phi.utils.walk import order_neighbors
        return order_neighbors(self.nx_graph, node_id, strategy, max_neighbors)

    def detect_changes(self) -> Tuple[List[str], List[str]]:
        """Return (new_paths, modified_paths) since last build."""
        known_paths: Set[str] = set(self.path_to_ids.keys())
        new_paths: List[str] = []
        modified: List[str] = []
        for path in known_paths:
            if not os.path.exists(path):
                continue
            if os.path.getmtime(path) > self._last_build_ts:
                modified.append(path)
        return new_paths, modified

    def nearest_similarity(self, embedding: np.ndarray) -> float:
        """
        Return cosine similarity to the nearest existing node.
        Used by AutonomousGate for novelty scoring.
        Falls back to 0.0 (maximally novel) when graph is empty.
        """
        if not hasattr(self, "_cached_embs") or self._cached_embs is None:
            return 0.0
        embs = self._cached_embs
        norm_q = embedding / (np.linalg.norm(embedding) + 1e-8)
        norms = np.linalg.norm(embs, axis=1, keepdims=True).clip(min=1e-8)
        sims = (embs / norms) @ norm_q
        return float(sims.max()) if len(sims) else 0.0

    def cache_embeddings(self, embs: np.ndarray) -> None:
        """Cache node embeddings for nearest_similarity lookups."""
        self._cached_embs = embs
