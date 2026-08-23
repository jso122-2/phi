"""
Tests for engine/phi_player.py — PhiPlayer playback + CAIRRN feedback loop.

Synthetic subsystems — no disk I/O, no audio playback.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from engine.cairrn_dispatch import CAIRRNDispatcher, PhiAction, PhiActionKind
from engine.gate import COHERENCE_THRESHOLD
from engine.hot_loader import CAIRRNHotLoader
from engine.phi_player import (
    FRAC_HEARD,
    FRAC_LOVED,
    PhiPlayer,
    PlayEvent,
    make_phi_player,
)
from phi._track import Track
from phi.graph.phi_graph import PhiGraphSnapshot
from sims.harmonic import HarmonicIndex


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tracks(n: int = 5) -> list[Track]:
    return [
        Track(path=Path(f"/fake/T{i}.mp3"), json_path=Path(f"/fake/T{i}.json"),
              name=f"Song {i}", artist=f"Artist {i}")
        for i in range(n)
    ]


def _make_snap(n: int = 5) -> PhiGraphSnapshot:
    rng = np.random.default_rng(0)
    H = rng.standard_normal((n, 256))
    H /= np.linalg.norm(H, axis=1, keepdims=True)
    A = np.zeros((n, n))
    return PhiGraphSnapshot(tracks=_make_tracks(n), H=H, A=A)


def _make_index() -> HarmonicIndex:
    return HarmonicIndex(n_harmonics=8, coupling=0.15)


def _make_dispatcher(index: HarmonicIndex | None = None) -> CAIRRNDispatcher:
    idx = index or _make_index()
    return CAIRRNDispatcher(
        harmonic_index=idx,
        tau=0.001,       # near-zero tau so gate opens immediately in tests
        threshold=COHERENCE_THRESHOLD,
    )


def _make_shuffle_mock(snap: PhiGraphSnapshot, index: HarmonicIndex) -> MagicMock:
    """
    Minimal CAIRRNPrefeedShuffle mock.

    - _session.snapshot → snap
    - _session.harmonic_index → index
    - shuffle.next() → cycles 0..N-1
    - shuffle.peek() → ShufflePeek-like object
    - peek_and_preload() → no-op
    - state() → {}
    """
    from engine.prefeed_shuffle import ShufflePeek

    cursor = [0]

    def _next():
        idx = cursor[0] % snap.N
        cursor[0] += 1
        return idx

    session_mock = MagicMock()
    session_mock.snapshot = snap
    session_mock.harmonic_index = index

    shuffle_inner = MagicMock()
    shuffle_inner.next.side_effect = _next
    shuffle_inner.peek.return_value = ShufflePeek(
        cursor=0, indices=list(range(min(3, snap.N))), pending_ready=False
    )

    mock = MagicMock()
    mock._session = session_mock
    mock.next.side_effect = _next
    mock.peek_and_preload.return_value = ShufflePeek(
        cursor=0, indices=[], pending_ready=False
    )
    mock.state.return_value = {}
    mock.shuffle = shuffle_inner
    return mock


def _make_player(
    n: int = 5,
    hot_loader: CAIRRNHotLoader | None = None,
) -> tuple[PhiPlayer, MagicMock, CAIRRNDispatcher, HarmonicIndex]:
    snap = _make_snap(n)
    idx = _make_index()
    dispatcher = _make_dispatcher(idx)
    shuffle = _make_shuffle_mock(snap, idx)
    player = PhiPlayer(
        shuffle=shuffle,
        dispatcher=dispatcher,
        hot_loader=hot_loader,
        preload_ahead=3,
    )
    return player, shuffle, dispatcher, idx


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestConstruction:
    def test_defaults(self):
        player, _, _, _ = _make_player()
        assert player.total_plays == 0
        assert player.skip_rate == 0.0
        assert player.current_track is None
        assert player.history == []

    def test_factory(self):
        snap = _make_snap()
        idx = _make_index()
        dispatcher = _make_dispatcher(idx)
        shuffle = _make_shuffle_mock(snap, idx)
        p = make_phi_player(shuffle=shuffle, dispatcher=dispatcher)
        assert isinstance(p, PhiPlayer)


# ---------------------------------------------------------------------------
# play_next
# ---------------------------------------------------------------------------


class TestPlayNext:
    def test_returns_track(self):
        player, _, _, _ = _make_player()
        track = player.play_next()
        assert isinstance(track, Track)

    def test_current_track_set_during_play(self):
        player, _, _, _ = _make_player()
        track = player.play_next()
        assert player.current_track is track

    def test_advances_cursor_each_call(self):
        player, shuffle, _, _ = _make_player()
        player.play_next()
        player.report_play(1.0)
        player.play_next()
        assert shuffle.next.call_count == 2

    def test_calls_peek_and_preload_when_hot_loader_attached(self):
        hl = CAIRRNHotLoader()
        player, shuffle, _, _ = _make_player(hot_loader=hl)
        player.play_next()
        shuffle.peek_and_preload.assert_called_once_with(hl, n=3)

    def test_no_peek_and_preload_without_hot_loader(self):
        player, shuffle, _, _ = _make_player(hot_loader=None)
        player.play_next()
        shuffle.peek_and_preload.assert_not_called()

    def test_raises_when_snapshot_none(self):
        snap = _make_snap()
        idx = _make_index()
        dispatcher = _make_dispatcher(idx)
        shuffle = _make_shuffle_mock(snap, idx)
        shuffle._session.snapshot = None
        player = PhiPlayer(shuffle=shuffle, dispatcher=dispatcher)
        with pytest.raises(RuntimeError, match="snapshot not built"):
            player.play_next()


# ---------------------------------------------------------------------------
# report_play
# ---------------------------------------------------------------------------


class TestReportPlay:
    def test_returns_play_event(self):
        player, _, _, _ = _make_player()
        player.play_next()
        event = player.report_play(0.9)
        assert isinstance(event, PlayEvent)

    def test_play_fraction_clamped(self):
        player, _, _, _ = _make_player()
        player.play_next()
        event = player.report_play(1.5)
        assert event.play_fraction == pytest.approx(1.0)

    def test_play_fraction_clamped_low(self):
        player, _, _, _ = _make_player()
        player.play_next()
        event = player.report_play(-0.5)
        assert event.play_fraction == pytest.approx(0.0)

    def test_current_track_cleared_after_report(self):
        player, _, _, _ = _make_player()
        player.play_next()
        player.report_play(1.0)
        assert player.current_track is None

    def test_increments_total_plays(self):
        player, _, _, _ = _make_player()
        for _ in range(3):
            player.play_next()
            player.report_play(1.0)
        assert player.total_plays == 3

    def test_skip_counted_below_frac_heard(self):
        player, _, _, _ = _make_player()
        player.play_next()
        event = player.report_play(FRAC_HEARD - 0.01)
        assert event.skipped is True
        assert player.skip_rate == pytest.approx(1.0)

    def test_not_skip_at_frac_heard(self):
        player, _, _, _ = _make_player()
        player.play_next()
        event = player.report_play(FRAC_HEARD)
        assert event.skipped is False

    def test_raises_without_play_next(self):
        player, _, _, _ = _make_player()
        with pytest.raises(RuntimeError, match="play_next"):
            player.report_play(1.0)

    def test_raises_if_called_twice(self):
        player, _, _, _ = _make_player()
        player.play_next()
        player.report_play(1.0)
        with pytest.raises(RuntimeError, match="play_next"):
            player.report_play(0.5)

    def test_event_stored_in_history(self):
        player, _, _, _ = _make_player()
        player.play_next()
        event = player.report_play(0.95)
        assert player.history[-1] is event


# ---------------------------------------------------------------------------
# Injection thresholds
# ---------------------------------------------------------------------------


class TestInjectionThresholds:
    """Verify _compute_injections maps fractions to correct hub values."""

    def test_loved_injects_both_hubs(self):
        player, _, _, _ = _make_player()
        home, code = player._compute_injections(FRAC_LOVED)
        assert home == pytest.approx(FRAC_LOVED)
        assert code == pytest.approx(FRAC_LOVED)

    def test_loved_above_threshold(self):
        player, _, _, _ = _make_player()
        frac = 0.95
        home, code = player._compute_injections(frac)
        assert home == pytest.approx(frac)
        assert code == pytest.approx(frac)

    def test_heard_only_home(self):
        player, _, _, _ = _make_player()
        frac = 0.60
        home, code = player._compute_injections(frac)
        assert home == pytest.approx(frac)
        assert code == pytest.approx(0.0)

    def test_heard_lower_bound(self):
        player, _, _, _ = _make_player()
        home, code = player._compute_injections(FRAC_HEARD)
        assert home == pytest.approx(FRAC_HEARD)
        assert code == pytest.approx(0.0)

    def test_skipped_no_injection(self):
        player, _, _, _ = _make_player()
        home, code = player._compute_injections(0.0)
        assert home == pytest.approx(0.0)
        assert code == pytest.approx(0.0)

    def test_just_below_heard_no_injection(self):
        player, _, _, _ = _make_player()
        home, code = player._compute_injections(FRAC_HEARD - 0.01)
        assert home == pytest.approx(0.0)
        assert code == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Harmonic injection — verify dispatcher is called
# ---------------------------------------------------------------------------


class TestHarmonicFeedback:
    def test_loved_track_injects_home_and_code(self):
        player, _, dispatcher, idx = _make_player()
        player.play_next()

        # Spy on force_dispatch
        calls: list[PhiAction] = []
        original = dispatcher.force_dispatch

        def _spy(action):
            calls.append(action)
            return original(action)

        dispatcher.force_dispatch = _spy
        player.report_play(0.95)

        kinds = [c.kind for c in calls]
        hubs  = [c.payload.get("hub_name") for c in calls if c.kind == PhiActionKind.HUB_INJECT]

        assert PhiActionKind.HUB_INJECT in kinds
        assert PhiActionKind.PROPAGATE in kinds
        assert "HOME" in hubs
        assert "CODE" in hubs

    def test_heard_track_injects_only_home(self):
        player, _, dispatcher, _ = _make_player()
        player.play_next()

        calls: list[PhiAction] = []
        original = dispatcher.force_dispatch

        def _spy(action):
            calls.append(action)
            return original(action)

        dispatcher.force_dispatch = _spy
        player.report_play(0.60)

        hubs = [c.payload.get("hub_name") for c in calls if c.kind == PhiActionKind.HUB_INJECT]
        assert "HOME" in hubs
        assert "CODE" not in hubs

    def test_skipped_track_no_injection(self):
        player, _, dispatcher, _ = _make_player()
        player.play_next()

        calls: list[PhiAction] = []
        original = dispatcher.force_dispatch

        def _spy(action):
            calls.append(action)
            return original(action)

        dispatcher.force_dispatch = _spy
        player.report_play(0.10)

        inject_calls = [c for c in calls if c.kind == PhiActionKind.HUB_INJECT]
        propagate_calls = [c for c in calls if c.kind == PhiActionKind.PROPAGATE]
        assert inject_calls == []
        assert propagate_calls == []

    def test_propagate_uses_2_steps(self):
        player, _, dispatcher, _ = _make_player()
        player.play_next()

        calls: list[PhiAction] = []
        original = dispatcher.force_dispatch

        def _spy(action):
            calls.append(action)
            return original(action)

        dispatcher.force_dispatch = _spy
        player.report_play(0.95)

        prop = [c for c in calls if c.kind == PhiActionKind.PROPAGATE]
        assert len(prop) == 1
        assert prop[0].payload["steps"] == 2

    def test_injection_uses_urgent_priority(self):
        player, _, dispatcher, _ = _make_player()
        player.play_next()

        calls: list[PhiAction] = []
        original = dispatcher.force_dispatch

        def _spy(action):
            calls.append(action)
            return original(action)

        dispatcher.force_dispatch = _spy
        player.report_play(0.95)

        inject_calls = [c for c in calls if c.kind == PhiActionKind.HUB_INJECT]
        assert all(c.priority == -1 for c in inject_calls)


# ---------------------------------------------------------------------------
# Full loop — play → report → play → report
# ---------------------------------------------------------------------------


class TestFullLoop:
    def test_multi_track_cycle(self):
        player, _, _, _ = _make_player(n=5)
        for _ in range(5):
            player.play_next()
            player.report_play(1.0)
        assert player.total_plays == 5
        assert len(player.history) == 5

    def test_skip_rate_tracking(self):
        player, _, _, _ = _make_player(n=10)
        for i in range(10):
            player.play_next()
            frac = 0.0 if i % 2 == 0 else 1.0
            player.report_play(frac)
        assert player.skip_rate == pytest.approx(0.5, abs=0.01)

    def test_history_ring_respects_max(self):
        player, _, _, _ = _make_player(n=5)
        player._history.maxlen  # just access
        for _ in range(10):
            player.play_next()
            player.report_play(1.0)
        assert len(player.history) <= 200

    def test_play_event_has_duration(self):
        player, _, _, _ = _make_player()
        player.play_next()
        event = player.report_play(1.0)
        assert event.duration_s >= 0.0


# ---------------------------------------------------------------------------
# State / repr
# ---------------------------------------------------------------------------


class TestState:
    def test_state_keys(self):
        player, _, _, _ = _make_player()
        st = player.state()
        for key in ("in_play", "current", "total_plays", "skip_rate",
                    "history_len", "last_event", "shuffle", "dispatcher"):
            assert key in st, f"Missing key: {key}"

    def test_state_in_play_true(self):
        player, _, _, _ = _make_player()
        player.play_next()
        assert player.state()["in_play"] is True

    def test_state_in_play_false_after_report(self):
        player, _, _, _ = _make_player()
        player.play_next()
        player.report_play(1.0)
        assert player.state()["in_play"] is False

    def test_repr(self):
        player, _, _, _ = _make_player()
        r = repr(player)
        assert "plays=" in r
        assert "skip_rate=" in r

    def test_play_event_as_dict(self):
        player, _, _, _ = _make_player()
        player.play_next()
        event = player.report_play(0.9)
        d = event.as_dict()
        for key in ("track", "track_idx", "duration_s", "play_fraction",
                    "skipped", "home_injected", "code_injected"):
            assert key in d
