# -*- coding: utf-8 -*-
"""phi.meta._meta_embedder — three-tier track embedding for OctopusOrganizer.

Builds the (N, d_model) matrix H that OctopusTracer ingests:

  Tier 1  CLAP audio vector (512-d) → CLAPProjection → 256-d  (rich)
  Tier 2  librosa features (19-d)   → fixed random projection   (sparse)
  Tier 3  stable random vector      → seeded by path hash        (cold)

Tiers 2/3 are informationally thin; the tracer's sprout arm correctly flags
these tracks as graph-isolated, pushing them to the front of the enrich queue.
"""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING

try:
    import torch
    import torch.nn.functional as F
    _TORCH_OK = True
except ImportError:
    torch = None  # type: ignore[assignment]
    F = None      # type: ignore[assignment]
    _TORCH_OK = False

if TYPE_CHECKING:
    from phi.core.library import Library
    from phi.models.clap_proj import CLAPProjection

logger = logging.getLogger(__name__)

# Cold-start projection constants
_COLD_DIM       = 19       # BPM(1) + key_idx(1) + rms(1) + centroid(1) + zcr(1)
                            # + energy(1) + mfcc_mean(13)
_COLD_PROJ_SEED = 0xDA14C01D


class MetaEmbedder:
    """Builds the (N, d_model) embedding matrix H for OctopusTracer ingestion.

    Args:
        d_model    : output embedding dimension (must match tracer.d_model)
        device     : torch device for all tensors
        meta_store : path to ``~/.phi/meta_store.jsonl`` for librosa features

    Raises: nothing — missing data degrades silently to a lower tier.
    """

    def __init__(
        self,
        d_model:    int                    = 256,
        device:     Optional[torch.device] = None,
        meta_store: Optional[Path]         = None,
    ) -> None:
        self.d_model    = d_model
        self.device     = device or torch.device("cpu")
        self.meta_store = meta_store or (Path.home() / ".phi" / "meta_store.jsonl")

        gen = torch.Generator()
        gen.manual_seed(_COLD_PROJ_SEED)
        proj = torch.randn(_COLD_DIM, d_model, generator=gen)
        self._cold_proj: torch.Tensor = F.normalize(proj, dim=0)

        self._librosa_store: Dict[str, dict] = {}

    def load_librosa_store(self) -> None:
        """Load meta_store.jsonl into memory for cold-start embedding."""
        if not self.meta_store.exists():
            return
        with self.meta_store.open() as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    self._librosa_store[rec["path"]] = rec
                except Exception:
                    pass
        logger.debug("MetaEmbedder: loaded %d librosa records", len(self._librosa_store))

    def embed(
        self,
        library:    "Library",
        projection: Optional["CLAPProjection"] = None,
    ) -> Tuple[torch.Tensor, List[str], Dict[str, str]]:
        """Build H for all tracks in library using the best available tier.

        Returns:
            H        (N, d_model) tensor — row i corresponds to paths[i]
            paths    list of N track paths
            sources  {path: "clap" | "librosa" | "random"}
        """
        if not self._librosa_store:
            self.load_librosa_store()

        vecs:    List[torch.Tensor] = []
        paths:   List[str]          = []
        sources: Dict[str, str]     = {}

        for path in library.playlist:
            ann = library.annotations.get(path, {})
            vec = ann.get("genre_vec") or ann.get("mood_vec")

            if vec and projection is not None and len(vec) == projection.d_clap:
                import numpy as _np
                arr  = _np.asarray(vec, dtype=_np.float64).reshape(1, -1)
                h_np = projection.forward(arr)[0]          # (d_model,) numpy
                h    = torch.tensor(h_np, dtype=torch.float32)
                source = "clap"
            elif path in self._librosa_store:
                h      = self._embed_librosa(self._librosa_store[path])
                source = "librosa"
            else:
                h      = self._embed_random(path)
                source = "random"

            vecs.append(h.to(self.device))
            paths.append(path)
            sources[path] = source

        if not vecs:
            return torch.zeros(0, self.d_model, device=self.device), [], {}

        H = torch.stack(vecs, dim=0)
        logger.debug(
            "MetaEmbedder: built H %s  clap=%d  librosa=%d  random=%d",
            tuple(H.shape),
            sum(1 for s in sources.values() if s == "clap"),
            sum(1 for s in sources.values() if s == "librosa"),
            sum(1 for s in sources.values() if s == "random"),
        )
        return H, paths, sources

    # ── Tier 2: librosa cold-start ────────────────────────────────────────────

    def _embed_librosa(self, rec: dict) -> torch.Tensor:
        """Project a 19-d librosa feature vector to d_model via fixed random matrix."""
        bpm      = min(float(rec.get("bpm",              120.0)), 200.0) / 200.0
        key_idx  = float(rec.get("key_idx",                  0))  / 11.0
        rms      = min(float(rec.get("loudness_rms",      0.05)), 0.15) / 0.15
        centroid = min(float(rec.get("spectral_cent",   2000.0)), 8000.0) / 8000.0
        zcr      = min(float(rec.get("zcr",              0.05)), 0.20) / 0.20
        energy   = float(rec.get("energy_heuristic",     0.50))

        mfcc = rec.get("mfcc_mean") or ([0.0] * 13)
        mfcc_norm = [min(max(v / 50.0, -1.0), 1.0) for v in mfcc[:13]]
        while len(mfcc_norm) < 13:
            mfcc_norm.append(0.0)

        feat = torch.tensor(
            [bpm, key_idx, rms, centroid, zcr, energy] + mfcc_norm,
            dtype=torch.float32,
        )
        h = feat @ self._cold_proj.to(feat.device)
        return F.normalize(h, dim=0)

    # ── Tier 3: stable random ─────────────────────────────────────────────────

    def _embed_random(self, path: str) -> torch.Tensor:
        """Return a deterministic d_model-dimensional unit vector seeded by path hash."""
        seed = int(hashlib.md5(path.encode()).hexdigest()[:8], 16)
        gen  = torch.Generator()
        gen.manual_seed(seed)
        return F.normalize(torch.randn(self.d_model, generator=gen), dim=0)
