# -*- coding: utf-8 -*-
"""phi.graph.phi_graph_builder — topology-aware music graph construction.

Extends `PhiGraph` (which builds H from CLAP embeddings) with:

  1. Typed music edges wired into an ObsidianGraph-compatible nx.DiGraph:
       semantic   — CLAP cosine similarity > threshold
       wikilink   — Camelot harmonic key compatibility (±1 on wheel, relative)
       temporal   — BPM proximity |BPM_i − BPM_j| < bpm_window
       tag_overlap — shared mood / genre tags from Phi annotations

  2. TopologicalGraph built over those edges → χ, β₀, β₁, ∂₁, ∂₂

  3. D4InjectionLayer — `nn.Linear(1, d_model)` that additively biases H with
     D4 acoustic quality scores before the OctopusTracer forward pass.

The typed edge set gives the music graph the same multi-relational topology
as the Obsidian knowledge graph, making `TopologicalGraph`'s Euler
characteristic meaningful in a music context and usable as the live
`euler_chi_target` for `CoherenceLayer` each PhiOrchestrator cycle.

Usage
─────
    builder  = PhiGraphBuilder(library, clap_proj)
    snap     = phi_graph.build()             # PhiGraphSnapshot (H built)
    snap     = score_and_attach(snap)        # D4 scores attached
    topo     = builder.build_topology(snap)  # TopologicalGraph over music edges
    H_aug    = builder.inject_d4(H=snap.H, d4=snap.d4_scores)
    out      = tracer(H_aug)

Reference:
    Camelot wheel: DJ mixing harmonic compatibility table (Open Key notation)
    CLAP: Wu et al. (2023), https://arxiv.org/abs/2211.06687
    TopologicalGraph: topology/topo_graph.py (this project)
"""
from __future__ import annotations

import logging
import math
import re
from typing import TYPE_CHECKING, Dict, List, Optional, Set, Tuple

try:
    import torch
    import torch.nn as nn
    _TORCH_OK = True
except ImportError:
    torch = None  # type: ignore[assignment]
    nn = None  # type: ignore[assignment]
    _TORCH_OK = False

if TYPE_CHECKING:
    from phi.core.library import Library
    from phi.models.clap_proj import CLAPProjection
    from phi.graph.phi_graph import PhiGraphSnapshot
    from phi.topology.topo_graph import TopologicalGraph

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Camelot wheel compatibility
# ──────────────────────────────────────────────────────────────────────────────

# Regex parses "1A", "12B", "10A", etc.
_CAMELOT_RE = re.compile(r"^(\d{1,2})([AB])$", re.IGNORECASE)


def _parse_camelot(code: str) -> Optional[Tuple[int, str]]:
    """Parse a Camelot code like '5A' or '12B' → (number, letter) or None."""
    if not code:
        return None
    m = _CAMELOT_RE.match(code.strip())
    if not m:
        return None
    return int(m.group(1)), m.group(2).upper()


def camelot_compatible(code_a: str, code_b: str) -> bool:
    """
    True when two Camelot codes are harmonically compatible for DJ mixing.

    Compatibility rules (Open Key / Camelot wheel):
        1. Same code                   — same key
        2. ±1 number, same letter      — dominant / subdominant relationship
        3. Same number, different letter — relative major / minor
    """
    a = _parse_camelot(code_a)
    b = _parse_camelot(code_b)
    if a is None or b is None:
        return False
    num_a, let_a = a
    num_b, let_b = b

    if num_a == num_b and let_a == let_b:
        return True

    if let_a == let_b:
        diff = abs(num_a - num_b)
        return diff == 1 or diff == 11   # wrap-around: 1 and 12

    if num_a == num_b:
        return True   # relative key

    return False


# ──────────────────────────────────────────────────────────────────────────────
# D4 injection layer
# ──────────────────────────────────────────────────────────────────────────────

if _TORCH_OK:
    class D4InjectionLayer(nn.Module):  # type: ignore[misc]
        """Additively biases node embeddings H with the D4 acoustic quality score."""

        def __init__(self, d_model: int = 256) -> None:
            super().__init__()
            self.d_model = d_model
            self.proj = nn.Linear(1, d_model, bias=True)
            nn.init.xavier_uniform_(self.proj.weight)
            nn.init.zeros_(self.proj.bias)

        def forward(self, H, d4):
            assert H.ndim == 2 and H.size(-1) == self.d_model
            assert d4.ndim == 1 and d4.size(0) == H.size(0)
            d4_clean = d4.nan_to_num(nan=0.5).to(H.device).unsqueeze(-1)
            bias     = self.proj(d4_clean)
            return H + bias

        def parameter_count(self) -> int:
            return sum(p.numel() for p in self.parameters())
else:
    class D4InjectionLayer:  # type: ignore[no-redef]
        """Stub: torch not available."""
        def __init__(self, *a, **kw): pass


# ──────────────────────────────────────────────────────────────────────────────
# PhiGraphBuilder
# ──────────────────────────────────────────────────────────────────────────────

class PhiGraphBuilder:
    """
    Builds a topology-aware music graph from a Phi Library for OctopusTracer.

    Unlike `PhiGraph` (which builds H in soft-edge mode with no explicit
    topology), `PhiGraphBuilder` constructs a full typed edge set over the
    same CLAP-embedded tracks and computes `TopologicalGraph` invariants
    (χ, β₀, β₁) from those edges.

    The graph mirrors the four edge types used in ObsidianGraph:
        semantic   — CLAP cosine similarity > sim_threshold
        wikilink   — Camelot harmonic key compatibility (±1 wheel)
        temporal   — BPM proximity |BPM_i − BPM_j| < bpm_window
        tag_overlap — shared mood / genre / era tags (Phi annotations)

    Args:
        library:        Phi Library instance (source of annotations)
        clap_proj:      CLAPProjection — for the semantic edge computation
        sim_threshold:  CLAP cosine similarity floor for semantic edges (default 0.65)
        bpm_window:     BPM difference floor for temporal edges in beats/min (default 8.0)
        device:         torch device for H tensors (default: cpu)
    """

    def __init__(
        self,
        library:        "Library",
        clap_proj:      "CLAPProjection",
        sim_threshold:  float = 0.65,
        bpm_window:     float = 8.0,
        device:         Optional[torch.device] = None,
    ) -> None:
        self._library       = library
        self._clap_proj     = clap_proj
        self._sim_threshold = sim_threshold
        self._bpm_window    = bpm_window
        self._device        = device or torch.device("cpu")

    # ── public API ────────────────────────────────────────────────────────────

    def build_topology(
        self,
        snap: "PhiGraphSnapshot",
    ) -> "TopologicalGraph":
        """
        Build a TopologicalGraph from the music graph encoded in *snap*.

        Constructs an ObsidianGraph-compatible nx.DiGraph with four typed edge
        families, then instantiates and builds a TopologicalGraph over it.

        Args:
            snap: PhiGraphSnapshot produced by PhiGraph.build() — provides H
                  and the ordered path list.  Optionally should have d4_scores
                  attached via score_and_attach().

        Returns:
            TopologicalGraph with .invariant (χ, β₀, β₁) and
            .boundary_operator (∂₁, ∂₂) ready for CoherenceLayer binding.
        """
        from phi.data.obsidian_graph import NoteNode, ObsidianGraph, EDGE_TYPES
        from phi.topology.topo_graph import TopologicalGraph

        obs = ObsidianGraph()   # blank vault — we populate nx_graph directly
        G   = obs.nx_graph

        paths = snap.paths
        N     = len(paths)
        if N == 0:
            logger.warning("PhiGraphBuilder.build_topology: empty snapshot — no CLAP tracks.")
            topo = TopologicalGraph(obs)
            topo.build()
            return topo

        # ── 1. Add one NoteNode per track ─────────────────────────────────────
        for idx, path in enumerate(paths):
            ann   = self._library.annotations.get(path, {})
            meta  = self._library.meta_cache.get(path, {})
            title = meta.get("title") or (
                (meta.get("artist") or "") + " - " + (meta.get("album") or "")
            )
            title = title.strip(" -") or path
            bpm   = ann.get("bpm") or meta.get("bpm")
            key   = ann.get("key", "")
            mood  = ann.get("mood", "")
            snippet = f"bpm={bpm}  key={key}  mood={mood}"

            note = NoteNode(
                path=path,
                title=title,
                content_snippet=snippet,
                tags=self._collect_tags(ann),
                node_id=idx,
            )
            obs.notes[path]           = note
            obs.path_to_id[path]      = idx
            G.add_node(idx, note=note)

        # ── 2. Semantic edges (CLAP cosine similarity) ────────────────────────
        H      = snap.H.to(self._device)   # (N, D)
        H_norm = torch.nn.functional.normalize(H, dim=-1)
        sims   = (H_norm @ H_norm.T).cpu()  # (N, N)

        sem_count = 0
        for i in range(N):
            for j in range(i + 1, N):
                s = float(sims[i, j])
                if s >= self._sim_threshold:
                    G.add_edge(i, j, edge_type="semantic",
                               edge_type_id=EDGE_TYPES["semantic"],
                               weight=round(s * 0.8, 4))
                    sem_count += 1

        # ── 3. Wikilink edges (Camelot harmonic compatibility) ─────────────────
        harm_count = 0
        camelot_list: List[str] = []
        for path in paths:
            ann = self._library.annotations.get(path, {})
            camelot_list.append(ann.get("key_camelot", "") or "")

        for i in range(N):
            for j in range(i + 1, N):
                if camelot_list[i] and camelot_list[j]:
                    if camelot_compatible(camelot_list[i], camelot_list[j]):
                        if not G.has_edge(i, j):
                            G.add_edge(i, j, edge_type="wikilink",
                                       edge_type_id=EDGE_TYPES["wikilink"],
                                       weight=1.0)
                        harm_count += 1

        # ── 4. Temporal edges (BPM proximity) ─────────────────────────────────
        bpm_list: List[Optional[float]] = []
        for path in paths:
            ann  = self._library.annotations.get(path, {})
            meta = self._library.meta_cache.get(path, {})
            raw  = ann.get("bpm") or meta.get("bpm")
            try:
                bpm_list.append(float(raw))
            except (TypeError, ValueError):
                bpm_list.append(None)

        bpm_count = 0
        for i in range(N):
            bi = bpm_list[i]
            if bi is None:
                continue
            for j in range(i + 1, N):
                bj = bpm_list[j]
                if bj is None:
                    continue
                diff = abs(bi - bj)
                if diff < self._bpm_window:
                    if not G.has_edge(i, j):
                        w = 1.0 - diff / self._bpm_window
                        G.add_edge(i, j, edge_type="temporal",
                                   edge_type_id=EDGE_TYPES["temporal"],
                                   weight=round(w * 0.4, 4))
                    bpm_count += 1

        # ── 5. Tag-overlap edges (shared mood / genre / era tags) ──────────────
        tag_lists: List[Set[str]] = []
        for path in paths:
            tag_lists.append(set(self._collect_tags(self._library.annotations.get(path, {}))))

        _UBIQUITOUS = {"vocal", "instrumental"}
        tag_count = 0
        for i in range(N):
            ti = tag_lists[i] - _UBIQUITOUS
            if not ti:
                continue
            for j in range(i + 1, N):
                tj = tag_lists[j] - _UBIQUITOUS
                if not tj:
                    continue
                overlap = ti & tj
                if overlap and not G.has_edge(i, j):
                    w = len(overlap) / max(len(ti), len(tj))
                    G.add_edge(i, j, edge_type="tag_overlap",
                               edge_type_id=EDGE_TYPES["tag_overlap"],
                               weight=round(w * 0.6, 4))
                    tag_count += 1

        logger.info(
            "PhiGraphBuilder: %d nodes  sem=%d harm=%d bpm=%d tag=%d edges",
            N, sem_count, harm_count, bpm_count, tag_count,
        )

        # ── 6. Wrap in TopologicalGraph ────────────────────────────────────────
        topo = TopologicalGraph(obs)
        topo.build()
        return topo

    # ── helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _collect_tags(ann: dict) -> List[str]:
        """Extract a flat list of music tags from Phi annotations."""
        tags: List[str] = []
        for key in ("mood", "genre", "phi_tags"):
            val = ann.get(key)
            if isinstance(val, str):
                tags.append(val.lower())
            elif isinstance(val, list):
                tags.extend(str(v).lower() for v in val)
        return tags
