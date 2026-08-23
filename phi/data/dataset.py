"""
PyTorch Dataset and batching utilities for SambaGNN training.

GraphBatch holds precomputed node embeddings + ordered neighborhood sequences
so that the GNN forward pass doesn't have to re-encode text every step.
"""
try:
    import torch
    from torch.utils.data import Dataset
    _TORCH_OK = True
except ImportError:
    torch = None  # type: ignore[assignment]
    Dataset = object  # type: ignore[assignment,misc]
    _TORCH_OK = False
from dataclasses import dataclass
from typing import List, Optional, Tuple

from .obsidian_graph import ObsidianGraph, EDGE_TYPES


@dataclass
class GraphBatch:
    """
    A full-graph batch (single graph, subgraph sampled for training).

    node_emb:        (N, hidden_dim) — pre-encoded node features
    neighbor_seqs:   (N, max_neighbors, hidden_dim) — ordered neighbor walks
    edge_type_ids:   (N, max_neighbors) — edge type per neighbor position
    neighbor_mask:   (N, max_neighbors) — True where neighbor exists
    pos_src:         (M,) — positive link src indices
    pos_dst:         (M,) — positive link dst indices
    neg_src:         (M,) — negative link src indices
    neg_dst:         (M,) — negative link dst indices
    hop_radius:      current curriculum hop depth
    """
    node_emb: torch.Tensor
    neighbor_seqs: torch.Tensor
    edge_type_ids: torch.LongTensor
    neighbor_mask: torch.BoolTensor
    pos_src: torch.LongTensor
    pos_dst: torch.LongTensor
    neg_src: torch.LongTensor
    neg_dst: torch.LongTensor
    hop_radius: int = 1

    def to(self, device: torch.device) -> "GraphBatch":
        return GraphBatch(
            node_emb=self.node_emb.to(device),
            neighbor_seqs=self.neighbor_seqs.to(device),
            edge_type_ids=self.edge_type_ids.to(device),
            neighbor_mask=self.neighbor_mask.to(device),
            pos_src=self.pos_src.to(device),
            pos_dst=self.pos_dst.to(device),
            neg_src=self.neg_src.to(device),
            neg_dst=self.neg_dst.to(device),
            hop_radius=self.hop_radius,
        )


class ObsidianGraphDataset(Dataset):
    """
    Dataset that wraps an ObsidianGraph and yields per-node training samples.

    Each sample is a node index. The collate function assembles GraphBatch.

    Supports curriculum learning: `set_hop_radius(k)` controls neighborhood
    depth used during training (start at 1, expand to max_hop over epochs).
    """

    def __init__(
        self,
        graph: ObsidianGraph,
        node_embeddings: torch.Tensor,  # (N, hidden_dim) — pre-encoded, cached
        walk_strategy: str = "recency",
        max_neighbors: int = 16,
        neg_samples_per_pos: int = 1,
        hop_radius: int = 1,
    ) -> None:
        self.graph = graph
        self.node_emb = node_embeddings
        self.walk_strategy = walk_strategy
        self.max_neighbors = max_neighbors
        self.neg_k = neg_samples_per_pos
        self.hop_radius = hop_radius

        self.N = graph.num_nodes
        self._build_neighbor_cache()
        self._build_link_pairs()

    def set_hop_radius(self, k: int) -> None:
        """Curriculum control — expand hop radius to include deeper neighborhoods."""
        self.hop_radius = k
        self._build_neighbor_cache()

    def _build_neighbor_cache(self) -> None:
        """Precompute ordered neighbor sequences for all nodes."""
        H = self.node_emb.size(1)
        M = self.max_neighbors

        self.neighbor_seqs = torch.zeros(self.N, M, H)
        self.edge_type_ids = torch.zeros(self.N, M, dtype=torch.long)
        self.neighbor_mask = torch.zeros(self.N, M, dtype=torch.bool)

        for node_id in range(self.N):
            neighbors = self.graph.get_ordered_neighbors(
                node_id,
                strategy=self.walk_strategy,
                max_neighbors=M,
            )
            for pos, (nbr_id, etype_id, weight) in enumerate(neighbors[:M]):
                if nbr_id < self.N:
                    self.neighbor_seqs[node_id, pos] = self.node_emb[nbr_id]
                    self.edge_type_ids[node_id, pos] = etype_id
                    self.neighbor_mask[node_id, pos] = True

    def _build_link_pairs(self) -> None:
        """Collect positive edge pairs and sample negatives."""
        G = self.graph.nx_graph
        edges = list(G.edges())
        if not edges:
            self.pos_pairs = torch.zeros(0, 2, dtype=torch.long)
        else:
            self.pos_pairs = torch.tensor(edges, dtype=torch.long)

    def _sample_negatives(self, pos_src: torch.Tensor, pos_dst: torch.Tensor) -> Tuple:
        """Random negative sampling (corrupt dst)."""
        neg_dst = torch.randint(0, self.N, pos_dst.shape)
        return pos_src, neg_dst

    def __len__(self) -> int:
        return max(1, len(self.pos_pairs))

    def __getitem__(self, idx: int):
        return idx  # node index; batch assembled in get_batch()

    def get_batch(self, hop_radius: Optional[int] = None) -> GraphBatch:
        """
        Returns a full GraphBatch for one training step.
        Uses all nodes (small graphs) or subsamples for large vaults.
        """
        if hop_radius is not None:
            self.set_hop_radius(hop_radius)

        pos_src = self.pos_pairs[:, 0] if len(self.pos_pairs) else torch.zeros(1, dtype=torch.long)
        pos_dst = self.pos_pairs[:, 1] if len(self.pos_pairs) else torch.zeros(1, dtype=torch.long)
        neg_src, neg_dst = self._sample_negatives(pos_src, pos_dst)

        return GraphBatch(
            node_emb=self.node_emb,
            neighbor_seqs=self.neighbor_seqs,
            edge_type_ids=self.edge_type_ids,
            neighbor_mask=self.neighbor_mask,
            pos_src=pos_src,
            pos_dst=pos_dst,
            neg_src=neg_src,
            neg_dst=neg_dst,
            hop_radius=self.hop_radius,
        )
