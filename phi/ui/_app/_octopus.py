# -*- coding: utf-8 -*-
"""phi.ui._app._octopus — OctopusOrganizer + PhiOrchestrator background init."""
from __future__ import annotations
import threading


class _OctopusMixin:
    """_init_octopus_bg / _init_octopus / _apply_plan_to_annotations — DAWN ML pipeline."""

    def _init_octopus_bg(self) -> None:
        """Schedule OctopusOrganizer initialisation on a background thread.

        Called from the main thread (via self.after) so it never blocks the UI.
        A second call while a run is in progress is a no-op (thread is still alive).
        """
        if getattr(self, "_octopus_thread", None) and self._octopus_thread.is_alive():
            return
        self._octopus_thread = threading.Thread(
            target=self._init_octopus,
            daemon=True,
            name="phi-octopus",
        )
        self._octopus_thread.start()

    def _init_octopus(self) -> None:
        """Background thread: build OctopusOrganizer, run it, apply all arm outputs.

        Returns immediately (silently) when torch is not installed — the full
        ML pipeline requires torch and the GNN cannot run without it.

        Pipeline:
          1. Instantiate CLAPProjection (cheap — Xavier init, no network)
          2. Instantiate OctopusTracer  (≈251K params, CPU in < 1s)
          3. Run organise() — builds H from librosa/CLAP, forward pass, emits plan
          4. Pass plan to enrich_daemon.set_plan(plan)   ← reorders enrichment queue
          5. Apply all arm outputs to annotations via _apply_plan_to_annotations()
             - octopus_tags     (tag arm)      → feeds genre_consensus each cycle
             - octopus_cluster  (cluster arm)  → grouping signal for ranker/UI
             - octopus_prune_score             → surfaces bad-file candidates
             - octopus_sprout / resurface      → isolation / burial signals
             - octopus_grafts  (graft arm)     → informational link suggestions
          6. Push near-duplicate pairs (merge arm) to review_queue
          7. Subscribe to CAIRRN MATH shard (3) → rebuild when CLAP data changes
          8. Schedule a 20-minute periodic re-run to stay current between events
        """
        try:
            import torch  # noqa: F401
        except ImportError:
            return  # ML pipeline unavailable without torch — skip silently

        try:
            import logging
            _log = logging.getLogger("phi.octopus")
            _log.info("OctopusOrganizer: starting background pass…")

            from phi.models.clap_proj import CLAPProjection
            from phi.gnn.octopus_tracer import OctopusTracer
            from phi.meta.octopus_organizer import OctopusOrganizer

            if not hasattr(self, "_octopus_organizer") or self._octopus_organizer is None:
                proj   = CLAPProjection.load_default()
                tracer = OctopusTracer(
                    d_model        = proj.d_model,
                    num_clusters   = 16,
                    num_tags       = 64,
                    soft_edge_mode = True,
                )
                self._octopus_organizer = OctopusOrganizer(
                    library    = self.library,
                    tracer     = tracer,
                    projection = proj,
                )

            plan = self._octopus_organizer.organise()
            _log.info(
                "OctopusOrganizer: plan ready  n=%d  clap=%d  librosa=%d  random=%d"
                "  clusters=%d  merge_pairs=%d  graft_pairs=%d  prune_flagged=%d",
                plan.n_total, plan.n_clap, plan.n_librosa, plan.n_random,
                len(plan.cluster_map), len(plan.merge_pairs),
                len(plan.graft_pairs), len(plan.prune_flags),
            )

            if self.enrich_daemon is not None:
                self.enrich_daemon.set_plan(plan)

            self.dispatch(0, lambda p=plan: self._apply_plan_to_annotations(p))

            if not getattr(self, "_octopus_math_subscribed", False):
                self._octopus_math_subscribed = True

                def _on_math_shift(result, payload: dict) -> None:
                    if result.should_act:
                        _log.info(
                            "CAIRRN/MATH: CLAP embeddings updated — "
                            "re-running OctopusOrganizer"
                        )
                        self._init_octopus_bg()

                self.floor.when_floor_shifts(shard=3, handler=_on_math_shift)
                _log.info("OctopusOrganizer: subscribed to CAIRRN MATH shard (3)")

            self._sched(20 * 60 * 1_000, self._init_octopus_bg)

            try:
                from phi.graph.phi_orchestrator import PhiOrchestrator

                if not getattr(self, "_phi_orchestrator", None):
                    from phi.models.clap_proj  import CLAPProjection as _ClapProj
                    from phi.gnn.octopus_tracer import OctopusTracer   as _Tracer
                    _orch_proj   = _ClapProj.load_default()
                    _orch_tracer = _Tracer(
                        d_model        = _orch_proj.d_model,
                        num_clusters   = 16,
                        num_tags       = 64,
                        soft_edge_mode = True,
                    )
                    _lib  = self.library
                    _q    = self.queue
                    _self = self   # capture for the closure below

                    def _on_gnn_write(ranked: list) -> None:
                        """Called from the GNN background thread after every write.

                        1. Reorder pending queue slots via QueueEngine.nudge()
                           (order is F_SCUP_CANONICAL from PhiTracerBridge).
                        2. Notify QueueRoom on the main thread so it can refresh
                           the list and increment the GNN nudge counter.
                        """
                        n = _q.nudge(ranked, _lib)
                        if n > 0:
                            qr = getattr(_self, "_queue_page", None)
                            if qr is not None:
                                _self.dispatch(0, lambda _n=n: qr.on_gnn_nudge(_n))

                    self._phi_orchestrator = PhiOrchestrator(
                        library   = _lib,
                        tracer    = _orch_tracer,
                        clap_proj = _orch_proj,
                        on_write  = _on_gnn_write,
                    )

                orch_result = self._phi_orchestrator.run_cycle()
                _log.info(
                    "PhiOrchestrator: n=%d  embedded=%d  d4=%d  "
                    "coh=%.3f  write=%s  %.0f ms",
                    orch_result["n_tracks"],
                    orch_result["n_embedded"],
                    orch_result["d4_scored"],
                    orch_result["coherence_score"],
                    orch_result["write_gated"],
                    orch_result["elapsed_ms"],
                )
            except Exception as _orch_exc:
                import traceback as _tb
                _log.warning(
                    "PhiOrchestrator cycle non-fatal: %s\n%s",
                    _orch_exc, _tb.format_exc(),
                )

        except Exception as exc:
            import logging, traceback
            logging.getLogger("phi.octopus").warning(
                "OctopusOrganizer pass failed (non-fatal): %s\n%s",
                exc, traceback.format_exc(),
            )

    def _apply_plan_to_annotations(self, plan) -> None:
        """Main-thread: write all OctopusOrganizer arm outputs into library annotations.

        Called via dispatch() from the background octopus thread — always on Tk thread.

        Annotations written per track:
            octopus_tags          list[str]   — tag arm suggestions (genre/mood)
            octopus_cluster       int         — hard cluster assignment
            octopus_prune_score   float       — quality concern signal ∈ [0,1]
            octopus_sprout        float       — graph isolation signal ∈ [0,1]
            octopus_resurface     float       — burial signal ∈ [0,1]
            octopus_grafts        list[str]   — top-3 suggested link paths

        Near-duplicate pairs (merge arm ≥ 0.80) are pushed to review_queue.
        """
        import os as _os

        cluster_by_path = plan.cluster_map_by_path
        graft_by_path   = plan.graft_map_by_path
        n_annotated     = 0

        for job in plan.enrich_queue:
            path = job.path
            ann: dict = {}

            tags = plan.suggested_tags.get(path)
            if tags:
                ann["octopus_tags"] = tags

            cid = cluster_by_path.get(path)
            if cid is not None:
                ann["octopus_cluster"] = cid

            prune = plan.prune_flags.get(path, 0.0)
            if prune > 0:
                ann["octopus_prune_score"] = round(prune, 4)

            ann["octopus_sprout"]    = round(job.sprout_score,    4)
            ann["octopus_resurface"] = round(job.resurface_score, 4)

            grafts = graft_by_path.get(path, [])
            if grafts:
                grafts_sorted = sorted(grafts, key=lambda t: -t[1])[:3]
                ann["octopus_grafts"] = [p for p, _ in grafts_sorted]

            if ann:
                self.library.store_annotation(path, ann)
                n_annotated += 1

        dupes_annotated = 0
        for pa, pb, conf in plan.merge_pairs:
            conf_r = round(conf, 4)
            try:
                self.library.store_annotation(pa, {"octopus_near_dup": [pb, conf_r]})
                self.library.store_annotation(pb, {"octopus_near_dup": [pa, conf_r]})
                dupes_annotated += 1
            except Exception:
                pass

        _log = __import__("logging").getLogger("phi.octopus")
        _log.info(
            "_apply_plan_to_annotations: annotated=%d  merge_candidates=%d  "
            "prune_flagged=%d  clusters=%d",
            n_annotated, dupes_annotated, len(plan.prune_flags), len(plan.cluster_map),
        )

        if plan.prune_flags:
            names = [_os.path.basename(p) for p in list(plan.prune_flags)[:2]]
            suffix = f" +{len(plan.prune_flags)-2} more" if len(plan.prune_flags) > 2 else ""
            self._flash(
                f"Octopus: {len(plan.prune_flags)} tracks flagged for review "
                f"({', '.join(names)}{suffix})",
                ms=8_000,
            )
        elif plan.merge_pairs:
            self._flash(
                f"Octopus: {len(plan.merge_pairs)} near-duplicate pair"
                f"{'s' if len(plan.merge_pairs) != 1 else ''} found",
                ms=5_000,
            )
