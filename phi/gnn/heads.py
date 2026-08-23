"""
Task heads for SambaGNN.
All lightweight — collective budget kept under ~120K params.
"""
try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    _TORCH_OK = True
except ImportError:
    torch = None  # type: ignore[assignment]
    nn = None     # type: ignore[assignment]
    F = None      # type: ignore[assignment]
    _TORCH_OK = False


class LinkPredictionHead(nn.Module):
    """
    Bilinear + MLP link scorer.
    Given embeddings for src and dst nodes, returns a link existence logit.
    Designed for both positive/negative link prediction and orphan detection.
    """

    def __init__(self, hidden_dim: int) -> None:
        super().__init__()
        self.mlp = nn.Sequential(
            nn.Linear(hidden_dim * 2, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.GELU(),
            nn.Linear(hidden_dim // 2, 1),
        )

    def forward(self, h_src: torch.Tensor, h_dst: torch.Tensor) -> torch.Tensor:
        """
        Args:
            h_src: (M, hidden_dim)
            h_dst: (M, hidden_dim)

        Returns:
            logits: (M,)
        """
        pair = torch.cat([h_src, h_dst], dim=-1)   # (M, 2*H)
        return self.mlp(pair).squeeze(-1)


class NodeRetrievalHead(nn.Module):
    """
    Projects node embeddings into a retrieval space for cosine similarity search.
    Used for "find notes like this" and query routing through the graph.
    """

    def __init__(self, hidden_dim: int, proj_dim: int = 128) -> None:
        super().__init__()
        self.proj = nn.Sequential(
            nn.Linear(hidden_dim, proj_dim),
            nn.LayerNorm(proj_dim),
        )

    def forward(self, h: torch.Tensor) -> torch.Tensor:
        """Returns L2-normalized projection for cosine similarity. Shape: (..., proj_dim)."""
        return F.normalize(self.proj(h), dim=-1)


class ClusterHead(nn.Module):
    """
    Soft cluster assignment head.
    Outputs a probability distribution over K clusters per node.
    Cluster centroids are learned and can be warm-started from k-means.
    """

    def __init__(self, hidden_dim: int, num_clusters: int = 16) -> None:
        super().__init__()
        self.num_clusters = num_clusters
        self.proj = nn.Linear(hidden_dim, num_clusters)
        # learnable cluster prototypes for auxiliary loss
        self.prototypes = nn.Parameter(torch.randn(num_clusters, hidden_dim))

    def forward(self, h: torch.Tensor) -> torch.Tensor:
        """Returns soft cluster probabilities. Shape: (N, num_clusters)."""
        return F.softmax(self.proj(h), dim=-1)

    def prototype_loss(self, h: torch.Tensor, assignments: torch.Tensor) -> torch.Tensor:
        """
        Auxiliary clustering loss: push node embeddings toward assigned prototypes.
        assignments: (N, num_clusters) soft from forward()
        """
        protos = F.normalize(self.prototypes, dim=-1)   # (K, H)
        h_norm = F.normalize(h, dim=-1)                  # (N, H)
        sim = h_norm @ protos.T                           # (N, K)
        # encourage high similarity to assigned cluster, low to others
        return -(assignments * sim).sum(dim=-1).mean()
