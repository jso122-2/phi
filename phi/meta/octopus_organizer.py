# -*- coding: utf-8 -*-
"""phi.meta.octopus_organizer — OctopusTracer-driven metadata organisation pipeline.

Run OctopusTracer *before* enrichment to decide:
  - Which tracks to enrich first (sprout + resurface signal)
  - Which tracks are probably corrupt / skip enrichment (prune signal)
  - Which near-duplicate pairs to surface for user review (merge arm)
  - What cluster a track belongs to (cluster arm)
  - What tags the model thinks a track should carry (tag arm)

Priority formula::

    enrich_priority = sprout × (1 − prune) + resurface × 0.30

Usage::

    from phi.meta.octopus_organizer import OctopusOrganizer, make_organizer

    plan = make_organizer(library).organise()
    plan.enrich_queue   # sorted EnrichJobs, highest priority first
    plan.merge_pairs    # [(path_a, path_b, confidence), ...]
    plan.cluster_map    # {cluster_id: [paths]}
    plan.suggested_tags # {path: [tag_str, ...]}
    plan.prune_flags    # {path: prune_score}
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional, TYPE_CHECKING

try:
    import torch
    _TORCH_OK = True
except ImportError:
    torch = None  # type: ignore[assignment]
    _TORCH_OK = False

from phi.meta._octopus_types import (
    OrganizationPlan,
    TAG_VOCAB,
    MERGE_THRESHOLD,
    GRAFT_THRESHOLD,
    PRUNE_WARNING,
)
from phi.meta._meta_embedder import MetaEmbedder
from phi.meta._octopus_arms import (
    build_enrich_queue,
    extract_pairs,
    build_cluster_map,
    build_tag_suggestions,
)

if TYPE_CHECKING:
    from phi.core.library import Library
    from phi.gnn.octopus_tracer import OctopusTracer
    from phi.models.clap_proj import CLAPProjection

logger = logging.getLogger(__name__)


class OctopusOrganizer:
    """Runs OctopusTracer over the full Phi library to produce an OrganizationPlan.

    Designed to run:
      1. After batch_extractor (librosa cold embeddings available)
      2. Before AcoustID / MusicBrainz enrichment pipeline
      3. Optionally after CLAP annotation for a richer second pass

    Args:
        library          Phi Library instance
        tracer           OctopusTracer model (loaded or freshly initialised)
        projection       CLAPProjection — required for Tier 1 embeddings (optional)
        device           torch device
        meta_store_path  Override path to meta_store.jsonl
    """

    def __init__(
        self,
        library:         "Library",
        tracer:          "OctopusTracer",
        projection:      Optional["CLAPProjection"] = None,
        device=None,
        meta_store_path: Optional[Path]             = None,
    ) -> None:
        self._library    = library
        self._tracer     = tracer
        self._projection = projection
        self._device     = device or (torch.device("cpu") if _TORCH_OK else None)
        self._embedder   = MetaEmbedder(
            d_model    = tracer.d_model,
            device     = self._device,
            meta_store = meta_store_path,
        )

    def organise(self, auto_tick: bool = True) -> OrganizationPlan:
        """Run the full pipeline and return an OrganizationPlan.

        Steps: build H → tracer forward → extract arm outputs → return plan.

        Args:
            auto_tick: advance tracer._tick after running (False during training).

        Returns: OrganizationPlan with all arm-derived intelligence.
        """
        H, paths, sources = self._embedder.embed(self._library, self._projection)

        if len(paths) == 0:
            logger.warning("OctopusOrganizer: empty library — returning empty plan")
            return OrganizationPlan(
                enrich_queue=[], merge_pairs=[], cluster_map={},
                suggested_tags={}, prune_flags={}, graft_pairs=[],
            )

        n_clap    = sum(1 for s in sources.values() if s == "clap")
        n_librosa = sum(1 for s in sources.values() if s == "librosa")
        n_random  = sum(1 for s in sources.values() if s == "random")
        logger.info(
            "OctopusOrganizer: N=%d  (clap=%d  librosa=%d  random=%d)",
            len(paths), n_clap, n_librosa, n_random,
        )

        self._tracer.eval()
        H_in = H.to(self._device) if _TORCH_OK and self._device is not None and hasattr(H, "to") else H
        if _TORCH_OK:
            import torch as _torch
            with _torch.no_grad():
                out = self._tracer(H_in, auto_spawn=False)
        else:
            out = self._tracer(H_in, auto_spawn=False)
        if auto_tick:
            self._tracer.tick()

        prune_flags = {
            paths[i]: float(out.prune[i])
            for i in range(len(paths))
            if float(out.prune[i]) >= PRUNE_WARNING
        }
        if prune_flags:
            logger.warning(
                "OctopusOrganizer: %d tracks flagged for pruning review",
                len(prune_flags),
            )

        plan = OrganizationPlan(
            enrich_queue   = build_enrich_queue(paths, sources, out),
            merge_pairs    = extract_pairs(paths, out.merge, MERGE_THRESHOLD),
            cluster_map    = build_cluster_map(paths, out.cluster),
            suggested_tags = build_tag_suggestions(paths, out.tag),
            prune_flags    = prune_flags,
            graft_pairs    = extract_pairs(paths, out.graft, GRAFT_THRESHOLD),
            n_clap         = n_clap,
            n_librosa      = n_librosa,
            n_random       = n_random,
            tracer_output  = out,
        )
        logger.info("OctopusOrganizer:\n%s", plan.summary())
        return plan


def make_organizer(
    library:    "Library",
    d_model:    int                        = 256,
    projection: Optional["CLAPProjection"] = None,
    device=None,
) -> OctopusOrganizer:
    """Instantiate an OctopusOrganizer with a fresh (untrained) tracer.

    For production, load a trained checkpoint instead::

        tracer = OctopusTracer()
        tracer.load_state_dict(torch.load("checkpoints/octopus.pt"))
        org = OctopusOrganizer(library, tracer, projection)
    """
    from phi.gnn.octopus_tracer import OctopusTracer
    tracer = OctopusTracer(
        d_model        = d_model,
        num_clusters   = 16,
        num_tags       = len(TAG_VOCAB),
        soft_edge_mode = True,
    )
    return OctopusOrganizer(library, tracer, projection, device)
