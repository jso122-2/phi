"""
ReplayBuffer for Perpetual Pretraining
Stores graph snapshots (node embeddings + edge topology) and mixes old
experience with new vault observations during perpetual training.

Design:
    - Ring buffer of fixed capacity (in snapshot slots)
    - Each slot = a GraphSnapshot (node_emb, edge_index, edge_weight, metadata)
    - Sampling strategy: recent-biased exponential decay so new notes
      are seen more often than old ones, but old structure is never forgotten
    - Priority queue within each slot for curriculum: harder examples sampled more

Two use cases:
    1. Pretraining on synthetic graphs — fill buffer with generated snapshots
    2. Live vault finetuning — add new snapshots when vault changes are detected
"""
import time
import math
import random
import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, List, Optional, Tuple

try:
    import torch
    _TORCH_OK = True
except ImportError:
    torch = None  # type: ignore[assignment]
    _TORCH_OK = False
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class GraphSnapshot:
    """One captured state of the knowledge graph for replay."""
    node_emb: torch.Tensor          # (N, hidden_dim) — frozen encoder output
    edge_index: torch.LongTensor    # (2, E)
    edge_weight: torch.Tensor       # (E,)
    neighbor_seqs: torch.Tensor     # (N, max_neighbors, hidden_dim)
    edge_type_ids: torch.LongTensor # (N, max_neighbors)
    neighbor_mask: torch.BoolTensor # (N, max_neighbors)
    timestamp: float = field(default_factory=time.time)
    source: str = "vault"           # "vault" | "synthetic" | "augmented"
    priority: float = 1.0           # higher = sampled more often

    def to(self, device: torch.device) -> "GraphSnapshot":
        return GraphSnapshot(
            node_emb=self.node_emb.to(device),
            edge_index=self.edge_index.to(device),
            edge_weight=self.edge_weight.to(device),
            neighbor_seqs=self.neighbor_seqs.to(device),
            edge_type_ids=self.edge_type_ids.to(device),
            neighbor_mask=self.neighbor_mask.to(device),
            timestamp=self.timestamp,
            source=self.source,
            priority=self.priority,
        )

    @property
    def num_nodes(self) -> int:
        return self.node_emb.size(0)

    @property
    def num_edges(self) -> int:
        return self.edge_index.size(1) if self.edge_index.numel() > 0 else 0


class ReplayBuffer:
    """
    Ring buffer of GraphSnapshots with recent-biased sampling.

    Sampling weight of slot i (age a_i seconds):
        w_i = priority_i · exp(-λ · a_i)

    where λ = recency_decay controls how quickly old snapshots lose weight.
    λ = 0 → uniform; λ → ∞ → always pick newest.

    Args:
        capacity:         max number of snapshots to retain
        recency_decay:    λ for exponential recency weighting (1/hours)
        min_vault_frac:   minimum fraction of each batch from "vault" source
    """

    def __init__(
        self,
        capacity: int = 64,
        recency_decay: float = 0.01,    # λ per second (0.01 = half-life ~70s)
        min_vault_frac: float = 0.5,
    ) -> None:
        self.capacity = capacity
        self.recency_decay = recency_decay
        self.min_vault_frac = min_vault_frac
        self._buffer: Deque[GraphSnapshot] = deque(maxlen=capacity)
        self._total_added = 0

    def add(self, snapshot: GraphSnapshot) -> None:
        self._buffer.append(snapshot)
        self._total_added += 1
        logger.debug(
            f"ReplayBuffer: added {snapshot.source} snapshot "
            f"({snapshot.num_nodes}N, {snapshot.num_edges}E) "
            f"[{len(self._buffer)}/{self.capacity}]"
        )

    def sample(self, n: int = 1) -> List[GraphSnapshot]:
        """
        Sample n snapshots with recent-biased weighting.
        Guarantees at least min_vault_frac of samples are from the vault.
        """
        if len(self._buffer) == 0:
            raise RuntimeError("ReplayBuffer is empty — add snapshots before sampling")

        buf = list(self._buffer)
        now = time.time()

        weights = np.array([
            s.priority * math.exp(-self.recency_decay * (now - s.timestamp))
            for s in buf
        ], dtype=np.float64)
        weights /= weights.sum()

        vault_indices = [i for i, s in enumerate(buf) if s.source == "vault"]
        other_indices = [i for i, s in enumerate(buf) if s.source != "vault"]

        min_vault = max(1, int(n * self.min_vault_frac)) if vault_indices else 0
        n_vault = min(min_vault, len(vault_indices))
        n_other = n - n_vault

        chosen = []
        if n_vault > 0 and vault_indices:
            v_weights = weights[vault_indices]
            v_weights = v_weights / v_weights.sum()
            v_choice = np.random.choice(vault_indices, size=n_vault, replace=True, p=v_weights)
            chosen.extend(v_choice.tolist())

        if n_other > 0:
            all_weights = weights / weights.sum()
            o_choice = np.random.choice(len(buf), size=n_other, replace=True, p=all_weights)
            chosen.extend(o_choice.tolist())

        return [buf[i] for i in chosen]

    def update_priority(self, source: str, delta: float) -> None:
        """Increase priority of snapshots from a given source (e.g. after loss spike)."""
        for s in self._buffer:
            if s.source == source:
                s.priority = max(0.1, s.priority + delta)

    def __len__(self) -> int:
        return len(self._buffer)

    @property
    def vault_count(self) -> int:
        return sum(1 for s in self._buffer if s.source == "vault")

    @property
    def synthetic_count(self) -> int:
        return sum(1 for s in self._buffer if s.source == "synthetic")


# ──────────────────────────────────────────────────────────────────────────────
# Synthetic graph generator (for pretraining without a vault)
# ──────────────────────────────────────────────────────────────────────────────

def generate_synthetic_snapshot(
    num_nodes: int = 32,
    num_edges: int = 64,
    hidden_dim: int = 256,
    max_neighbors: int = 16,
    num_edge_types: int = 4,
) -> GraphSnapshot:
    """
    Generate a random GraphSnapshot for pretraining when vault is unavailable.
    Draws from a mixture of Barabási-Albert (hub structure) and Erdős-Rényi graphs.
    """
    import networkx as nx

    # alternate between BA (scale-free, like real wikis) and ER
    if random.random() < 0.6:
        G = nx.barabasi_albert_graph(num_nodes, m=min(3, num_nodes - 1))
    else:
        p = num_edges / (num_nodes * (num_nodes - 1) / 2 + 1e-8)
        G = nx.erdos_renyi_graph(num_nodes, p=min(p, 0.5))

    edges = list(G.edges())
    if not edges:
        edges = [(0, 1)]

    src = torch.tensor([e[0] for e in edges], dtype=torch.long)
    dst = torch.tensor([e[1] for e in edges], dtype=torch.long)
    edge_index = torch.stack([src, dst], dim=0)
    edge_weight = torch.rand(len(edges))
    edge_type_ids_flat = torch.randint(0, num_edge_types, (len(edges),))

    node_emb = torch.randn(num_nodes, hidden_dim) * 0.1
    N, M, H = num_nodes, max_neighbors, hidden_dim
    neighbor_seqs = torch.zeros(N, M, H)
    n_edge_type_ids = torch.zeros(N, M, dtype=torch.long)
    neighbor_mask = torch.zeros(N, M, dtype=torch.bool)

    adj = {i: [] for i in range(num_nodes)}
    for (u, v), et in zip(edges, edge_type_ids_flat.tolist()):
        adj[u].append((v, et))
        adj[v].append((u, et))

    for node in range(num_nodes):
        nbrs = adj[node][:M]
        for pos, (nbr, et) in enumerate(nbrs):
            neighbor_seqs[node, pos] = node_emb[nbr]
            n_edge_type_ids[node, pos] = et
            neighbor_mask[node, pos] = True

    return GraphSnapshot(
        node_emb=node_emb,
        edge_index=edge_index,
        edge_weight=edge_weight,
        neighbor_seqs=neighbor_seqs,
        edge_type_ids=n_edge_type_ids,
        neighbor_mask=neighbor_mask,
        source="synthetic",
    )


def prefill_buffer_synthetic(
    buffer: ReplayBuffer,
    n_snapshots: int = 16,
    **kwargs,
) -> None:
    """Fill a ReplayBuffer with synthetic snapshots for cold-start pretraining."""
    for i in range(n_snapshots):
        snap = generate_synthetic_snapshot(**kwargs)
        snap.priority = 0.5   # lower priority than real vault data
        buffer.add(snap)
    logger.info(f"Prefilled ReplayBuffer with {n_snapshots} synthetic snapshots")
