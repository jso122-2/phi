"""
tests/test_cursor_tracer.py — unit tests for engine.cursor_tracer.

Coverage:
  - HoverRegion.contains() — boundary, inside, outside
  - CursorSample hovered_regions field — default empty list, as_dict omits key
    when empty, includes key when non-empty
  - CursorTracer.register_hover() — registers region, initialises counter to 0
  - CursorTracer._check_hover() — dwell accumulation, fires at threshold,
    does NOT fire before threshold, does NOT fire again on the next sample,
    resets counter after leaving region, can re-fire after re-entry
  - CursorTracer.attach_dispatcher() — swapped dispatcher receives signals
  - CursorTracer.snapshot() hover_regions key exposed
  - No exception raised when dispatcher.signal_hover() raises
"""
from __future__ import annotations

import pytest

from engine.cursor_tracer import CursorTracer, CursorSample, HoverRegion


# ---------------------------------------------------------------------------
# HoverRegion.contains
# ---------------------------------------------------------------------------

class TestHoverRegionContains:
    def _region(self) -> HoverRegion:
        return HoverRegion(name="play", x=100.0, y=200.0, w=80.0, h=40.0)

    def test_inside_centre(self):
        r = self._region()
        assert r.contains(140.0, 220.0)

    def test_top_left_corner(self):
        r = self._region()
        assert r.contains(100.0, 200.0)

    def test_bottom_right_corner(self):
        r = self._region()
        assert r.contains(180.0, 240.0)

    def test_outside_left(self):
        r = self._region()
        assert not r.contains(99.9, 220.0)

    def test_outside_right(self):
        r = self._region()
        assert not r.contains(180.1, 220.0)

    def test_outside_top(self):
        r = self._region()
        assert not r.contains(140.0, 199.9)

    def test_outside_bottom(self):
        r = self._region()
        assert not r.contains(140.0, 240.1)

    def test_dwell_samples_default(self):
        r = self._region()
        assert r.dwell_samples == 2


# ---------------------------------------------------------------------------
# CursorSample — hovered_regions field
# ---------------------------------------------------------------------------

class TestCursorSampleHoveredRegions:
    def _sample(self, hovered=None) -> CursorSample:
        return CursorSample(
            ts=1.0, x=0.0, y=0.0, metric=0.5,
            hub="CODE", coherence=0.75, re_routed=False, interval_ms=500.0,
            **({"hovered_regions": hovered} if hovered is not None else {}),
        )

    def test_default_empty(self):
        s = self._sample()
        assert s.hovered_regions == []

    def test_as_dict_omits_key_when_empty(self):
        d = self._sample().as_dict()
        assert "hovered_regions" not in d

    def test_as_dict_includes_key_when_non_empty(self):
        s = self._sample(hovered=["play"])
        d = s.as_dict()
        assert d["hovered_regions"] == ["play"]

    def test_as_dict_multiple_regions(self):
        s = self._sample(hovered=["play", "next"])
        assert set(s.as_dict()["hovered_regions"]) == {"play", "next"}


# ---------------------------------------------------------------------------
# CursorTracer.register_hover + dwell logic
# ---------------------------------------------------------------------------

class _FakeDispatcher:
    """Minimal dispatcher stub that records signal_hover calls."""
    def __init__(self) -> None:
        self.signals: list[str] = []

    def signal_hover(self, name: str) -> bool:
        self.signals.append(name)
        return True


class TestCursorTracerHover:
    def _tracer(self) -> CursorTracer:
        return CursorTracer(max_samples=10, hub="CODE")

    def test_register_initialises_counter_zero(self):
        t = self._tracer()
        r = HoverRegion(name="play", x=0, y=0, w=100, h=50)
        t.register_hover(r)
        with t._hover_lock:
            assert t._dwell_counters["play"] == 0

    def test_no_signal_before_threshold(self):
        t = self._tracer()
        d = _FakeDispatcher()
        t.attach_dispatcher(d)
        t.register_hover(HoverRegion(name="btn", x=0, y=0, w=100, h=50, dwell_samples=3))
        # Two samples inside — threshold is 3, should not fire yet
        t._check_hover(50.0, 25.0)
        t._check_hover(50.0, 25.0)
        assert d.signals == []

    def test_signal_fires_exactly_at_threshold(self):
        t = self._tracer()
        d = _FakeDispatcher()
        t.attach_dispatcher(d)
        t.register_hover(HoverRegion(name="btn", x=0, y=0, w=100, h=50, dwell_samples=2))
        t._check_hover(50.0, 25.0)  # count → 1, no fire
        fired = t._check_hover(50.0, 25.0)  # count → 2, fires
        assert fired == ["btn"]
        assert d.signals == ["hover:btn"]

    def test_signal_does_not_re_fire_while_still_inside(self):
        t = self._tracer()
        d = _FakeDispatcher()
        t.attach_dispatcher(d)
        t.register_hover(HoverRegion(name="btn", x=0, y=0, w=100, h=50, dwell_samples=2))
        t._check_hover(50.0, 25.0)
        t._check_hover(50.0, 25.0)  # fires
        t._check_hover(50.0, 25.0)  # count goes to 3 — must NOT re-fire
        t._check_hover(50.0, 25.0)  # count goes to 4 — must NOT re-fire
        assert len(d.signals) == 1

    def test_counter_resets_on_leave(self):
        t = self._tracer()
        d = _FakeDispatcher()
        t.attach_dispatcher(d)
        t.register_hover(HoverRegion(name="btn", x=0, y=0, w=100, h=50, dwell_samples=2))
        t._check_hover(50.0, 25.0)  # inside — count 1
        t._check_hover(200.0, 200.0)  # outside — counter resets to 0
        with t._hover_lock:
            assert t._dwell_counters["btn"] == 0

    def test_can_refire_after_reentry(self):
        t = self._tracer()
        d = _FakeDispatcher()
        t.attach_dispatcher(d)
        t.register_hover(HoverRegion(name="btn", x=0, y=0, w=100, h=50, dwell_samples=2))
        # First dwell entry
        t._check_hover(50.0, 25.0)
        t._check_hover(50.0, 25.0)  # fires once
        # Leave
        t._check_hover(999.0, 999.0)
        # Re-enter
        t._check_hover(50.0, 25.0)
        t._check_hover(50.0, 25.0)  # fires again
        assert d.signals == ["hover:btn", "hover:btn"]

    def test_multiple_regions_independent(self):
        t = self._tracer()
        d = _FakeDispatcher()
        t.attach_dispatcher(d)
        t.register_hover(HoverRegion(name="play",  x=0,   y=0, w=50, h=50, dwell_samples=2))
        t.register_hover(HoverRegion(name="pause", x=100, y=0, w=50, h=50, dwell_samples=2))
        # Cursor inside "play" only
        t._check_hover(25.0, 25.0)
        t._check_hover(25.0, 25.0)
        assert d.signals == ["hover:play"]
        # Now move to "pause"
        t._check_hover(125.0, 25.0)
        t._check_hover(125.0, 25.0)
        assert "hover:pause" in d.signals
        assert d.signals.count("hover:play") == 1  # no extra play fires

    def test_no_dispatcher_no_exception(self):
        t = self._tracer()
        t.register_hover(HoverRegion(name="btn", x=0, y=0, w=100, h=50, dwell_samples=1))
        fired = t._check_hover(50.0, 25.0)
        assert fired == ["btn"]  # returns fired names even without dispatcher

    def test_broken_dispatcher_does_not_crash(self):
        class BrokenDispatcher:
            def signal_hover(self, name: str) -> bool:
                raise RuntimeError("intentional failure")

        t = self._tracer()
        t.attach_dispatcher(BrokenDispatcher())
        t.register_hover(HoverRegion(name="btn", x=0, y=0, w=100, h=50, dwell_samples=1))
        # Must not raise
        fired = t._check_hover(50.0, 25.0)
        assert fired == ["btn"]

    def test_attach_dispatcher_replaces_previous(self):
        t = self._tracer()
        d1 = _FakeDispatcher()
        d2 = _FakeDispatcher()
        t.attach_dispatcher(d1)
        t.attach_dispatcher(d2)
        t.register_hover(HoverRegion(name="btn", x=0, y=0, w=100, h=50, dwell_samples=1))
        t._check_hover(50.0, 25.0)
        assert d1.signals == []
        assert d2.signals == ["hover:btn"]


# ---------------------------------------------------------------------------
# snapshot() exposes hover_regions
# ---------------------------------------------------------------------------

class TestCursorTracerSnapshot:
    def test_snapshot_hover_regions_empty(self):
        t = CursorTracer()
        snap = t.snapshot()
        assert snap["hover_regions"] == []

    def test_snapshot_hover_regions_populated(self):
        t = CursorTracer()
        t.register_hover(HoverRegion(name="play", x=0, y=0, w=100, h=50, dwell_samples=2))
        snap = t.snapshot()
        assert len(snap["hover_regions"]) == 1
        entry = snap["hover_regions"][0]
        assert entry["name"] == "play"
        assert entry["dwell_samples"] == 2
        assert entry["counter"] == 0

    def test_snapshot_counter_advances(self):
        t = CursorTracer()
        t.register_hover(HoverRegion(name="play", x=0, y=0, w=100, h=50, dwell_samples=3))
        t._check_hover(50.0, 25.0)
        t._check_hover(50.0, 25.0)
        snap = t.snapshot()
        assert snap["hover_regions"][0]["counter"] == 2
