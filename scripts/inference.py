"""
SambaGNN Inference Interface
Provides a clean API for Obsidian graph orchestration tasks:
  - find_related(note_title, top_k)  → ranked list of related notes
  - suggest_links(note_title)        → notes that should be linked but aren't
  - get_clusters()                   → topic clusters across the vault
  - route_query(query_text, top_k)   → find most relevant notes for a query

When config.yaml includes a [crawler] section, the orchestrator builds from
the full filesystem UnifiedGraph (all repos + notes on ~/), gates symbols via
AutonomousGate, and falls back to the ObsidianGraph vault only when no crawler
config is present.  All public API methods work identically in both modes.
"""
import os
import logging
import time
from typing import Dict, List, Optional, Tuple

import torch
import yaml

from phi.gnn.samba_gnn import SambaGNN
from phi.data.obsidian_graph import ObsidianGraph
from phi.data.unified_graph import UnifiedGraph
from phi.data.crawler import FilesystemCrawler
from phi.data.dataset import ObsidianGraphDataset
from engine.coherence_gate import AutonomousGate, GateAction
from phi.topology import TopologicalGraph

logger = logging.getLogger(__name__)


class SambaOrchestrator:
    """
    High-level inference wrapper for the Obsidian knowledge graph.
    Loads a trained SambaGNN checkpoint and exposes graph orchestration APIs.
    """

    def __init__(
        self,
        checkpoint_path: str,
        config_path: str = "config/config.yaml",
        device: Optional[torch.device] = None,
        lazy_embed: bool = False,
    ) -> None:
        """
        Args:
            lazy_embed: if True, skip _build_representations() at init. H will be
                        None until refresh() or node_embeddings(fast=True) is called.
                        Use this when only BERT-level embeddings are needed (e.g.
                        OctopusTracer soft_edge_mode).
        """
        self.device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")

        with open(config_path) as f:
            self.cfg = yaml.safe_load(f)

        enc = self.cfg["model"]["encoder"]
        gnn = self.cfg["model"]["gnn"]
        ssm = self.cfg["model"]["ssm"]

        # ── Graph source: unified filesystem (preferred) or Obsidian vault ────
        self._crawler: Optional[FilesystemCrawler] = None
        self._gate: Optional[AutonomousGate] = None
        self._use_unified: bool = "crawler" in self.cfg

        if self._use_unified:
            self._crawler = FilesystemCrawler(self.cfg["crawler"])
            self._gate = AutonomousGate(
                cfg=self.cfg.get("gate", {}),
                log_path=self.cfg.get("gate", {}).get("log_path", "logs/gate.db"),
            )
            self.graph: UnifiedGraph = self._build_unified_graph()
        else:
            vault_path = (
                os.environ.get("OBSIDIAN_VAULT_PATH")
                or self.cfg.get("graph", {}).get("vault_path", "")
            )
            self.graph = ObsidianGraph(
                vault_path=vault_path or None,
                semantic_threshold=self.cfg["edges"]["semantic_threshold"],
            )
            self.graph.build()

        # Topology primitive layer — rebuilt on every refresh()
        self.topo = TopologicalGraph(self.graph)
        if not lazy_embed:
            self.topo.build()

        # ── Model ─────────────────────────────────────────────────────────────
        self.model = SambaGNN(
            encoder_model=enc["model_name"],
            clip_layers=enc["clip_layers"],
            hidden_dim=gnn["hidden_dim"],
            num_layers=gnn["num_layers"],
            d_state=ssm["d_state"],
            d_conv=ssm["d_conv"],
            share_weights=gnn["share_weights"],
            num_edge_types=gnn.get("num_edge_types", 7),
            num_clusters=self.cfg["model"]["heads"]["num_clusters"],
            max_neighbors=self.cfg["walk"]["max_neighbors"],
        ).to(self.device)

        ckpt = torch.load(checkpoint_path, map_location=self.device)
        # Filter shape-mismatched keys before loading so old checkpoints (e.g. 4
        # edge types vs current 7) don't raise even under strict=False.
        ckpt_sd   = ckpt["model_state_dict"]
        model_sd  = self.model.state_dict()
        compatible = {
            k: v for k, v in ckpt_sd.items()
            if k in model_sd and v.shape == model_sd[k].shape
        }
        skipped = [k for k in ckpt_sd if k not in compatible]
        if skipped:
            logger.debug("Skipped shape-mismatched checkpoint keys: %s", skipped)
        missing, unexpected = self.model.load_state_dict(compatible, strict=False)
        if missing:
            logger.debug("Checkpoint missing keys (ok for new edge types): %s", missing)
        self.model.eval()
        logger.info(f"Loaded checkpoint from {checkpoint_path}")

        self._h: Optional[torch.Tensor] = None
        self._last_crawl_ts: float = time.time()
        if not lazy_embed:
            self._build_representations()

    # ──────────────────────────────────────────────────────────────────────────
    # Graph construction helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _build_unified_graph(self) -> UnifiedGraph:
        """Full crawl + gate + UnifiedGraph build. Called at init and on full refresh."""
        assert self._crawler is not None and self._gate is not None
        symbols = self._crawler.scan()
        logger.info("Crawl: %d raw symbols", len(symbols))
        decisions = self._gate.evaluate_batch(symbols)
        admitted = [s for s, d in zip(symbols, decisions) if d.action == GateAction.ADMIT]
        logger.info(
            "Gate: %d admitted | %d deferred | %d skipped",
            len(admitted),
            sum(1 for d in decisions if d.action.value == "defer"),
            sum(1 for d in decisions if d.action.value == "skip"),
        )
        g = UnifiedGraph(semantic_threshold=self.cfg["edges"]["semantic_threshold"])
        g.build(admitted)
        self._gate.update_name_index(g._name_index)
        self._last_crawl_ts = time.time()
        logger.info("UnifiedGraph: %d nodes, %d edges", g.num_nodes, g.nx_graph.number_of_edges())
        return g

    def _rebuild_unified_incremental(self) -> None:
        """Incremental crawl since last scan — gate new symbols and merge into graph."""
        assert self._crawler is not None and self._gate is not None
        new_syms = self._crawler.scan_incremental(since_ts=self._last_crawl_ts)
        self._last_crawl_ts = time.time()
        if not new_syms:
            return
        decisions = self._gate.evaluate_batch(new_syms)
        admitted = [s for s, d in zip(new_syms, decisions) if d.action == GateAction.ADMIT]
        if not admitted:
            return
        all_syms = list(self.graph.notes.values()) + admitted
        self.graph.build(all_syms)
        self._gate.update_name_index(self.graph._name_index)
        logger.info(
            "Incremental refresh: +%d symbols → %d nodes total",
            len(admitted), self.graph.num_nodes,
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Representation building
    # ──────────────────────────────────────────────────────────────────────────

    @torch.no_grad()
    def _build_representations(self) -> None:
        """Encode all nodes and run GNN to build cached node representations."""
        texts = self.graph.all_texts
        if not texts:
            logger.warning("Graph is empty — skipping representation build")
            self._h = torch.zeros(0, self.model.hidden_dim, device=self.device)
            return
        node_emb = self.model.encode_nodes(texts, self.device)

        dataset = ObsidianGraphDataset(
            graph=self.graph,
            node_embeddings=node_emb.cpu(),
            walk_strategy=self.cfg["walk"]["strategy"],
            max_neighbors=self.cfg["walk"]["max_neighbors"],
        )
        batch = dataset.get_batch().to(self.device)

        self._h, _ = self.model(
            batch.node_emb, batch.neighbor_seqs, batch.edge_type_ids, batch.neighbor_mask
        )
        logger.info(f"Built representations for {self._h.size(0)} nodes")

    def refresh(self) -> None:
        """Re-encode after vault/filesystem changes. Rebuilds topology layer."""
        if self._use_unified:
            self._rebuild_unified_incremental()
        else:
            self.graph.build()
        self.topo.build()
        self._build_representations()

    @torch.no_grad()
    def node_embeddings(self, fast: bool = False) -> torch.Tensor:
        """
        Return current node representation tensor (N, hidden_dim).

        Args:
            fast: if True and GNN representations are not yet ready, fall back to
                  raw BERT [CLS] embeddings (no GNN pass). Useful for tracer first-
                  spawn before the slow full pipeline completes.

        Returns:
            H: (N, hidden_dim) on self.device
        """
        if self._h is not None and self._h.size(0) > 0:
            return self._h

        if fast:
            texts = self.graph.all_texts
            if not texts:
                return torch.zeros(0, self.model.hidden_dim, device=self.device)
            logger.info("node_embeddings: GNN cache empty — falling back to fast BERT encoding")
            return self.model.encode_nodes(texts, self.device)

        return torch.zeros(0, self.model.hidden_dim, device=self.device)

    # ──────────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────────

    def find_related(self, note_title: str, top_k: int = 10) -> List[Dict]:
        """
        Find top-k notes most related to the given note.

        Returns:
            List of {"title": str, "path": str, "score": float}
        """
        node_id = self._title_to_id(note_title)
        if node_id is None:
            return []

        scores, indices = self.model.retrieve(self._h, node_id, top_k + 1)
        results = []
        for score, idx in zip(scores.cpu().tolist(), indices.cpu().tolist()):
            if idx == node_id:
                continue
            note = self._id_to_note(idx)
            if note:
                results.append({"title": note.title, "path": note.path, "score": round(score, 4)})
        return results[:top_k]

    def suggest_links(self, note_title: str, top_k: int = 5) -> List[Dict]:
        """
        Suggest notes that are semantically close but not yet explicitly linked.
        These are "orphan link" candidates.
        """
        node_id = self._title_to_id(note_title)
        if node_id is None:
            return []

        existing_links = set(self.graph.nx_graph.successors(node_id))
        existing_links |= set(self.graph.nx_graph.predecessors(node_id))

        scores, indices = self.model.retrieve(self._h, node_id, top_k * 3)
        suggestions = []
        for score, idx in zip(scores.cpu().tolist(), indices.cpu().tolist()):
            if idx == node_id or idx in existing_links:
                continue
            note = self._id_to_note(idx)
            if note:
                suggestions.append({
                    "title": note.title,
                    "path": note.path,
                    "score": round(score, 4),
                    "suggested_link": f"[[{note.title}]]",
                })
            if len(suggestions) >= top_k:
                break
        return suggestions

    def get_clusters(self) -> List[Dict]:
        """
        Return topic clusters across the vault.
        Each cluster contains its most representative notes.
        """
        with torch.no_grad():
            assignments = self.model.cluster(self._h)  # (N, K)

        K = assignments.size(1)
        clusters = []
        for k in range(K):
            cluster_scores = assignments[:, k]
            top_indices = torch.topk(cluster_scores, k=min(5, self._h.size(0))).indices
            notes = []
            for idx in top_indices.cpu().tolist():
                note = self._id_to_note(idx)
                if note:
                    notes.append({
                        "title": note.title,
                        "score": round(cluster_scores[idx].item(), 4)
                    })
            clusters.append({"cluster_id": k, "notes": notes})
        return clusters

    def topology_summary(self) -> Dict:
        """
        Return the current topological invariants of the knowledge graph.

        Includes χ (Euler characteristic), β₀ (connected components),
        β₁ (independent cycles), and per-type edge counts.
        Useful for MCP reporting and coherence monitoring.
        """
        return self.topo.snapshot()

    def graph_snapshot(self) -> Dict:
        """
        Return a lightweight graph metrics snapshot without triggering topo.build().
        Safe to call even when lazy_embed=True — only reads graph object properties.

        Suitable for feeding CAIRRN/TracerDaemon when full topology is too slow.
        """
        G = self.graph.nx_graph
        n_nodes = self.graph.num_nodes
        n_edges = G.number_of_edges() if G is not None else 0
        n_cc    = 0
        try:
            import networkx as nx
            n_cc = nx.number_weakly_connected_components(G) if G else 1
        except Exception:
            n_cc = 1
        return {
            "nodes":       n_nodes,
            "edges":       n_edges,
            "components":  n_cc,
            "density":     n_edges / max(n_nodes * (n_nodes - 1), 1),
            "euler_chi":   n_nodes - n_edges,   # triangles unknown — approx
        }

    def route_query(self, query_text: str, top_k: int = 5) -> List[Dict]:
        """
        Find most relevant notes for an arbitrary query string.
        Encodes the query via BERT clippings and retrieves in graph space.
        """
        with torch.no_grad():
            q_emb = self.model.encoder([query_text], self.device)     # (1, H)
            q_proj = self.model.retrieval_head(q_emb)                 # (1, proj_dim)
            keys = self.model.retrieval_head(self._h)                 # (N, proj_dim)
            scores = (q_proj @ keys.T).squeeze(0)                    # (N,)
        top = torch.topk(scores, k=min(top_k, self._h.size(0)))
        results = []
        for score, idx in zip(top.values.cpu().tolist(), top.indices.cpu().tolist()):
            note = self._id_to_note(idx)
            if note:
                results.append({"title": note.title, "path": note.path, "score": round(score, 4)})
        return results

    def node_index_map(self) -> Dict[int, Dict[str, str]]:
        """
        Return {node_id: {"title": str, "path": str}} for all nodes in the graph.

        Call once per cycle after refresh() — node IDs can shift when the graph
        is rebuilt.  Returns an empty dict when the graph has no notes attribute
        (e.g. during cold startup or UnifiedGraph mode without markdown notes).
        """
        result: Dict[int, Dict[str, str]] = {}
        try:
            for note in self.graph.notes.values():
                result[note.node_id] = {"title": note.title, "path": note.path}
        except AttributeError:
            logger.debug("node_index_map: graph has no .notes attribute — returning empty map")
        return result

    # ──────────────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _title_to_id(self, title: str) -> Optional[int]:
        title_lower = title.lower()
        for note in self.graph.notes.values():
            if note.title.lower() == title_lower:
                return note.node_id
        logger.warning(f"Note '{title}' not found in graph")
        return None

    def _id_to_note(self, node_id: int):
        for note in self.graph.notes.values():
            if note.node_id == node_id:
                return note
        return None


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("--task", choices=["related", "suggest_links", "clusters", "query"],
                        required=True)
    parser.add_argument("--note", help="Note title for related/suggest tasks")
    parser.add_argument("--query", help="Query text for route task")
    parser.add_argument("--top_k", type=int, default=5)
    args = parser.parse_args()

    orch = SambaOrchestrator(args.checkpoint, args.config)

    if args.task == "related":
        results = orch.find_related(args.note, args.top_k)
    elif args.task == "suggest_links":
        results = orch.suggest_links(args.note, args.top_k)
    elif args.task == "clusters":
        results = orch.get_clusters()
    elif args.task == "query":
        results = orch.route_query(args.query, args.top_k)

    print(json.dumps(results, indent=2))
