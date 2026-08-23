# -*- coding: utf-8 -*-
"""phi.graph.phi_orchestrator — end-to-end Phi ↔ OctopusTracer cycle.

PhiOrchestrator ties the full ML pipeline together in a single `run_cycle()`
call.  It is the runtime counterpart of the plan diagram:

    PhiGraph.build()               →  snap.H   (N, 256) CLAP embeddings
    derivative_bridge.score_and_attach() →  snap.d4_scores  (N,)
    PhiGraphBuilder.build_topology()     →  TopologicalGraph (χ, β₀, β₁)
    D4InjectionLayer(H, d4)              →  H_aug  (N, 256)
    OctopusTracer(H_aug)                 →  TracerOutput  (8 arms)
    CoherenceLayer ← topo.invariant.chi  (live topology target)
    PhiTracerBridge.write(out, snap, topo) →  library.annotations

The orchestrator is intentionally thin — each component (PhiGraph,
PhiGraphBuilder, D4InjectionLayer, OctopusTracer, PhiTracerBridge) is tested
and used independently.  PhiOrchestrator is only the runtime glue.

CAIRRN gate
───────────
Before running the tracer, the orchestrator checks `tracer.write_gated`.
If coherence < 0.50, arm outputs are computed but PhiTracerBridge.write()
is skipped — matching the CAIRRN Layer 3 write-authority contract.

Usage
─────
    from phi.graph.phi_orchestrator import PhiOrchestrator

    orch = PhiOrchestrator(
        library   = library,
        tracer    = OctopusTracer(d_model=256),
        clap_proj = CLAPProjection(),
    )
    result = orch.run_cycle()
    # result["topo"]    — topology snapshot dict
    # result["n_tracks"] — number of tracks processed
    # result["wrote"]   — True if CAIRRN gate allowed write
"""
from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Callable, List, Optional

import numpy as np

try:
    import torch
    _TORCH_OK = True
except ImportError:
    torch = None  # type: ignore[assignment]
    _TORCH_OK = False

from phi.graph.phi_graph_gnn     import PhiGraph   # GNN version
from phi.graph.phi_graph_builder import PhiGraphBuilder, D4InjectionLayer
from phi.graph.phi_tracer_bridge import PhiTracerBridge
from phi.graph.derivative_bridge import score_and_attach

if TYPE_CHECKING:
    from phi.core.library         import Library
    from phi.models.clap_proj     import CLAPProjection
    from phi.gnn.octopus_tracer import OctopusTracer

logger = logging.getLogger(__name__)


class PhiOrchestrator:
    """
    Full Phi ↔ OctopusTracer inference cycle.

    Each call to run_cycle():
      1. Builds the CLAP embedding graph (PhiGraph)
      2. Attaches D4 acoustic quality scores (derivative_bridge)
      3. Constructs the typed music topology (PhiGraphBuilder → TopologicalGraph)
      4. Injects D4 into node embeddings H (D4InjectionLayer)
      5. Sets the live Euler characteristic χ on the CoherenceLayer
      6. Runs OctopusTracer forward pass (all 8 arms)
      7. Advances the CAIRRN tick counter
      8. If coherence ≥ 0.50 (write_gated), writes arm outputs to Library

    Args:
        library:        Phi Library — source of annotations and track list
        tracer:         OctopusTracer model instance (pre-loaded or freshly init)
        clap_proj:      CLAPProjection — projects 512-d CLAP vecs → 256-d
        device:         torch device (default: cpu)
        sim_threshold:  CLAP cosine floor for semantic edges (default 0.65)
        bpm_window:     BPM proximity window for temporal edges (default 8.0)
        graft_top_k:    Max graft suggestions per track (default 5)
        d4_inject:      If True, augment H with D4InjectionLayer (default True)
    """

    def __init__(
        self,
        library:       "Library",
        tracer:        "OctopusTracer",
        clap_proj:     "CLAPProjection",
        device=None,
        sim_threshold: float = 0.65,
        bpm_window:    float = 8.0,
        graft_top_k:   int   = 5,
        d4_inject:     bool  = True,
        on_write:      Optional[Callable[[List[str]], None]] = None,
    ) -> None:
        self._library = library
        self._tracer  = tracer
        self._device  = device or (torch.device("cpu") if _TORCH_OK else None)
        self._d4_inject = d4_inject

        self._phi_graph = PhiGraph(
            library=library,
            projection=clap_proj,
            sim_threshold=sim_threshold,
        )
        self._builder = PhiGraphBuilder(
            library=library,
            clap_proj=clap_proj,
            sim_threshold=sim_threshold,
            bpm_window=bpm_window,
            device=self._device,
        )
        self._d4_layer = D4InjectionLayer(d_model=tracer.d_model)
        if _TORCH_OK and self._device is not None:
            self._d4_layer = self._d4_layer.to(self._device)
        self._bridge   = PhiTracerBridge(
            library,
            graft_top_k=graft_top_k,
            on_write=on_write,    # fires queue.nudge() after every GNN write
        )

    # ── main cycle ────────────────────────────────────────────────────────────

    def run_cycle(self, auto_spawn: bool = True) -> dict:
        """
        Execute one full Phi ↔ OctopusTracer inference cycle.

        Args:
            auto_spawn: whether to allow SuckerPool spawns during the tracer pass

        Returns:
            dict with keys:
                n_tracks:       number of tracks processed
                n_embedded:     tracks with CLAP embeddings
                topo:           TopologicalGraph snapshot dict (χ, β₀, β₁, …)
                coherence_score: CAIRRN coherence gate value
                write_gated:    True if arm outputs were written to Library
                elapsed_ms:     wall-clock time for the full cycle
                d4_scored:      number of tracks with valid D4 scores
        """
        t0 = time.perf_counter()
        logger.info("PhiOrchestrator cycle start")

        # ── Step 1: CLAP embedding graph ──────────────────────────────────────
        snap = self._phi_graph.build()
        N    = snap.n_embedded
        if N == 0:
            logger.warning("PhiOrchestrator: no CLAP-embedded tracks — cycle skipped.")
            return {"n_tracks": snap.n_tracks, "n_embedded": 0,
                    "topo": {}, "coherence_score": self._tracer.coherence_score,
                    "write_gated": False, "elapsed_ms": 0, "d4_scored": 0}

        # ── Step 2: D4 derivative scores ──────────────────────────────────────
        snap = score_and_attach(snap)
        d4_scored = int((~np.isnan(snap.d4_scores)).sum()) if snap.d4_scores is not None else 0

        # ── Step 3: Typed music topology ──────────────────────────────────────
        topo = self._builder.build_topology(snap)
        inv  = topo.invariant
        logger.info(
            "Music topology: V=%d  E=%d  T=%d  χ=%.1f  β₀=%d  β₁=%d",
            inv.V, inv.E, inv.T, inv.chi, inv.beta_0, inv.beta_1,
        )

        # ── Step 4: Bind live χ to CoherenceLayer (if model has one) ──────────
        if hasattr(self._tracer, "coherence"):
            self._tracer.coherence.euler_chi_target = float(inv.chi)

        # ── Step 5: D4-augmented embeddings ───────────────────────────────────
        H = snap.H
        if _TORCH_OK:
            import torch as _torch
            if isinstance(H, np.ndarray):
                H = _torch.from_numpy(H.astype(np.float32))
            if self._device is not None and hasattr(H, "to"):
                H = H.to(self._device)
        if _TORCH_OK and self._d4_inject and snap.d4_scores is not None:
            import torch as _torch
            with _torch.no_grad():
                d4_t = _torch.from_numpy(snap.d4_scores)
                if self._device is not None:
                    d4_t = d4_t.to(self._device)
                H = self._d4_layer(H, d4_t)

        # ── Step 6: OctopusTracer forward pass ────────────────────────────────
        if _TORCH_OK and self._device is not None and hasattr(self._tracer, "to"):
            self._tracer.to(self._device)
        if hasattr(self._tracer, "eval"):
            self._tracer.eval()

        bert_w = None  # warm-start weight for SuckerPool (None = kaiming init)

        if _TORCH_OK:
            import torch as _torch
            with _torch.no_grad():
                out = self._tracer(
                    H           = H,
                    adj         = None,
                    auto_spawn  = auto_spawn,
                    bert_proj_weight = bert_w,
                )
        else:
            out = self._tracer(
                H           = H,
                adj         = None,
                auto_spawn  = auto_spawn,
                bert_proj_weight = bert_w,
            )

        # ── Step 7: Advance CAIRRN tick ───────────────────────────────────────
        self._tracer.tick()
        coherence_score = out.coherence_score
        write_gated     = out.write_gated

        # ── Step 8: Write arm outputs to Library (if CAIRRN gate allows) ──────
        wrote = False
        if write_gated:
            self._bridge.write(out, snap, topo)
            wrote = True
        else:
            logger.info(
                "PhiOrchestrator: CAIRRN coherence=%.3f < 0.50 — arms read-only, no write.",
                coherence_score,
            )

        elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
        logger.info(
            "PhiOrchestrator cycle done  n=%d  wrote=%s  coh=%.3f  %.0f ms",
            N, wrote, coherence_score, elapsed_ms,
        )

        return {
            "n_tracks":       snap.n_tracks,
            "n_embedded":     N,
            "d4_scored":      d4_scored,
            "topo":           topo.snapshot(),
            "coherence_score": round(coherence_score, 4),
            "write_gated":    wrote,
            "elapsed_ms":     elapsed_ms,
        }

    # ── accessors ─────────────────────────────────────────────────────────────

    @property
    def tracer(self) -> "OctopusTracer":
        return self._tracer

    @property
    def bridge(self) -> PhiTracerBridge:
        return self._bridge

    @property
    def d4_layer(self) -> D4InjectionLayer:
        return self._d4_layer

    def reset_cairrn(self) -> None:
        """Reset the CAIRRN tick counter — arms regain write authority immediately."""
        self._tracer.reset_tick()
        logger.info("PhiOrchestrator: CAIRRN tick reset → coherence=1.0")

    def parameter_report(self) -> dict:
        """Combined parameter count across tracer + D4 injection layer."""
        tracer_report = self._tracer.parameter_report()
        tracer_report["d4_injection"] = self._d4_layer.parameter_count()
        tracer_report["total_phi_orch"] = (
            tracer_report.get("total_tracer", 0) + tracer_report["d4_injection"]
        )
        return tracer_report
