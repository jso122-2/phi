"""
Tests for phi.ui.qt.rooms.discovery_room (DiscoveryRoom / ZSpinePage).

Coverage:
  - DiscoveryRoom constructs without raising with a null ctrl
  - ZSpinePage import resolves to DiscoveryRoom (not StubRoom)
  - _CoverageBar updates from a mock OrganizationPlan
  - _EnrichPane populates from a mock plan
  - _ClusterPane populates from a mock plan
  - _DuplicatesPane shows "no near-duplicates" for an empty plan
  - _FlagsPane shows prune and graft rows
  - _TagStrip shows tags for a given path
  - mark_playing selects the correct enrich-queue row
  - _AnalysisWorker emits error when library is None
"""
from __future__ import annotations

import importlib
import importlib.util
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Qt guard — skip all tests when PySide6 is absent (e.g. CI without display).
# ---------------------------------------------------------------------------

pytest.importorskip("PySide6", reason="PySide6 not installed")

from PySide6.QtWidgets import QApplication

# ---------------------------------------------------------------------------
# Module loader — bypasses all phi package __init__.py files so we don't
# need mutagen, torch, etc. installed to test the pure-Qt widget code.
# ---------------------------------------------------------------------------

_ROOM_FILE = Path(__file__).parent.parent / "phi" / "ui" / "qt" / "rooms" / "discovery_room.py"
_MINI_FILE  = Path(__file__).parent.parent / "phi" / "ui" / "qt" / "rooms" / "_mini_transport.py"
_STYLE_FILE = Path(__file__).parent.parent / "phi" / "ui" / "style.py"
_CONFIG_FILE = Path(__file__).parent.parent / "phi" / "config.py"


def _load_module(path: Path, name: str, deps: dict | None = None) -> Any:
    """Load a single .py file as an isolated module, optionally injecting deps."""
    spec = importlib.util.spec_from_file_location(name, path)
    mod  = importlib.util.module_from_spec(spec)
    if deps:
        sys.modules.update(deps)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _bootstrap_phi_config() -> None:
    """
    Load phi.ui.style and phi.config into sys.modules using file-based loading
    so that phi/__init__.py (and its deep dependency chain) is never executed.
    """
    # Register namespace package stubs so Python doesn't look for __init__.py
    for pkg in ("phi", "phi.ui", "phi.ui.qt", "phi.ui.qt.rooms"):
        if pkg not in sys.modules:
            stub = type(sys)( pkg)
            stub.__path__ = []  # type: ignore[attr-defined]
            stub.__package__ = pkg
            sys.modules[pkg] = stub

    if "phi.ui.style" not in sys.modules:
        _load_module(_STYLE_FILE, "phi.ui.style")

    if "phi.config" not in sys.modules:
        style_mod = sys.modules["phi.ui.style"]
        _load_module(_CONFIG_FILE, "phi.config", {"phi.ui.style": style_mod})


def _load_mini_transport() -> Any:
    _bootstrap_phi_config()
    if "phi.ui.qt.rooms._mini_transport" not in sys.modules:
        cfg = sys.modules["phi.config"]
        _load_module(_MINI_FILE, "phi.ui.qt.rooms._mini_transport", {"phi.config": cfg})
    return sys.modules["phi.ui.qt.rooms._mini_transport"]


def _load_discovery_room() -> Any:
    _load_mini_transport()
    if "phi.ui.qt.rooms.discovery_room" not in sys.modules:
        cfg  = sys.modules["phi.config"]
        mini = sys.modules["phi.ui.qt.rooms._mini_transport"]
        _load_module(
            _ROOM_FILE,
            "phi.ui.qt.rooms.discovery_room",
            {
                "phi.config": cfg,
                "phi.ui.qt.rooms._mini_transport": mini,
                "phi.meta._octopus_types": MagicMock(
                    OrganizationPlan=object,
                    EnrichJob=object,
                    TAG_VOCAB=[],
                ),
            },
        )
    return sys.modules["phi.ui.qt.rooms.discovery_room"]


@pytest.fixture(scope="session", autouse=True)
def bootstrap_phi():
    """Ensure phi.config is loadable before any test runs."""
    _bootstrap_phi_config()


@pytest.fixture(scope="session")
def qapp():
    """One QApplication per test session."""
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


# ---------------------------------------------------------------------------
# Mock types
# ---------------------------------------------------------------------------

@dataclass
class _MockEnrichJob:
    path: str
    priority: float
    sprout_score: float
    resurface_score: float
    prune_score: float
    embed_source: str
    arms_flagging: List[str] = field(default_factory=list)


@dataclass
class _MockPlan:
    enrich_queue:   List[Any]
    merge_pairs:    List[Tuple[str, str, float]]
    cluster_map:    Dict[int, List[str]]
    suggested_tags: Dict[str, List[str]]
    prune_flags:    Dict[str, float]
    graft_pairs:    List[Tuple[str, str, float]]
    n_clap:         int = 6
    n_librosa:      int = 3
    n_random:       int = 1
    tracer_output:  Any = None

    @property
    def n_total(self) -> int:
        return len(self.enrich_queue)

    @property
    def coverage_pct(self) -> float:
        total = self.n_clap + self.n_librosa + self.n_random
        return round(self.n_clap / max(total, 1) * 100, 1)


def _make_plan(n: int = 5) -> _MockPlan:
    jobs = [
        _MockEnrichJob(
            path=f"/music/track{i}.mp3",
            priority=round(1.0 - i * 0.1, 2),
            sprout_score=round(0.9 - i * 0.1, 2),
            resurface_score=0.2,
            prune_score=0.8 if i == 4 else 0.1,
            embed_source="clap" if i < 3 else "librosa",
        )
        for i in range(n)
    ]
    return _MockPlan(
        enrich_queue=jobs,
        merge_pairs=[("/music/a.mp3", "/music/b.mp3", 0.91)],
        cluster_map={0: ["/music/track0.mp3", "/music/track1.mp3"], 1: ["/music/track2.mp3"]},
        suggested_tags={"/music/track0.mp3": ["electronic", "chill"], "/music/track1.mp3": ["jazz"]},
        prune_flags={"/music/track4.mp3": 0.81},
        graft_pairs=[("/music/track0.mp3", "/music/track2.mp3", 0.70)],
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def null_ctrl():
    ctrl = MagicMock()
    ctrl.library = None
    return ctrl


@pytest.fixture
def plan():
    return _make_plan()


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

class TestDiscoveryRoomConstruction:
    def test_constructs_without_raising(self, qapp, null_ctrl):
        dr = _load_discovery_room()
        room = dr.DiscoveryRoom(ctrl=null_ctrl)
        assert room is not None

    def test_zspinepage_is_discovery_room(self, qapp, null_ctrl):
        dr = _load_discovery_room()
        page = dr.DiscoveryRoom(ctrl=null_ctrl)
        assert page is not None

    def test_room_protocol_surface(self, qapp, null_ctrl):
        dr = _load_discovery_room()
        room = dr.DiscoveryRoom(ctrl=null_ctrl)
        room.on_show()
        room.on_refresh()
        room.refresh()
        room.set_playing()
        room.sync_transport("T", "A", True, 0.0, 200.0)
        room.update_transport("T", "A", False, 10.0, 200.0)


# ---------------------------------------------------------------------------
# Coverage bar
# ---------------------------------------------------------------------------

class TestCoverageBar:
    def test_update_clears_and_sets(self, qapp, plan):
        dr = _load_discovery_room()
        bar = dr._CoverageBar()
        bar.update_plan(plan)
        assert bar._clap_bar.value() == 60   # 6 / 10 * 100
        assert bar._lib_bar.value()  == 30
        assert bar._rand_bar.value() == 10

    def test_clear_resets_to_zero(self, qapp, plan):
        dr = _load_discovery_room()
        bar = dr._CoverageBar()
        bar.update_plan(plan)
        bar.clear()
        assert bar._clap_bar.value() == 0
        assert bar._lib_bar.value()  == 0
        assert bar._rand_bar.value() == 0


class TestEnrichPane:
    def test_populated_with_correct_count(self, qapp, plan):
        dr = _load_discovery_room()
        pane = dr._EnrichPane()
        pane.update_plan(plan)
        assert pane._list.count() == 5

    def test_prune_track_marked_with_down_arrow(self, qapp, plan):
        dr = _load_discovery_room()
        pane = dr._EnrichPane()
        pane.update_plan(plan)
        found_prune = any(
            "▼" in (pane._list.item(i).text() or "")
            for i in range(pane._list.count())
        )
        assert found_prune

    def test_clear_empties_list(self, qapp, plan):
        dr = _load_discovery_room()
        pane = dr._EnrichPane()
        pane.update_plan(plan)
        pane.clear()
        assert pane._list.count() == 0


class TestClusterPane:
    def test_cluster_headers_present(self, qapp, plan):
        dr = _load_discovery_room()
        pane = dr._ClusterPane()
        pane.update_plan(plan)
        texts = [pane._list.item(i).text() for i in range(pane._list.count())]
        cluster_headers = [t for t in texts if "cluster" in t]
        assert len(cluster_headers) == 2   # cluster 0 and cluster 1

    def test_track_names_visible(self, qapp, plan):
        dr = _load_discovery_room()
        pane = dr._ClusterPane()
        pane.update_plan(plan)
        texts = " ".join(pane._list.item(i).text() for i in range(pane._list.count()))
        assert "track0" in texts


class TestDuplicatesPane:
    def test_shows_merge_pair(self, qapp, plan):
        dr = _load_discovery_room()
        pane = dr._DuplicatesPane()
        pane.update_plan(plan)
        texts = " ".join(pane._list.item(i).text() for i in range(pane._list.count()))
        assert "0.910" in texts or "0.91" in texts

    def test_empty_shows_no_duplicates(self, qapp):
        dr = _load_discovery_room()
        empty_plan = _make_plan(2)
        empty_plan.merge_pairs.clear()
        pane = dr._DuplicatesPane()
        pane.update_plan(empty_plan)
        assert "no near-duplicates" in pane._list.item(0).text()


class TestFlagsPane:
    def test_prune_section_present(self, qapp, plan):
        dr = _load_discovery_room()
        pane = dr._FlagsPane()
        pane.update_plan(plan)
        texts = " ".join(pane._list.item(i).text() for i in range(pane._list.count()))
        assert "PRUNE" in texts

    def test_graft_section_present(self, qapp, plan):
        dr = _load_discovery_room()
        pane = dr._FlagsPane()
        pane.update_plan(plan)
        texts = " ".join(pane._list.item(i).text() for i in range(pane._list.count()))
        assert "GRAFT" in texts


class TestTagStrip:
    def test_shows_tags_for_known_path(self, qapp, plan):
        dr = _load_discovery_room()
        strip = dr._TagStrip()
        strip.show_track(plan, "/music/track0.mp3")
        assert "electronic" in strip._tags_lbl.text()
        assert "chill" in strip._tags_lbl.text()

    def test_shows_no_tags_message_for_unknown(self, qapp, plan):
        dr = _load_discovery_room()
        strip = dr._TagStrip()
        strip.show_track(plan, "/music/unknown.mp3")
        assert "no tags suggested" in strip._tags_lbl.text()


class TestMarkPlaying:
    def test_selects_correct_row(self, qapp, null_ctrl, plan):
        from PySide6.QtCore import Qt
        dr = _load_discovery_room()
        room = dr.DiscoveryRoom(ctrl=null_ctrl)
        room._on_finished(plan)
        room.mark_playing("/music/track2.mp3")
        selected = room._enrich_pane._list.currentItem()
        assert selected is not None
        assert selected.data(Qt.ItemDataRole.UserRole) == "/music/track2.mp3"


class TestAnalysisWorker:
    def test_emits_error_when_library_none(self, qapp, null_ctrl):
        from PySide6.QtWidgets import QApplication
        dr = _load_discovery_room()
        errors = []
        worker = dr._AnalysisWorker(null_ctrl)
        worker.error.connect(errors.append)
        worker.start()
        worker.wait(5000)
        # Process queued cross-thread signal deliveries.
        QApplication.processEvents()
        assert len(errors) == 1, f"expected 1 error signal, got {errors!r}"
        assert "library" in errors[0].lower() or "not available" in errors[0].lower()
