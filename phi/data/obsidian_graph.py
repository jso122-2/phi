"""
Local Graph Builder
Reads .md files directly from the vault path on disk.
No REST API, no plugins, no network required.
"""
import os
import re
import time
import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple

import networkx as nx
import numpy as np

logger = logging.getLogger(__name__)

_TS_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})-(\d{2})(\d{2})(\d{2})-")


@dataclass
class NoteNode:
    path: str
    title: str
    content_snippet: str
    tags: List[str] = field(default_factory=list)
    outlinks: List[str] = field(default_factory=list)
    created_ts: float = 0.0
    modified_ts: float = 0.0
    node_id: int = -1

    @property
    def encoding_text(self) -> str:
        return f"{self.title}: {self.content_snippet[:200]}"

    @property
    def content_hash(self) -> str:
        return hashlib.md5(self.content_snippet.encode()).hexdigest()


EDGE_TYPES = {
    "wikilink": 0,
    "tag_overlap": 1,
    "temporal": 2,
    "semantic": 3,
}

_SKIP_DIRS = {
    "__pycache__", ".git", ".obsidian", "node_modules", ".pytest_cache",
    "cursor-ingest", ".hub.git",
}
try:
    from graph.layers import (
        INGEST_TOP,
        PHI_VISIBLE_INGEST,
        SESSION_TOP,
        phi_visible,
    )
    _SKIP_DIRS |= (set(INGEST_TOP) - set(PHI_VISIBLE_INGEST)) | set(SESSION_TOP)
except Exception:  # pragma: no cover — phi used without graph package
    _SKIP_DIRS |= {"keep", "spotify-pipeline", "agent-log", "sessions"}

    def phi_visible(rel_path: str) -> bool:  # type: ignore[misc]
        rel = rel_path.replace("\\", "/").lstrip("./")
        if "/" not in rel:
            return True
        top = rel.split("/", 1)[0]
        if top in {"keep", "spotify-pipeline", "agent-log", "sessions", "cursor-ingest"}:
            return False
        return True

_UBIQUITOUS_TAGS = {"keep", "imported", "session", "prompt"}


class ObsidianGraph:
    """
    Builds a NetworkX DiGraph from .md files on disk.

    Usage:
        graph = ObsidianGraph(vault_path="/path/to/notes")
        graph.build()
    """

    def __init__(
        self,
        vault_path: Optional[str] = None,
        semantic_threshold: float = 0.65,
        temporal_window_days: float = 7.0,
        # Legacy kwargs accepted but ignored — no REST API
        local_vault_path: Optional[str] = None,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> None:
        self.vault_path = (
            vault_path
            or local_vault_path
            or os.environ.get("OBSIDIAN_VAULT_PATH", "")
        )
        self.semantic_threshold = semantic_threshold
        self.temporal_window = temporal_window_days * 86400

        self.nx_graph: nx.DiGraph = nx.DiGraph()
        self.notes: Dict[str, NoteNode] = {}
        self.path_to_id: Dict[str, int] = {}
        self._last_build_ts: float = 0.0

    # ──────────────────────────────────────────────────────────────────────────

    def build(self) -> None:
        if not self.vault_path or not os.path.isdir(self.vault_path):
            logger.warning(f"Vault path not found: {self.vault_path!r} — using mock graph.")
            self._build_mock_graph()
            return

        self._fetch_notes()
        self._add_wikilink_edges()
        self._add_tag_overlap_edges()
        self._add_temporal_edges()
        self._last_build_ts = time.time()
        logger.info(
            f"Graph built: {self.nx_graph.number_of_nodes()} nodes, "
            f"{self.nx_graph.number_of_edges()} edges"
        )

    def _fetch_notes(self) -> None:
        self.notes.clear()
        self.nx_graph.clear()
        self.path_to_id.clear()

        md_files = []
        for root, dirs, files in os.walk(self.vault_path):
            dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
            for fname in files:
                if fname.endswith(".md"):
                    md_files.append(os.path.join(root, fname))

        for idx, abs_path in enumerate(sorted(md_files)):
            rel_path = os.path.relpath(abs_path, self.vault_path).replace("\\", "/")
            if not phi_visible(rel_path):
                continue
            try:
                with open(abs_path, encoding="utf-8", errors="replace") as f:
                    raw = f.read()
            except OSError:
                continue

            title = self._extract_title(raw, rel_path)
            created_ts, modified_ts = self._extract_timestamps(abs_path, rel_path, raw)
            tags = self._extract_tags(raw)
            outlinks = self._extract_wikilinks(raw)
            snippet = self._extract_body(raw)[:500]

            note = NoteNode(
                path=rel_path,
                title=title,
                content_snippet=snippet,
                tags=tags,
                outlinks=outlinks,
                created_ts=created_ts,
                modified_ts=modified_ts,
                node_id=idx,
            )
            self.notes[rel_path] = note
            self.path_to_id[rel_path] = idx
            self.nx_graph.add_node(idx, note=note)

        logger.info(f"Loaded {len(self.notes)} notes from {self.vault_path}")

    # ──────────────────────────────────────────────────────────────────────────
    # Edge builders
    # ──────────────────────────────────────────────────────────────────────────

    def _add_wikilink_edges(self) -> None:
        title_to_path: Dict[str, str] = {}
        for p, n in self.notes.items():
            title_to_path[n.title.lower()] = p
            title_to_path[os.path.basename(p).replace(".md", "").lower()] = p

        for path, note in self.notes.items():
            for link in note.outlinks:
                target = title_to_path.get(link.lower())
                if target and target in self.path_to_id:
                    src, dst = self.path_to_id[path], self.path_to_id[target]
                    if src != dst:
                        self.nx_graph.add_edge(src, dst, edge_type="wikilink",
                                               edge_type_id=EDGE_TYPES["wikilink"], weight=1.0)

    def _add_tag_overlap_edges(self) -> None:
        notes_list = list(self.notes.values())
        for i in range(len(notes_list)):
            for j in range(i + 1, len(notes_list)):
                ni, nj = notes_list[i], notes_list[j]
                ti = set(ni.tags) - _UBIQUITOUS_TAGS
                tj = set(nj.tags) - _UBIQUITOUS_TAGS
                overlap = ti & tj
                if overlap:
                    w = len(overlap) / max(len(ti), len(tj), 1)
                    self.nx_graph.add_edge(ni.node_id, nj.node_id, edge_type="tag_overlap",
                                           edge_type_id=EDGE_TYPES["tag_overlap"], weight=w * 0.6)

    def _add_temporal_edges(self) -> None:
        notes_list = [n for n in self.notes.values() if n.modified_ts > 0]
        for i in range(len(notes_list)):
            for j in range(i + 1, len(notes_list)):
                ni, nj = notes_list[i], notes_list[j]
                dt = abs(ni.modified_ts - nj.modified_ts)
                if dt < self.temporal_window:
                    w = 0.4 * (1 - dt / self.temporal_window)
                    self.nx_graph.add_edge(ni.node_id, nj.node_id, edge_type="temporal",
                                           edge_type_id=EDGE_TYPES["temporal"], weight=w)

    def add_semantic_edges(self, node_embs: np.ndarray, threshold: Optional[float] = None) -> int:
        thresh = threshold if threshold is not None else self.semantic_threshold
        norms = np.linalg.norm(node_embs, axis=1, keepdims=True).clip(min=1e-8)
        sims = (node_embs / norms) @ (node_embs / norms).T
        added = 0
        N = sims.shape[0]
        for i in range(N):
            for j in range(i + 1, N):
                if sims[i, j] >= thresh and not self.nx_graph.has_edge(i, j):
                    self.nx_graph.add_edge(i, j, edge_type="semantic",
                                           edge_type_id=EDGE_TYPES["semantic"],
                                           weight=float(sims[i, j]) * 0.8)
                    added += 1
        return added

    # ──────────────────────────────────────────────────────────────────────────
    # Change detection
    # ──────────────────────────────────────────────────────────────────────────

    def detect_changes(self) -> Tuple[List[str], List[str]]:
        if not self.vault_path or not os.path.isdir(self.vault_path):
            return [], []
        current: Set[str] = set()
        for root, dirs, files in os.walk(self.vault_path):
            dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
            for fname in files:
                if fname.endswith(".md"):
                    current.add(os.path.relpath(os.path.join(root, fname), self.vault_path))
        known = set(self.notes.keys())
        new_paths = list(current - known)
        modified = [p for p in current & known
                    if os.path.getmtime(os.path.join(self.vault_path, p)) > self._last_build_ts]
        return new_paths, modified

    # ──────────────────────────────────────────────────────────────────────────
    # Title / content extraction
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _extract_title(content: str, rel_path: str) -> str:
        m = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        if m:
            heading = m.group(1).strip()
            if not re.match(r"^[\d\s:TtZz.\-+/]+$", heading):
                return heading

        stem = os.path.basename(rel_path).replace(".md", "")
        stem = re.sub(r"^\d{4}-\d{2}-\d{2}-\d{6}-", "", stem).strip("-_ ")
        stem = re.sub(r"^\d{4}-\d{2}-\d{2}[-t][\dtz.:\-+]+", "", stem, flags=re.IGNORECASE).strip("-_ ")
        if stem:
            return stem.replace("-", " ").title()

        for line in content.splitlines():
            line = line.strip()
            if line and not line.startswith(("#", ">", "-", "!", "```", "|")):
                return line[:60].rstrip()

        date_m = re.match(r"(\d{4}-\d{2}-\d{2})", os.path.basename(rel_path))
        return date_m.group(1) if date_m else os.path.basename(rel_path).replace(".md", "")

    @staticmethod
    def _extract_body(content: str) -> str:
        body = re.sub(r"(^>.*\n)+", "", content, flags=re.MULTILINE)
        body = re.sub(r"^---+\s*\n", "", body, flags=re.MULTILINE)
        body = re.sub(r"^#\s+.+\n?", "", body, count=1, flags=re.MULTILINE)
        return body.strip()

    @staticmethod
    def _extract_timestamps(abs_path: str, rel_path: str, content: str) -> Tuple[float, float]:
        mtime = os.path.getmtime(abs_path)
        fname = os.path.basename(rel_path)
        m = _TS_RE.match(fname)
        if m:
            try:
                dt = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                               int(m.group(4)), int(m.group(5)), int(m.group(6)),
                               tzinfo=timezone.utc)
                created_ts = dt.timestamp()
            except ValueError:
                created_ts = mtime
        else:
            created_ts = mtime

        modified_ts = mtime
        for line in content.splitlines():
            if re.search(r"Edited:", line, re.IGNORECASE):
                m2 = re.search(r"(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})", line)
                if m2:
                    try:
                        modified_ts = datetime.strptime(
                            f"{m2.group(1)} {m2.group(2)}", "%Y-%m-%d %H:%M"
                        ).replace(tzinfo=timezone.utc).timestamp()
                    except ValueError:
                        pass
        return created_ts, modified_ts

    @staticmethod
    def _extract_tags(content: str) -> List[str]:
        return re.findall(r"#([\w/-]+)", content)

    @staticmethod
    def _extract_wikilinks(content: str) -> List[str]:
        return re.findall(r"\[\[([^\]|#]+)(?:\|[^\]]*)?\]\]", content)

    def get_ordered_neighbors(self, node_id: int, strategy: str = "recency",
                               max_neighbors: int = 16) -> List[Tuple[int, int, float]]:
        from phi.utils.walk import order_neighbors
        return order_neighbors(self.nx_graph, node_id, strategy, max_neighbors)

    @property
    def num_nodes(self) -> int:
        return self.nx_graph.number_of_nodes()

    @property
    def all_texts(self) -> List[str]:
        return [n.encoding_text for n in sorted(self.notes.values(), key=lambda n: n.node_id)]

    # ──────────────────────────────────────────────────────────────────────────
    # Mock fallback (offline / missing vault)
    # ──────────────────────────────────────────────────────────────────────────

    def _build_mock_graph(self) -> None:
        mock = [
            ("Attention Mechanism", "The attention mechanism computes #transformer #ml"),
            ("Mamba SSM", "State space models for efficient sequence modeling #ssm #ml"),
            ("Graph Neural Networks", "Message passing on graph structures #gnn #ml"),
            ("DAWN Project", "Deep learning research [[Graph Neural Networks]] #project #ml"),
        ]
        for idx, (title, content) in enumerate(mock):
            note = NoteNode(path=f"{title.replace(' ', '_')}.md", title=title,
                            content_snippet=content, tags=self._extract_tags(content),
                            outlinks=self._extract_wikilinks(content), node_id=idx,
                            modified_ts=time.time() - idx * 3600)
            self.notes[note.path] = note
            self.path_to_id[note.path] = idx
            self.nx_graph.add_node(idx, note=note)
        self._add_wikilink_edges()
        self._add_tag_overlap_edges()
        logger.info("Using mock graph (vault path not found).")
