"""
Encoder module for the Samba GNN.

Classes:
    BERTClippingEncoder   Frozen 2-layer BERT for prose / markdown text.
    CodeBERTEncoder       Frozen CodeBERT (clipped) for Python / JS symbols.
    DualEncoder           Routes SymbolNodes to the right encoder by language,
                          concatenates results in node_id order.

All encoders follow the same contract:
    forward(texts, device) -> Tensor(N, hidden_dim)

DualEncoder additionally accepts:
    forward_nodes(nodes, device) -> Tensor(N, hidden_dim)

The existing BERTClippingEncoder interface is unchanged — existing callers
(MCP tools, coherence engine) continue to work without modification.
"""
from __future__ import annotations

try:
    import torch
    import torch.nn as nn
    _TORCH_OK = True
except ImportError:
    torch = None  # type: ignore[assignment]
    nn = None     # type: ignore[assignment]
    _TORCH_OK = False

try:
    from transformers import AutoModel, AutoTokenizer
    _TRANSFORMERS_OK = True
except ImportError:
    AutoModel = None      # type: ignore[assignment]
    AutoTokenizer = None  # type: ignore[assignment]
    _TRANSFORMERS_OK = False

from typing import List, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from phi.data.symbol_node import SymbolNode

_CODE_LANGUAGES = {"python", "javascript", "typescript"}

_DEPS_OK = _TORCH_OK and _TRANSFORMERS_OK
_NNBase = nn.Module if _TORCH_OK else object
_no_grad = torch.no_grad if _TORCH_OK else (lambda f: f)


class BERTClippingEncoder(_NNBase):
    """
    Frozen BERT with layer clipping. Only the projection head is trainable.

    Uses google/bert_uncased_L-2_H-128_A-2 by default — a 2-layer, 128-dim
    BERT that is already a "clip" of bert-base-uncased from Google's
    Well-Read Students distillation work.

    Args:
        model_name:  HuggingFace model identifier
        clip_layers: how many transformer blocks to keep (from layer 0)
        output_dim:  GNN hidden dim to project into
        max_length:  token budget per note
    """

    def __init__(
        self,
        model_name: str = "google/bert_uncased_L-2_H-128_A-2",
        clip_layers: int = 2,
        output_dim: int = 256,
        max_length: int = 64,
    ) -> None:
        super().__init__()
        self.max_length = max_length

        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        bert = AutoModel.from_pretrained(model_name)

        # Clip: keep only the first `clip_layers` transformer blocks
        bert.encoder.layer = bert.encoder.layer[:clip_layers]

        self.bert = bert
        self._freeze_bert()

        bert_hidden = bert.config.hidden_size
        # Trainable projection into GNN space — the only params we own here
        self.proj = nn.Linear(bert_hidden, output_dim)
        self.norm = nn.LayerNorm(output_dim)

    def _freeze_bert(self) -> None:
        for param in self.bert.parameters():
            param.requires_grad = False

    @_no_grad
    def _encode_raw(self, texts: List[str], device: torch.device) -> torch.Tensor:
        """Run the frozen BERT and return [CLS] embeddings."""
        enc = self.tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=self.max_length,
            return_tensors="pt",
        )
        enc = {k: v.to(device) for k, v in enc.items()}
        out = self.bert(**enc)
        return out.last_hidden_state[:, 0, :]  # [CLS] token

    def forward(self, texts: List[str], device: torch.device) -> torch.Tensor:
        """
        Args:
            texts:  list of N note strings (title + body snippet)
            device: target device

        Returns:
            Tensor of shape (N, output_dim) — trainable projection of CLS embeddings
        """
        cls = self._encode_raw(texts, device)            # (N, bert_hidden) — frozen
        emb = self.norm(self.proj(cls.to(device)))       # (N, output_dim) — trainable
        return emb

    def encode_single(self, text: str, device: torch.device) -> torch.Tensor:
        return self.forward([text], device).squeeze(0)

    @staticmethod
    def trainable_params(model: "BERTClippingEncoder") -> int:
        return sum(p.numel() for p in model.parameters() if p.requires_grad)


class CodeBERTEncoder(_NNBase):
    """
    Frozen CodeBERT with layer clipping, projected to GNN hidden dim.

    Uses microsoft/codebert-base (12-layer, 768-dim) clipped to `clip_layers`
    transformer blocks — same pattern as BERTClippingEncoder. Only the
    linear projection head is trainable.

    Args:
        model_name:  HuggingFace model identifier (default: codebert-base)
        clip_layers: how many transformer blocks to keep (default 2)
        output_dim:  GNN hidden dim to project into
        max_length:  token budget per symbol (default 128 — code is denser)
    """

    def __init__(
        self,
        model_name: str = "microsoft/codebert-base",
        clip_layers: int = 2,
        output_dim: int = 256,
        max_length: int = 128,
    ) -> None:
        super().__init__()
        self.max_length = max_length

        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        bert = AutoModel.from_pretrained(model_name)
        bert.encoder.layer = bert.encoder.layer[:clip_layers]
        self.bert = bert
        self._freeze_bert()

        bert_hidden = bert.config.hidden_size
        self.proj = nn.Linear(bert_hidden, output_dim)
        self.norm = nn.LayerNorm(output_dim)

    def _freeze_bert(self) -> None:
        for param in self.bert.parameters():
            param.requires_grad = False

    @_no_grad
    def _encode_raw(self, texts: List[str], device: torch.device) -> torch.Tensor:
        enc = self.tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=self.max_length,
            return_tensors="pt",
        )
        enc = {k: v.to(device) for k, v in enc.items()}
        out = self.bert(**enc)
        return out.last_hidden_state[:, 0, :]

    def forward(self, texts: List[str], device: torch.device) -> torch.Tensor:
        """
        Args:
            texts:  list of N symbol strings (language hint + signature + body)
            device: target device

        Returns:
            Tensor of shape (N, output_dim)
        """
        cls = self._encode_raw(texts, device)
        return self.norm(self.proj(cls.to(device)))

    def encode_single(self, text: str, device: torch.device) -> torch.Tensor:
        return self.forward([text], device).squeeze(0)

    @staticmethod
    def trainable_params(model: "CodeBERTEncoder") -> int:
        return sum(p.numel() for p in model.parameters() if p.requires_grad)


class DualEncoder(_NNBase):
    """
    Routes SymbolNodes to the appropriate encoder by language, then
    reassembles results in original node_id order.

    Code symbols (python, javascript, typescript) → code_encoder
    Everything else (markdown, yaml, json, unknown) → text_encoder

    If code_encoder is None, all nodes are routed to text_encoder.

    Args:
        text_encoder:  BERTClippingEncoder instance (required)
        code_encoder:  CodeBERTEncoder instance (optional — omit to use text for all)
    """

    def __init__(
        self,
        text_encoder: BERTClippingEncoder,
        code_encoder: Optional[CodeBERTEncoder] = None,
    ) -> None:
        super().__init__()
        self.text_encoder = text_encoder
        self.code_encoder = code_encoder

    def forward(self, texts: List[str], device: torch.device) -> torch.Tensor:
        """Encode a plain list of strings — all routed to text_encoder."""
        return self.text_encoder(texts, device)

    def forward_nodes(
        self,
        nodes: List["SymbolNode"],
        device: torch.device,
    ) -> torch.Tensor:
        """
        Encode a list of SymbolNodes, routing by language.

        Returns:
            Tensor of shape (N, hidden_dim) in the same order as `nodes`.
        """
        if self.code_encoder is None:
            texts = [n.encoding_text for n in nodes]
            return self.text_encoder(texts, device)

        # Partition by language
        text_indices, code_indices = [], []
        for i, node in enumerate(nodes):
            if node.language in _CODE_LANGUAGES:
                code_indices.append(i)
            else:
                text_indices.append(i)

        N = len(nodes)
        hidden_dim = self.text_encoder.proj.out_features
        out = torch.zeros(N, hidden_dim, device=device)

        if text_indices:
            texts = [nodes[i].encoding_text for i in text_indices]
            embs = self.text_encoder(texts, device)
            for local_i, global_i in enumerate(text_indices):
                out[global_i] = embs[local_i]

        if code_indices:
            texts = [nodes[i].encoding_text for i in code_indices]
            embs = self.code_encoder(texts, device)
            for local_i, global_i in enumerate(code_indices):
                out[global_i] = embs[local_i]

        return out

    @staticmethod
    def trainable_params(model: "DualEncoder") -> int:
        return sum(p.numel() for p in model.parameters() if p.requires_grad)
