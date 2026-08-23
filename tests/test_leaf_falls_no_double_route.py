"""Regression: leaf_falls must not DOUBLE_ROUTE TRACK_TRANSITION with arrival.

Departure (leaf_falls) records the leaf + skip-pressure ML_INFERENCE only.
Arrival (_apply_track_to_ui) owns the single TRACK_TRANSITION route.
"""
from __future__ import annotations

from phi.engine.cairrn.floor import ForestFloor
from phi.engine.cairrn.router import RequestKind


class TestLeafFallsNoDoubleRoute:
    def test_leaf_falls_routes_ml_inference_not_track_transition(self):
        floor = ForestFloor()
        result = floor.leaf_falls("/tmp/track.mp3", completion_rate=0.88)
        assert result.kind == RequestKind.ML_INFERENCE
        assert len(floor.fallen_leaves) == 1

    def test_departure_then_arrival_no_double_route(self):
        """Mirrors load_and_play: record_departure → schedule(_apply_track_to_ui)."""
        floor = ForestFloor()
        floor.leaf_falls("/tmp/prev.mp3", completion_rate=0.9)
        arrival = floor.router.route(
            RequestKind.TRACK_TRANSITION,
            metric=1.0,
            payload={"path": "/tmp/next.mp3"},
        )
        assert arrival.kind == RequestKind.TRACK_TRANSITION
        assert floor._watchdog._total_double_route == 0
        # Suppressed stubs always return modulated=0.0; a real pipeline step does not.
        assert arrival.modulated != 0.0
