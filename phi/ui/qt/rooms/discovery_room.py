# -*- coding: utf-8 -*-
"""phi.ui.qt.rooms.discovery_room — OctopusOrganizer discovery UI.

The first real Z-spine page.  Runs OctopusOrganizer in a background QThread
and surfaces the five arm-output views the model produces:

  ┌──────────────────────────────────────────────────────────────────────┐
  │  DISCOVERY                                    [Run Analysis] [← →]  │
  ├──────────────────────────────────────────────────────────────────────┤
  │  coverage  CLAP ████████▒░ 72%  librosa ████░ 24%  random ░ 4%      │
  ├────────────────────────┬─────────────────────────────────────────────┤
  │  DISCOVER (enrich q)   │  CLUSTERS  /  DUPLICATES  /  FLAGS  [tabs] │
  │  ▲ 0.94  Track — Artist│  ● cluster 3 (14 tracks)                   │
  │  ▲ 0.89  Track — Artist│    Track — Artist                          │
  │  ▲ 0.81  Track — Artist│    …                                       │
  │  ▼ 0.12  Track (prune) │                                            │
  │  …                     │  ● cluster 7 (9 tracks)                    │
  ├────────────────────────┴─────────────────────────────────────────────┤
  │  TAGS  track — [electronic] [chill] [focused] …                     │
  ├──────────────────────────────────────────────────────────────────────┤
  │  mini transport                                                       │
  └──────────────────────────────────────────────────────────────────────┘

Room protocol: on_show(), on_refresh(), sync_transport(), mark_playing()
"""
from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from phi.config import (
    ACC, ACC2, BG, CARD, CARD2, BORDER, FG, GOLD, MUTED, VIOLET,
    METER_OK, METER_WARN, METER_CRIT,
)
from phi.ui.qt.rooms._mini_transport import MiniTransportWidget

# ── optional imports ──────────────────────────────────────────────────────────

try:
    from phi.meta._octopus_types import OrganizationPlan, EnrichJob, TAG_VOCAB
    _TYPES_OK = True
except ImportError:
    _TYPES_OK = False
    OrganizationPlan = None  # type: ignore[assignment,misc]
    EnrichJob = None          # type: ignore[assignment,misc]
    TAG_VOCAB = []            # type: ignore[assignment]

# ── geometry ──────────────────────────────────────────────────────────────────

_ROW_H       = 30
_LEFT_W_FRAC = 0.40   # left pane as fraction of total width


# ── worker thread ─────────────────────────────────────────────────────────────

class _AnalysisWorker(QThread):
    """Run OctopusOrganizer.organise() off the GUI thread."""

    finished = Signal(object)   # OrganizationPlan | None
    error    = Signal(str)

    def __init__(self, ctrl: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._ctrl = ctrl

    def run(self) -> None:
        try:
            lib = getattr(self._ctrl, "library", None)
            if lib is None:
                self.error.emit("library not available")
                return

            from phi.meta.octopus_organizer import make_organizer
            organizer = make_organizer(lib)
            plan = organizer.organise()
            self.finished.emit(plan)
        except Exception as exc:  # noqa: BLE001
            self.error.emit(f"{type(exc).__name__}: {exc}")


# ── coverage bar ──────────────────────────────────────────────────────────────

class _CoverageBar(QWidget):
    """Horizontal bar showing CLAP / librosa / random embedding coverage."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(28)
        lo = QHBoxLayout(self)
        lo.setContentsMargins(8, 2, 8, 2)
        lo.setSpacing(14)

        self._clap_lbl    = self._make_label("CLAP", METER_OK)
        self._lib_lbl     = self._make_label("librosa", METER_WARN)
        self._rand_lbl    = self._make_label("random", METER_CRIT)
        self._clap_bar    = self._make_bar(METER_OK)
        self._lib_bar     = self._make_bar(METER_WARN)
        self._rand_bar    = self._make_bar(METER_CRIT)

        lo.addWidget(self._clap_lbl)
        lo.addWidget(self._clap_bar)
        lo.addWidget(self._lib_lbl)
        lo.addWidget(self._lib_bar)
        lo.addWidget(self._rand_lbl)
        lo.addWidget(self._rand_bar)
        lo.addStretch()

    @staticmethod
    def _make_label(text: str, colour: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setFixedWidth(54)
        lbl.setStyleSheet(f"color: {colour}; font-size: 10px; font-family: Menlo, monospace;")
        return lbl

    @staticmethod
    def _make_bar(colour: str) -> QProgressBar:
        bar = QProgressBar()
        bar.setFixedSize(80, 10)
        bar.setRange(0, 100)
        bar.setValue(0)
        bar.setTextVisible(False)
        bar.setStyleSheet(
            f"QProgressBar {{background: {CARD2}; border: none; border-radius: 3px;}}"
            f"QProgressBar::chunk {{background: {colour}; border-radius: 3px;}}"
        )
        return bar

    def update_plan(self, plan: Any) -> None:
        total = max(plan.n_clap + plan.n_librosa + plan.n_random, 1)
        clap_pct  = round(plan.n_clap    / total * 100)
        lib_pct   = round(plan.n_librosa / total * 100)
        rand_pct  = round(plan.n_random  / total * 100)
        self._clap_bar.setValue(clap_pct)
        self._lib_bar.setValue(lib_pct)
        self._rand_bar.setValue(rand_pct)
        self._clap_lbl.setText(f"CLAP {clap_pct}%")
        self._lib_lbl.setText(f"librosa {lib_pct}%")
        self._rand_lbl.setText(f"random {rand_pct}%")

    def clear(self) -> None:
        for bar in (self._clap_bar, self._lib_bar, self._rand_bar):
            bar.setValue(0)
        self._clap_lbl.setText("CLAP")
        self._lib_lbl.setText("librosa")
        self._rand_lbl.setText("random")


# ── enrich queue pane (left) ─────────────────────────────────────────────────

class _EnrichPane(QWidget):
    """Sorted list of EnrichJobs — highest priority at top, prune-flagged at bottom."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        lo = QVBoxLayout(self)
        lo.setContentsMargins(0, 0, 0, 0)
        lo.setSpacing(0)

        hdr = QLabel("DISCOVER")
        hdr.setStyleSheet(
            f"color: {ACC}; font-size: 10px; font-family: Menlo, monospace;"
            f" padding: 4px 8px; background: {CARD};"
        )
        lo.addWidget(hdr)

        self._list = QListWidget()
        self._list.setStyleSheet(
            f"QListWidget {{background: {BG}; border: none; outline: none;}}"
            f"QListWidget::item {{padding: 2px 8px; color: {FG};"
            f" font-size: 11px; font-family: Menlo, monospace;}}"
            f"QListWidget::item:selected {{background: {CARD2}; color: {ACC};}}"
        )
        self._list.setUniformItemSizes(True)
        lo.addWidget(self._list)

        self._count = QLabel("")
        self._count.setStyleSheet(
            f"color: {MUTED}; font-size: 9px; font-family: Menlo, monospace; padding: 2px 8px;"
        )
        lo.addWidget(self._count)

    def update_plan(self, plan: Any) -> None:
        self._list.clear()
        jobs = plan.enrich_queue  # already sorted by priority desc
        for job in jobs:
            name    = Path(job.path).stem[:34]
            arrow   = "▼" if job.prune_score >= 0.75 else "▲"
            colour  = METER_CRIT if job.prune_score >= 0.75 else (
                METER_OK if job.priority >= 0.7 else FG
            )
            src_tag = f"[{job.embed_source[:3]}]"
            text    = f"{arrow} {job.priority:.2f}  {name}  {src_tag}"
            item = QListWidgetItem(text)
            item.setForeground(__import__("PySide6.QtGui", fromlist=["QColor"]).QColor(colour))
            item.setData(Qt.ItemDataRole.UserRole, job.path)
            item.setSizeHint(__import__("PySide6.QtCore", fromlist=["QSize"]).QSize(0, _ROW_H))
            self._list.addItem(item)

        self._count.setText(
            f"{len(jobs)} tracks  ·  {len(plan.prune_flags)} flagged for prune"
        )

    def clear(self) -> None:
        self._list.clear()
        self._count.setText("")


# ── cluster pane ─────────────────────────────────────────────────────────────

class _ClusterPane(QWidget):
    """Scrollable cluster → track list."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        lo = QVBoxLayout(self)
        lo.setContentsMargins(0, 0, 0, 0)

        self._list = QListWidget()
        self._list.setStyleSheet(
            f"QListWidget {{background: {BG}; border: none; outline: none;}}"
            f"QListWidget::item {{padding: 1px 6px; color: {FG};"
            f" font-size: 11px; font-family: Menlo, monospace;}}"
            f"QListWidget::item:selected {{background: {CARD2}; color: {ACC};}}"
        )
        lo.addWidget(self._list)

    def update_plan(self, plan: Any) -> None:
        self._list.clear()
        for cid in sorted(plan.cluster_map.keys()):
            paths = plan.cluster_map[cid]
            header = QListWidgetItem(f"● cluster {cid}  ({len(paths)} tracks)")
            header.setForeground(
                __import__("PySide6.QtGui", fromlist=["QColor"]).QColor(GOLD)
            )
            header.setFlags(Qt.ItemFlag.NoItemFlags)
            self._list.addItem(header)
            for p in sorted(paths)[:8]:
                item = QListWidgetItem(f"    {Path(p).stem[:40]}")
                item.setData(Qt.ItemDataRole.UserRole, p)
                self._list.addItem(item)
            if len(paths) > 8:
                more = QListWidgetItem(f"    … {len(paths) - 8} more")
                more.setForeground(
                    __import__("PySide6.QtGui", fromlist=["QColor"]).QColor(MUTED)
                )
                self._list.addItem(more)

    def clear(self) -> None:
        self._list.clear()


# ── duplicates pane ───────────────────────────────────────────────────────────

class _DuplicatesPane(QWidget):
    """Near-duplicate merge candidates from the merge arm."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        lo = QVBoxLayout(self)
        lo.setContentsMargins(0, 0, 0, 0)

        self._list = QListWidget()
        self._list.setStyleSheet(
            f"QListWidget {{background: {BG}; border: none; outline: none;}}"
            f"QListWidget::item {{padding: 1px 6px; color: {FG};"
            f" font-size: 11px; font-family: Menlo, monospace;}}"
            f"QListWidget::item:selected {{background: {CARD2}; color: {ACC};}}"
        )
        lo.addWidget(self._list)

    def update_plan(self, plan: Any) -> None:
        from PySide6.QtGui import QColor
        self._list.clear()
        if not plan.merge_pairs:
            item = QListWidgetItem("  no near-duplicates detected")
            item.setForeground(QColor(MUTED))
            self._list.addItem(item)
            return
        for pa, pb, score in sorted(plan.merge_pairs, key=lambda x: -x[2]):
            score_lbl = f"{score:.3f}"
            colour    = METER_CRIT if score >= 0.95 else METER_WARN
            item = QListWidgetItem(
                f"  {score_lbl}  {Path(pa).stem[:24]}  ↔  {Path(pb).stem[:24]}"
            )
            item.setForeground(QColor(colour))
            self._list.addItem(item)

    def clear(self) -> None:
        self._list.clear()


# ── flags pane ────────────────────────────────────────────────────────────────

class _FlagsPane(QWidget):
    """Prune-flagged tracks and graft suggestions."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        lo = QVBoxLayout(self)
        lo.setContentsMargins(0, 0, 0, 0)

        self._list = QListWidget()
        self._list.setStyleSheet(
            f"QListWidget {{background: {BG}; border: none; outline: none;}}"
            f"QListWidget::item {{padding: 1px 6px; color: {FG};"
            f" font-size: 11px; font-family: Menlo, monospace;}}"
            f"QListWidget::item:selected {{background: {CARD2}; color: {ACC};}}"
        )
        lo.addWidget(self._list)

    def update_plan(self, plan: Any) -> None:
        from PySide6.QtGui import QColor
        self._list.clear()

        if plan.prune_flags:
            hdr = QListWidgetItem(f"▼ PRUNE FLAGS  ({len(plan.prune_flags)})")
            hdr.setForeground(QColor(METER_CRIT))
            hdr.setFlags(Qt.ItemFlag.NoItemFlags)
            self._list.addItem(hdr)
            for p, score in sorted(plan.prune_flags.items(), key=lambda x: -x[1]):
                item = QListWidgetItem(f"  {score:.3f}  {Path(p).stem[:38]}")
                item.setForeground(QColor(METER_WARN))
                item.setData(Qt.ItemDataRole.UserRole, p)
                self._list.addItem(item)

        if plan.graft_pairs:
            hdr2 = QListWidgetItem(f"↗ GRAFT LINKS  ({len(plan.graft_pairs)})")
            hdr2.setForeground(QColor(VIOLET))
            hdr2.setFlags(Qt.ItemFlag.NoItemFlags)
            self._list.addItem(hdr2)
            for pa, pb, score in sorted(plan.graft_pairs, key=lambda x: -x[2])[:20]:
                item = QListWidgetItem(
                    f"  {score:.3f}  {Path(pa).stem[:20]}  →  {Path(pb).stem[:20]}"
                )
                item.setForeground(QColor(VIOLET))
                self._list.addItem(item)

        if not plan.prune_flags and not plan.graft_pairs:
            item = QListWidgetItem("  no flags")
            item.setForeground(QColor(MUTED))
            self._list.addItem(item)

    def clear(self) -> None:
        self._list.clear()


# ── tag strip ─────────────────────────────────────────────────────────────────

class _TagStrip(QWidget):
    """Shows suggested tags for the currently playing track (or first track in plan)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(34)
        lo = QHBoxLayout(self)
        lo.setContentsMargins(8, 2, 8, 2)
        lo.setSpacing(6)

        self._track_lbl = QLabel("—")
        self._track_lbl.setStyleSheet(
            f"color: {MUTED}; font-size: 10px; font-family: Menlo, monospace;"
        )
        self._track_lbl.setFixedWidth(180)
        lo.addWidget(self._track_lbl)

        self._tags_lbl = QLabel("")
        self._tags_lbl.setStyleSheet(
            f"color: {ACC}; font-size: 10px; font-family: Menlo, monospace;"
        )
        lo.addWidget(self._tags_lbl)
        lo.addStretch()

    def show_track(self, plan: Any, path: str) -> None:
        tags = plan.suggested_tags.get(path, [])
        self._track_lbl.setText(Path(path).stem[:28])
        self._tags_lbl.setText("  ".join(f"[{t}]" for t in tags) or "no tags suggested")

    def clear(self) -> None:
        self._track_lbl.setText("—")
        self._tags_lbl.setText("")


# ── DiscoveryRoom (ZSpinePage) ────────────────────────────────────────────────

class DiscoveryRoom(QWidget):
    """
    OctopusOrganizer discovery UI — the first real Z-spine page.

    Displays enrich queue, cluster map, near-duplicate flags, prune warnings,
    and per-track tag suggestions.  All heavy compute runs off the GUI thread.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        ctrl:   Any            = None,
    ) -> None:
        super().__init__(parent)
        self._ctrl   = ctrl
        self._plan: Any = None
        self._worker: Optional[_AnalysisWorker] = None
        self._build_ui()

    # ── layout ────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        header = QWidget()
        header.setFixedHeight(36)
        header.setStyleSheet(f"background: {CARD};")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(12, 0, 8, 0)
        hl.setSpacing(8)

        title = QLabel("DISCOVERY")
        title.setStyleSheet(
            f"color: {ACC}; font-size: 12px; font-family: Menlo, monospace; font-weight: bold;"
        )
        hl.addWidget(title)

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet(
            f"color: {MUTED}; font-size: 10px; font-family: Menlo, monospace;"
        )
        hl.addWidget(self._status_lbl, 1)

        self._prev_btn = QPushButton("←")
        self._next_btn = QPushButton("→")
        for btn in (self._prev_btn, self._next_btn):
            btn.setFixedSize(26, 24)
            btn.setStyleSheet(
                f"QPushButton {{background: {CARD2}; color: {FG}; border: none; border-radius: 3px;}}"
                f"QPushButton:hover {{background: {ACC2};}}"
            )
        self._prev_btn.clicked.connect(self._on_prev)
        self._next_btn.clicked.connect(self._on_next)

        self._run_btn = QPushButton("Run Analysis")
        self._run_btn.setFixedHeight(24)
        self._run_btn.setStyleSheet(
            f"QPushButton {{background: {ACC}; color: {BG}; border: none;"
            f" border-radius: 3px; font-size: 10px; font-family: Menlo, monospace; padding: 0 10px;}}"
            f"QPushButton:hover {{background: {GOLD}; color: {BG};}}"
            f"QPushButton:disabled {{background: {CARD2}; color: {MUTED};}}"
        )
        self._run_btn.clicked.connect(self._on_run)

        hl.addWidget(self._prev_btn)
        hl.addWidget(self._next_btn)
        hl.addWidget(self._run_btn)
        root.addWidget(header)

        # Coverage bar
        self._coverage = _CoverageBar()
        self._coverage.setStyleSheet(f"background: {CARD2};")
        root.addWidget(self._coverage)

        # Splitter — enrich queue (left) | tabs (right)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet(
            f"QSplitter::handle {{background: {BORDER}; width: 1px;}}"
        )

        self._enrich_pane = _EnrichPane()
        splitter.addWidget(self._enrich_pane)

        right = QTabWidget()
        right.setStyleSheet(
            f"QTabWidget::pane {{border: none; background: {BG};}}"
            f"QTabBar::tab {{background: {CARD}; color: {MUTED}; padding: 4px 12px;"
            f" font-size: 10px; font-family: Menlo, monospace; border: none;}}"
            f"QTabBar::tab:selected {{color: {ACC}; background: {BG};}}"
        )
        self._cluster_pane    = _ClusterPane()
        self._duplicates_pane = _DuplicatesPane()
        self._flags_pane      = _FlagsPane()
        right.addTab(self._cluster_pane,    "Clusters")
        right.addTab(self._duplicates_pane, "Duplicates")
        right.addTab(self._flags_pane,      "Flags")
        splitter.addWidget(right)

        splitter.setSizes([300, 500])
        root.addWidget(splitter, 1)

        # Tag strip
        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {BORDER};")
        root.addWidget(sep)
        self._tag_strip = _TagStrip()
        self._tag_strip.setStyleSheet(f"background: {CARD2};")
        root.addWidget(self._tag_strip)

        # Mini transport
        sep2 = QWidget()
        sep2.setFixedHeight(1)
        sep2.setStyleSheet(f"background: {BORDER};")
        root.addWidget(sep2)
        self._transport = MiniTransportWidget(ctrl=self._ctrl)
        root.addWidget(self._transport)

        # Connect enrich list → tag strip
        self._enrich_pane._list.currentItemChanged.connect(self._on_enrich_select)

    # ── room protocol ─────────────────────────────────────────────────────────

    def on_show(self) -> None:
        """Called when the z-spine navigates to this page."""
        if self._plan is None:
            self._set_status("no analysis yet — press Run Analysis")

    def on_refresh(self) -> None:
        pass

    def refresh(self, *args: Any, **kwargs: Any) -> None:
        pass

    def sync_transport(self, title: str, artist: str, playing: bool,
                       pos: float, duration: float) -> None:
        self._transport.sync(title, artist, playing, pos, duration)

    def update_transport(self, *args: Any, **kwargs: Any) -> None:
        if args:
            self._transport.sync(*args, **kwargs)

    def set_playing(self, *args: Any, **kwargs: Any) -> None:
        pass

    def mark_playing(self, path: str) -> None:
        """Highlight the currently playing track in the enrich queue and show its tags."""
        if self._plan is None:
            return
        lst = self._enrich_pane._list
        for i in range(lst.count()):
            item = lst.item(i)
            if item and item.data(Qt.ItemDataRole.UserRole) == path:
                lst.setCurrentRow(i)
                self._tag_strip.show_track(self._plan, path)
                break

    # ── analysis ─────────────────────────────────────────────────────────────

    def _on_run(self) -> None:
        if self._worker and self._worker.isRunning():
            return
        self._run_btn.setEnabled(False)
        self._set_status("analysing …")
        self._coverage.clear()
        self._enrich_pane.clear()
        self._cluster_pane.clear()
        self._duplicates_pane.clear()
        self._flags_pane.clear()
        self._tag_strip.clear()

        self._worker = _AnalysisWorker(self._ctrl, parent=self)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_finished(self, plan: Any) -> None:
        self._plan = plan
        self._coverage.update_plan(plan)
        self._enrich_pane.update_plan(plan)
        self._cluster_pane.update_plan(plan)
        self._duplicates_pane.update_plan(plan)
        self._flags_pane.update_plan(plan)
        n = plan.n_total
        pairs = len(plan.merge_pairs)
        clusters = len(plan.cluster_map)
        self._set_status(
            f"{n} tracks  ·  {clusters} clusters  ·  {pairs} dup pairs"
            f"  ·  {plan.coverage_pct}% CLAP"
        )
        self._run_btn.setEnabled(True)

    def _on_error(self, msg: str) -> None:
        self._set_status(f"error: {msg}")
        self._run_btn.setEnabled(True)

    def _set_status(self, text: str) -> None:
        self._status_lbl.setText(text)

    # ── navigation ────────────────────────────────────────────────────────────

    def _on_prev(self) -> None:
        if self._ctrl and hasattr(self._ctrl, "z_prev_page"):
            self._ctrl.z_prev_page()

    def _on_next(self) -> None:
        if self._ctrl and hasattr(self._ctrl, "z_next_page"):
            self._ctrl.z_next_page()

    # ── enrich list selection ─────────────────────────────────────────────────

    def _on_enrich_select(self, current: Any, _previous: Any) -> None:
        if current is None or self._plan is None:
            return
        path = current.data(Qt.ItemDataRole.UserRole)
        if path:
            self._tag_strip.show_track(self._plan, path)
