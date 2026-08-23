# -*- coding: utf-8 -*-
"""phi.models.bert_encoder — phi-local BERT clipping encoder with offline cache.

On first use the model is fetched from HuggingFace Hub and pinned to
~/.phi/bert_encoder/<model_slug>/.  Every subsequent load reads from disk —
no network calls, no Hub warnings.

Consumers inside phi always import from here.  The samba-gnn top-level
models/encoder.py is used only by the GNN training loop and is unaffected.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import List

log = logging.getLogger(__name__)

# ── local model store ─────────────────────────────────────────────────────────

_PHI_BERT_DIR = Path.home() / ".phi" / "bert_encoder"


def _model_slug(model_name: str) -> str:
    """Convert 'google/bert_uncased_L-2_H-128_A-2' → 'google--bert_uncased_L-2_H-128_A-2'."""
    return re.sub(r"[/\\]", "--", model_name)


def _local_path(model_name: str) -> Path:
    return _PHI_BERT_DIR / _model_slug(model_name)


def ensure_local(model_name: str) -> Path:
    """
    Return the local model directory, downloading from HuggingFace Hub
    if it does not exist yet.

    After the first successful download this function is a pure disk read —
    zero network I/O, zero Hub warnings.
    """
    local = _local_path(model_name)
    marker = local / ".download_complete"

    if marker.exists():
        return local  # fast path — already pinned locally

    log.info("bert_encoder: downloading %s → %s", model_name, local)
    local.mkdir(parents=True, exist_ok=True)
    try:
        from huggingface_hub import snapshot_download  # type: ignore[import]
        snapshot_download(
            repo_id=model_name,
            local_dir=str(local),
            local_dir_use_symlinks=False,
        )
    except Exception as exc:
        # snapshot_download failed (old huggingface_hub version or network error).
        # Fall back: download via transformers and save with save_pretrained().
        log.warning("snapshot_download failed (%s), falling back to save_pretrained", exc)
        from transformers import AutoModel, AutoTokenizer  # type: ignore[import]
        tok = AutoTokenizer.from_pretrained(model_name)
        mdl = AutoModel.from_pretrained(model_name)
        tok.save_pretrained(str(local))
        mdl.save_pretrained(str(local))

    marker.touch()
    log.info("bert_encoder: model pinned locally at %s", local)
    return local


# ── encoder class ─────────────────────────────────────────────────────────────

try:
    import torch
    import torch.nn as nn
    _TORCH_OK = True
except ImportError:
    torch = None  # type: ignore[assignment]
    nn = None     # type: ignore[assignment]
    _TORCH_OK = False


class BERTClippingEncoder(nn.Module if _TORCH_OK else object):  # type: ignore[misc]
    """
    Frozen tiny BERT with trainable linear projection head.

    Loads from ~/.phi/bert_encoder/<slug>/ (local-only after first download).
    Only the projection head is trainable.

    Args:
        model_name:  HuggingFace model ID (default: google/bert_uncased_L-2_H-128_A-2)
        clip_layers: transformer blocks to keep (default 2 — the full tiny model)
        output_dim:  GNN / clipper hidden dim to project into (default 256)
        max_length:  token budget per text (default 64)
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

        import transformers  # type: ignore[import]
        from transformers import AutoModel, AutoTokenizer  # type: ignore[import]

        local = ensure_local(model_name)

        # Suppress the UNEXPECTED-keys LOAD REPORT (MLM/NSP heads not used here),
        # the loading-weights progress bar, and any residual Hub warnings.
        _prev_level = transformers.logging.get_verbosity()
        transformers.logging.set_verbosity_error()
        transformers.logging.disable_progress_bar()
        try:
            # local_files_only=True → no network calls, no Hub warnings
            self.tokenizer = AutoTokenizer.from_pretrained(
                str(local), local_files_only=True
            )
            bert = AutoModel.from_pretrained(
                str(local), local_files_only=True
            )
        finally:
            transformers.logging.set_verbosity(_prev_level)
            transformers.logging.enable_progress_bar()
        bert.encoder.layer = bert.encoder.layer[:clip_layers]
        self.bert = bert

        for p in self.bert.parameters():
            p.requires_grad = False

        bert_hidden = bert.config.hidden_size
        self.proj = nn.Linear(bert_hidden, output_dim)
        self.norm = nn.LayerNorm(output_dim)

    def _encode_raw(self, texts: List[str], device: torch.device) -> torch.Tensor:
        with torch.no_grad():
            enc = self.tokenizer(
                texts,
                padding=True,
                truncation=True,
                max_length=self.max_length,
                return_tensors="pt",
            )
            enc = {k: v.to(device) for k, v in enc.items()}
            return self.bert(**enc).last_hidden_state[:, 0, :]

    def forward(self, texts: List[str], device: torch.device) -> torch.Tensor:
        """
        Args:
            texts:  list of N strings
            device: target device

        Returns:
            Tensor (N, output_dim) — trainable projection of [CLS] embeddings
        """
        cls = self._encode_raw(texts, device)
        return self.norm(self.proj(cls.to(device)))

    def encode_single(self, text: str, device: torch.device) -> torch.Tensor:
        return self.forward([text], device).squeeze(0)

    @staticmethod
    def trainable_params(model: "BERTClippingEncoder") -> int:
        return sum(p.numel() for p in model.parameters() if p.requires_grad)


__all__ = ["BERTClippingEncoder", "ensure_local"]
