"""
SambaGNN — Full model orchestrating Obsidian knowledge graph.

Architecture overview:
    [Note text] → BERTClippingEncoder (frozen) → proj → (N, 256)
                                                          ↓
                                  EulerWalkPositionEncoder (e^ikω rotations, 0 params)
                                                          ↓
                                  SambaSSMLayer × 3  (shared EulerSSM weights)
                                      EulerSSM: r·e^iθ eigenvalues, oscillatory memory
                                                          ↓
                                  CoherenceLayer  (5 negative-e terms incl. χ=V-E+T)
                                                          ↓
                                  Task heads: link | retrieval | cluster

Parameter budget (d_model=256, d_state=64, d_conv=4, 3 layers shared EulerSSM):
    BERTClippingEncoder projection:     ~33K  (trainable)
    Shared EulerSSM (Euler complex):   ~249K  (same count as SelectiveSSM — drop-in)
    EulerWalkPositionEncoder:              0  (fixed frequency buffers)
    SambaSSMLayer × 3 (excl. SSM):    ~600K  (FF + norms + edge gates × 3)
    CoherenceLayer + χ term:               0  (pure formulas, buffers only)
    Task heads:                        ~100K
    ─────────────────────────────────────────
    Total trainable:                  ~982K   ← well under 1.65M, budget unchanged
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
from typing import Dict, List, Optional, Tuple

from .encoder import BERTClippingEncoder
from .euler_ssm import EulerSSM
from .euler_pos import EulerWalkPositionEncoder
from .samba_layer import SambaSSMLayer
from .heads import LinkPredictionHead, NodeRetrievalHead, ClusterHead
from .coherence import CoherenceLayer, CoherenceWeightSchedule


class SambaGNN(nn.Module):
    """
    Args:
        encoder_model:   HuggingFace model name for BERT clippings
        clip_layers:     how many BERT layers to use
        hidden_dim:      GNN hidden dimension
        num_layers:      number of Samba GNN layers
        d_state:         SSM state dimension
        d_conv:          SSM depthwise conv kernel size
        edge_dim:        edge feature embedding dimension
        num_edge_types:  number of discrete edge types
        num_clusters:    cluster head output size
        dropout:         dropout rate
        share_weights:   if True, all GNN layers share the same SSM (roving weights)
        max_length:      BERT max token length
        max_neighbors:   max neighborhood walk length
    """

    def __init__(
        self,
        encoder_model: str = "google/bert_uncased_L-2_H-128_A-2",
        clip_layers: int = 2,
        hidden_dim: int = 256,
        num_layers: int = 3,
        d_state: int = 64,
        d_conv: int = 4,
        edge_dim: int = 32,
        num_edge_types: int = 4,
        num_clusters: int = 16,
        dropout: float = 0.1,
        share_weights: bool = True,
        max_length: int = 64,
        max_neighbors: int = 16,
    ) -> None:
        super().__init__()
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        self.max_neighbors = max_neighbors

        # ── Encoder (frozen BERT + trainable projection) ──────────────────────
        self.encoder = BERTClippingEncoder(
            model_name=encoder_model,
            clip_layers=clip_layers,
            output_dim=hidden_dim,
            max_length=max_length,
        )

        # ── Edge feature embedding ─────────────────────────────────────────────
        self.edge_emb = nn.Embedding(num_edge_types, edge_dim)

        # ── Roving Euler SSM weights ───────────────────────────────────────────
        # One EulerSSM instance with complex Euler eigenvalues (r·e^iθ).
        # Shared across all GNN layers — the same oscillatory dynamics rove
        # the entire graph depth, encoding different note-recurrence timescales.
        shared_ssm = EulerSSM(d_model=hidden_dim, d_state=d_state, d_conv=d_conv)

        self.gnn_layers = nn.ModuleList()
        for _ in range(num_layers):
            ssm = shared_ssm if share_weights else EulerSSM(
                d_model=hidden_dim, d_state=d_state, d_conv=d_conv
            )
            self.gnn_layers.append(
                SambaSSMLayer(
                    hidden_dim=hidden_dim,
                    ssm=ssm,
                    edge_dim=edge_dim,
                    dropout=dropout,
                    max_seq_len=max_neighbors + 1,
                )
            )

        # ── Coherence layer (no trainable params — pure negative-e formulas) ──
        self.coherence = CoherenceLayer(
            alpha=0.10,    # negentropy
            beta=0.05,     # laplacian smoothness
            gamma=0.08,    # SSM Lyapunov stability
            delta=0.03,    # layer coherence KL
        )

        # ── Task heads ────────────────────────────────────────────────────────
        self.link_head = LinkPredictionHead(hidden_dim)
        self.retrieval_head = NodeRetrievalHead(hidden_dim)
        self.cluster_head = ClusterHead(hidden_dim, num_clusters)

    # ──────────────────────────────────────────────────────────────────────────
    # Core forward
    # ──────────────────────────────────────────────────────────────────────────

    def encode_nodes(
        self,
        texts: list,
        device: torch.device,
    ) -> torch.Tensor:
        """Encode a list of note texts → node embeddings (N, hidden_dim)."""
        return self.encoder(texts, device)

    def forward(
        self,
        node_emb: torch.Tensor,                   # (N, hidden_dim)
        neighbor_seqs: torch.Tensor,              # (N, max_neighbors, hidden_dim)
        edge_type_ids: torch.LongTensor,          # (N, max_neighbors)
        neighbor_mask: torch.Tensor,              # (N, max_neighbors) bool
        edge_index: Optional[torch.LongTensor] = None,  # (2, E) for coherence layer
        edge_weight: Optional[torch.Tensor] = None,     # (E,)
        return_coherence: bool = False,
    ) -> Tuple[torch.Tensor, Optional[Dict]]:
        """
        Run Samba GNN layers + coherence layer.

        Args:
            return_coherence: if True, also compute and return coherence energy + terms

        Returns:
            h:             (N, hidden_dim) — final node representations
            coh_info:      dict with E_coh tensor and per-term floats (if return_coherence)
                           else None
        """
        # Clamp edge_type_ids so graphs with more types than the embedding was
        # trained on (e.g. UnifiedGraph's 7 types vs a 4-type checkpoint) don't
        # cause an out-of-range IndexError.  Unknown types map to the last slot.
        edge_type_ids = edge_type_ids.clamp(max=self.edge_emb.num_embeddings - 1)
        edge_feats = self.edge_emb(edge_type_ids)   # (N, max_neighbors, edge_dim)

        h = node_emb
        h_layers: List[torch.Tensor] = []
        for layer in self.gnn_layers:
            h = layer(h, neighbor_seqs, edge_feats, neighbor_mask)
            h_layers.append(h)

        coh_info = None
        if return_coherence and edge_index is not None:
            ssm = self.gnn_layers[0].ssm
            # EulerSSM uses r_log + theta instead of A_log.
            # Lyapunov term checks r_log directly; pass it as A_log placeholder.
            dummy_dt = torch.ones(1, 1, self.hidden_dim, device=h.device) * 0.01
            E_coh, terms = self.coherence(
                h_layers=h_layers,
                A_log=ssm.r_log,
                dt=dummy_dt,
                edge_index=edge_index,
                edge_weight=edge_weight,
            )
            coh_info = {"E_coh": E_coh, "terms": terms}

        return h, coh_info

    # ──────────────────────────────────────────────────────────────────────────
    # Task-specific inference helpers
    # ──────────────────────────────────────────────────────────────────────────

    def predict_links(
        self,
        h: torch.Tensor,
        src_idx: torch.LongTensor,
        dst_idx: torch.LongTensor,
    ) -> torch.Tensor:
        """Pairwise link probability for (src, dst) index pairs. Returns (M,) logits."""
        return self.link_head(h[src_idx], h[dst_idx])

    def retrieve(
        self,
        h: torch.Tensor,
        query_idx: int,
        top_k: int = 10,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Retrieve top-k nearest notes. Returns (scores, indices) sorted descending."""
        q = self.retrieval_head(h[query_idx].unsqueeze(0))
        keys = self.retrieval_head(h)
        scores = (q @ keys.T).squeeze(0)
        top = torch.topk(scores, k=min(top_k, h.size(0)))
        return top.values, top.indices

    def cluster(self, h: torch.Tensor) -> torch.Tensor:
        """Soft cluster assignment. Returns (N, num_clusters) probabilities."""
        return self.cluster_head(h)

    def set_coherence_weights(self, weights: Dict[str, float]) -> None:
        """Delegate to CoherenceLayer — called by CoherenceWeightSchedule each step."""
        self.coherence.set_weights(weights)

    def euler_eigenvalue_report(self) -> dict:
        """
        Inspect the learned Euler eigenvalues (r, θ) of the shared EulerSSM.
        Shows what oscillation frequencies and decay rates the model has learned.
        """
        return self.gnn_layers[0].ssm.eigenvalue_summary()

    # ──────────────────────────────────────────────────────────────────────────
    # Parameter accounting
    # ──────────────────────────────────────────────────────────────────────────

    def parameter_report(self) -> Dict[str, int]:
        def count(m):
            return sum(p.numel() for p in m.parameters() if p.requires_grad)

        report = {
            "encoder_proj": count(self.encoder.proj) + count(self.encoder.norm),
            "edge_embedding": count(self.edge_emb),
            "ssm_shared": count(self.gnn_layers[0].ssm),
            "gnn_layers_excl_ssm": sum(
                count(l.norm1) + count(l.norm2) + count(l.edge_gate) + count(l.ff)
                for l in self.gnn_layers
            ),
            "link_head": count(self.link_head),
            "retrieval_head": count(self.retrieval_head),
            "cluster_head": count(self.cluster_head),
        }
        report["total_trainable"] = sum(p.numel() for p in self.parameters() if p.requires_grad)
        return report

# Related: ssm_lyapunov_loss, ceb_2, negentropy_loss,
#          MetaEmbedder._embed_librosa, euler_characteristic_loss
