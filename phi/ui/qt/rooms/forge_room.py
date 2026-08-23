# -*- coding: utf-8 -*-
"""phi.ui.qt.rooms.forge_room — ML Forge room.

Forge is the training / fitting station of the ML route.

Pipeline
--------
    1. MetaClipper.fit(library)         — build TF-IDF → SVD → PCA pipeline
       MetaClipper.run_batch(library)   — produce clipper_emb, clipper_x/y,
                                          fold_bits, d4_b for every track
    2. D4XGBoostModel.fit(anns, y)      — train XGBoost regressor
    3. Save both to ~/.phi/ checkpoints

Layout
------
┌──────────────────────────────────────────────────────────────────────┐
│  FORGE           ‹ Dragon · Inference · Forge ›        [Forge Model] │
├──────────────────────────────────────────────────────────────────────┤
│  STATUS                                                               │
│  MetaClipper  ░  not fitted    D4XGBoost   ░  not fitted             │
│  n_tracks     —                n_train     —                          │
│  vocab        —                val_rmse    —                          │
│                                                                       │
│  LOG ──────────────────────────────────────────────────────────────  │
│  > 14:23  Fitting MetaClipper on 842 tracks…                         │
│  > 14:23  MetaClipper fitted — vocab=4 122, explained_var=0.612      │
│  > 14:24  Training D4XGBoostModel…                                   │
│  > 14:24  D4XGBoostModel fitted — val_rmse=0.0312 (n_train=757)      │
│                                                                       │
│  FEATURE IMPORTANCE ───────────────────────────────────────────────  │
│  emb(36)  ████████████▒░░░ 0.512   fold(8)  █████░░░ 0.341   d4b  … │
│                                                                       │
│  SOCIAL COVERAGE ──────────────────────────────────────────────────  │
│  year             ████████████████████  98.3%                        │
│  duration         ████████████████████ 100.0%                        │
│  artist_lib_count ████████████████████ 100.0%                        │
│  spotify_pop      ░░░░░░░░░░░░░░░░░░░░   0.0%                       │
├──────────────────────────────────────────────────────────────────────┤
│  mini transport                                                        │
└──────────────────────────────────────────────────────────────────────┘

Room protocol: on_show(), on_refresh(), sync_transport(), mark_playing()
"""
from __future__ import annotations

import datetime
import os
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from phi.config import (
    ACC, ACC2, BG, CARD, CARD2, BORDER,
    FG, GOLD, INDIGO, MUTED, VIOLET,
    METER_OK, METER_WARN, METER_CRIT,
    PHI_DIR,
)
from phi.ui.qt.rooms._mini_transport import MiniTransportWidget


# ─────────────────────────────────────────────────────────────────────────────
# Route constants
# ─────────────────────────────────────────────────────────────────────────────

_ROUTE     = ["Dragon", "Inference", "Forge"]
_ROUTE_IDX = 2   # Forge is index 2

_CLIPPER_PATH = PHI_DIR / "meta_clipper.joblib"
_XGB_PATH     = PHI_DIR / "d4_xgb.joblib"


# ─────────────────────────────────────────────────────────────────────────────
# Background worker
# ─────────────────────────────────────────────────────────────────────────────

class _ForgeWorker(QThread):
    """
    Fit MetaClipper + train D4XGBoostModel on the library.

    Emits log lines to ``log_line`` as they happen, then ``finished``
    with a result dict, or ``error`` with an error string.
    """

    log_line = Signal(str)
    finished = Signal(dict)   # {n_tracks, vocab, explained_var, n_train, val_rmse, fi}
    error    = Signal(str)

    def __init__(
        self,
        items: list[tuple[str, dict]],   # (path, meta) pairs
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._items = items

    def _log(self, msg: str) -> None:
        ts = datetime.datetime.now().strftime("%H:%M")
        self.log_line.emit(f"[{ts}]  {msg}")

    def run(self) -> None:
        items = self._items
        n     = len(items)

        try:
            from phi.models.meta_clipper import MetaClipper
            from phi.models.d4_model    import D4XGBoostModel

            # ── 1. MetaClipper ────────────────────────────────────────────────
            self._log(f"Fitting MetaClipper on {n} tracks…")
            clipper = MetaClipper(depth=8)
            clipper.fit(items)

            vocab        = len(clipper._vec.vocabulary_) if clipper._vec else 0
            explained    = float(clipper._svd.explained_variance_ratio_.sum()) \
                           if clipper._svd else 0.0
            self._log(
                f"MetaClipper fitted — vocab={vocab:,}  "
                f"n_svd={clipper._n_svd_actual}  explained_var={explained:.3f}"
            )

            # ── 2. run_batch → annotations + rolling D4_A ─────────────────────
            self._log("Computing clipper annotations (run_batch)…")
            anns, rolling_d4a = clipper.run_batch(items, rolling_window=16)
            self._log(f"Annotations ready — {len(anns)} rows")

            # ── 3. D4XGBoostModel ─────────────────────────────────────────────
            self._log("Training D4XGBoostModel (XGBoost)…")
            model = D4XGBoostModel()
            fit_result = model.fit(anns, rolling_d4a)
            self._log(
                f"D4XGBoostModel fitted — "
                f"n_train={fit_result['n_train']}  "
                f"n_val={fit_result['n_val']}  "
                f"val_rmse={fit_result['val_rmse']:.4f}"
            )

            # ── 4. Feature importance ─────────────────────────────────────────
            fi = model.feature_importance()
            self._log(
                f"Feature importance — emb={fi['emb_mean']:.3f}  "
                f"fold={fi['fold_mean']:.3f}  d4b={fi['d4b_score']:.3f}"
            )

            # ── 5. Save checkpoints ───────────────────────────────────────────
            PHI_DIR.mkdir(parents=True, exist_ok=True)
            clipper.save(_CLIPPER_PATH)
            self._log(f"MetaClipper saved → {_CLIPPER_PATH}")
            model.save(_XGB_PATH)
            self._log(f"D4XGBoostModel saved → {_XGB_PATH}")

            # ── 6. Write clipper annotations back to meta_cache ───────────────
            self._log("Writing clipper annotations to meta_cache…")
            self.finished.emit({
                "n_tracks":     n,
                "vocab":        vocab,
                "explained_var": explained,
                "n_train":      fit_result["n_train"],
                "n_val":        fit_result["n_val"],
                "val_rmse":     fit_result["val_rmse"],
                "fi":           fi,
                "anns":         anns,
                "paths":        [p for p, _ in items],
            })

        except ImportError as exc:
            self.error.emit(f"Missing dependency: {exc}")
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))


# ─────────────────────────────────────────────────────────────────────────────
# Small bar widget for feature importance / social coverage
# ─────────────────────────────────────────────────────────────────────────────

def _ascii_bar(frac: float, width: int = 20) -> str:
    filled = int(round(max(0.0, min(1.0, frac)) * width))
    return "█" * filled + "░" * (width - filled)


# ─────────────────────────────────────────────────────────────────────────────
# MLForgePage
# ─────────────────────────────────────────────────────────────────────────────

class MLForgePage(QWidget):
    """
    Forge room — train MetaClipper + D4XGBoostModel on the current library.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        ctrl:   object         = None,
    ) -> None:
        super().__init__(parent)
        self._ctrl   = ctrl
        self._worker: Optional[_ForgeWorker] = None
        self._last_result: dict = {}
        self._build()
        self._check_checkpoints()

    # ── layout ────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._make_header())

        # Scrollable body
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            f"QScrollArea {{ background: {BG}; border: none; }}"
            f"QScrollBar:vertical {{ background: {CARD2}; width: 6px; border: none; }}"
            f"QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 3px; }}"
        )

        body = QWidget()
        body.setStyleSheet(f"background: {BG};")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(20, 16, 20, 16)
        body_layout.setSpacing(16)

        body_layout.addWidget(self._make_status_panel())
        body_layout.addWidget(self._make_log_panel())
        body_layout.addWidget(self._make_importance_panel())
        body_layout.addWidget(self._make_coverage_panel())
        body_layout.addStretch()

        scroll.setWidget(body)
        root.addWidget(scroll, stretch=1)

        self._mini = MiniTransportWidget(ctrl=self._ctrl, parent=self)
        root.addWidget(self._mini)

    def _make_header(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(36)
        bar.setStyleSheet(f"background: {CARD2}; border-bottom: 1px solid {BORDER};")
        row = QHBoxLayout(bar)
        row.setContentsMargins(14, 0, 10, 0)
        row.setSpacing(8)

        title = QLabel("FORGE")
        title.setStyleSheet(
            f"color: {ACC}; font-size: 10px; letter-spacing: 3px; "
            "border: none; background: transparent;"
        )
        row.addWidget(title)
        row.addStretch()

        nav_left = QPushButton("‹")
        nav_left.setFixedWidth(20)
        nav_left.setStyleSheet(
            f"color: {MUTED}; font-size: 13px; padding: 0; "
            "border: none; background: transparent;"
        )
        nav_left.clicked.connect(self._on_nav_prev)
        row.addWidget(nav_left)

        self._route_lbl = self._make_route_label()
        row.addWidget(self._route_lbl)

        nav_right = QPushButton("›")
        nav_right.setFixedWidth(20)
        nav_right.setStyleSheet(
            f"color: {MUTED}; font-size: 13px; padding: 0; "
            "border: none; background: transparent;"
        )
        nav_right.clicked.connect(self._on_nav_next)
        row.addWidget(nav_right)

        row.addSpacing(12)

        self._forge_btn = QPushButton("Forge Model")
        self._forge_btn.setFixedHeight(22)
        self._forge_btn.setStyleSheet(
            f"QPushButton {{"
            f"  color: {FG}; font-size: 9px; letter-spacing: 1px;"
            f"  background: {CARD2}; border: 1px solid {GOLD};"
            f"  padding: 2px 10px; border-radius: 3px;"
            f"}}"
            f"QPushButton:hover {{ background: {INDIGO}; border-color: {ACC}; }}"
            f"QPushButton:disabled {{ color: {MUTED}; border-color: {BORDER}; }}"
        )
        self._forge_btn.clicked.connect(self._on_forge)
        row.addWidget(self._forge_btn)

        return bar

    @staticmethod
    def _make_route_label() -> QLabel:
        parts = []
        for i, name in enumerate(_ROUTE):
            if i == _ROUTE_IDX:
                parts.append(f'<span style="color:{ACC}; font-weight:bold;">{name}</span>')
            else:
                parts.append(f'<span style="color:{MUTED};">{name}</span>')
        lbl = QLabel("  ·  ".join(parts))
        lbl.setTextFormat(Qt.TextFormat.RichText)
        lbl.setStyleSheet("font-size: 9px; border: none; background: transparent;")
        return lbl

    # ── Status panel ──────────────────────────────────────────────────────────

    def _make_status_panel(self) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet(f"background: {CARD}; border: 1px solid {BORDER}; border-radius: 4px;")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        layout.addWidget(self._sep("STATUS"))

        grid = QHBoxLayout()
        grid.setSpacing(24)

        # MetaClipper column
        mc_col = QVBoxLayout()
        mc_col.setSpacing(3)
        mc_title = QLabel("MetaClipper")
        mc_title.setStyleSheet(f"color: {MUTED}; font-size: 9px; letter-spacing: 1px;")
        mc_col.addWidget(mc_title)
        self._mc_status = QLabel("○  not fitted")
        self._mc_status.setStyleSheet(f"color: {MUTED}; font-size: 9px; font-family: Menlo, monospace;")
        mc_col.addWidget(self._mc_status)
        self._mc_vocab = self._kv_inline("vocab")
        mc_col.addWidget(self._mc_vocab[0])
        self._mc_var   = self._kv_inline("expl_var")
        mc_col.addWidget(self._mc_var[0])
        grid.addLayout(mc_col)

        # D4XGBoost column
        xgb_col = QVBoxLayout()
        xgb_col.setSpacing(3)
        xgb_title = QLabel("D4XGBoostModel")
        xgb_title.setStyleSheet(f"color: {MUTED}; font-size: 9px; letter-spacing: 1px;")
        xgb_col.addWidget(xgb_title)
        self._xgb_status = QLabel("○  not fitted")
        self._xgb_status.setStyleSheet(f"color: {MUTED}; font-size: 9px; font-family: Menlo, monospace;")
        xgb_col.addWidget(self._xgb_status)
        self._xgb_train  = self._kv_inline("n_train")
        xgb_col.addWidget(self._xgb_train[0])
        self._xgb_rmse   = self._kv_inline("val_rmse")
        xgb_col.addWidget(self._xgb_rmse[0])
        grid.addLayout(xgb_col)

        grid.addStretch()
        layout.addLayout(grid)

        # Store val labels for update
        self._mc_vocab_val = self._mc_vocab[1]
        self._mc_var_val   = self._mc_var[1]
        self._xgb_train_val = self._xgb_train[1]
        self._xgb_rmse_val  = self._xgb_rmse[1]

        return panel

    def _kv_inline(self, key: str) -> tuple[QWidget, QLabel]:
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        row = QHBoxLayout(w)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        k = QLabel(key)
        k.setStyleSheet(f"color: {MUTED}; font-size: 8px;")
        v = QLabel("—")
        v.setStyleSheet(f"color: {FG}; font-size: 8px; font-family: Menlo, monospace;")
        row.addWidget(k)
        row.addWidget(v)
        row.addStretch()
        return w, v

    # ── Log panel ─────────────────────────────────────────────────────────────

    def _make_log_panel(self) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet(f"background: {CARD}; border: 1px solid {BORDER}; border-radius: 4px;")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        layout.addWidget(self._sep("LOG"))

        self._log_box = QPlainTextEdit()
        self._log_box.setReadOnly(True)
        self._log_box.setFixedHeight(130)
        self._log_box.setStyleSheet(
            f"QPlainTextEdit {{"
            f"  background: {BG}; color: {FG}; border: none;"
            f"  font-size: 9px; font-family: Menlo, monospace;"
            f"  padding: 4px;"
            f"}}"
        )
        self._log_box.setPlaceholderText("  no log entries yet")
        layout.addWidget(self._log_box)

        return panel

    # ── Feature importance panel ───────────────────────────────────────────────

    def _make_importance_panel(self) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet(f"background: {CARD}; border: 1px solid {BORDER}; border-radius: 4px;")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        layout.addWidget(self._sep("FEATURE IMPORTANCE  (clipper_emb · fold_bits · d4b)"))

        self._fi_lbl = QLabel("—")
        self._fi_lbl.setStyleSheet(
            f"color: {MUTED}; font-size: 9px; font-family: Menlo, monospace;"
        )
        layout.addWidget(self._fi_lbl)

        return panel

    # ── Social coverage panel ─────────────────────────────────────────────────

    def _make_coverage_panel(self) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet(f"background: {CARD}; border: 1px solid {BORDER}; border-radius: 4px;")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        layout.addWidget(self._sep("SOCIAL COVERAGE  (D₂ feature health)"))

        self._cov_lbl = QLabel("Press [Forge Model] or [Refresh Coverage] to compute.")
        self._cov_lbl.setStyleSheet(
            f"color: {MUTED}; font-size: 9px; font-family: Menlo, monospace;"
        )
        self._cov_lbl.setWordWrap(True)
        layout.addWidget(self._cov_lbl)

        cov_btn = QPushButton("Refresh Coverage")
        cov_btn.setFixedHeight(20)
        cov_btn.setStyleSheet(
            f"QPushButton {{"
            f"  color: {MUTED}; font-size: 8px;"
            f"  background: {CARD2}; border: 1px solid {BORDER};"
            f"  padding: 2px 8px; border-radius: 3px;"
            f"}}"
            f"QPushButton:hover {{ color: {FG}; border-color: {INDIGO}; }}"
        )
        cov_btn.clicked.connect(self._refresh_coverage)
        layout.addWidget(cov_btn)

        return panel

    @staticmethod
    def _sep(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: {ACC}; font-size: 8px; letter-spacing: 2px; "
            "border: none; background: transparent;"
        )
        return lbl

    # ── slots ─────────────────────────────────────────────────────────────────

    def _on_nav_prev(self) -> None:
        try:
            self._ctrl.ml_prev_page()
        except AttributeError:
            pass

    def _on_nav_next(self) -> None:
        try:
            self._ctrl.ml_next_page()
        except AttributeError:
            pass

    def _on_forge(self) -> None:
        if self._worker and self._worker.isRunning():
            return
        items = self._library_items()
        if len(items) < 4:
            self._append_log(f"Need ≥ 4 tracks, library has {len(items)}.")
            return
        self._forge_btn.setEnabled(False)
        self._worker = _ForgeWorker(items, parent=self)
        self._worker.log_line.connect(self._append_log)
        self._worker.finished.connect(self._on_forge_done)
        self._worker.error.connect(self._on_forge_error)
        self._worker.start()

    def _on_forge_done(self, result: dict) -> None:
        self._last_result = result
        self._forge_btn.setEnabled(True)

        # Update status panel
        self._mc_status.setText(f"●  fitted  ({result['n_tracks']} tracks)")
        self._mc_status.setStyleSheet(f"color: {METER_OK}; font-size: 9px; font-family: Menlo, monospace;")
        self._mc_vocab_val.setText(f"{result['vocab']:,}")
        self._mc_var_val.setText(f"{result['explained_var']:.3f}")

        self._xgb_status.setText("●  fitted")
        self._xgb_status.setStyleSheet(f"color: {METER_OK}; font-size: 9px; font-family: Menlo, monospace;")
        self._xgb_train_val.setText(str(result["n_train"]))
        self._xgb_rmse_val.setText(f"{result['val_rmse']:.4f}")

        # Feature importance display
        fi = result.get("fi", {})
        em = fi.get("emb_mean",  0.0)
        fo = fi.get("fold_mean", 0.0)
        db = fi.get("d4b_score", 0.0)
        total = em + fo + db or 1.0
        lines = [
            f"emb(36)   {_ascii_bar(em/total, 18)}  {em:.3f}",
            f"fold(8)   {_ascii_bar(fo/total, 18)}  {fo:.3f}",
            f"d4b(1)    {_ascii_bar(db/total, 18)}  {db:.3f}",
        ]
        self._fi_lbl.setText("\n".join(lines))
        self._fi_lbl.setStyleSheet(
            f"color: {FG}; font-size: 9px; font-family: Menlo, monospace;"
        )

        # Write clipper annotations back to meta_cache
        self._write_annotations(result.get("anns", []), result.get("paths", []))

        # Refresh coverage now that we have annotations
        self._refresh_coverage()

    def _on_forge_error(self, msg: str) -> None:
        self._forge_btn.setEnabled(True)
        self._append_log(f"ERROR: {msg}")

    def _append_log(self, line: str) -> None:
        self._log_box.appendPlainText(line)
        sb = self._log_box.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _refresh_coverage(self) -> None:
        try:
            from phi.models.song_derivative import social_coverage
            paths = [p for p, _ in self._library_items()]
            cov   = social_coverage(paths or None)
        except Exception as exc:  # noqa: BLE001
            self._cov_lbl.setText(f"Error: {exc}")
            return

        n = cov.get("n_tracks", 0)
        lines = [f"{n} tracks\n"]
        for field, frac in cov.get("coverage", {}).items():
            bar  = _ascii_bar(frac, 20)
            pct  = frac * 100.0
            col  = METER_OK if frac >= 0.8 else (METER_WARN if frac >= 0.3 else METER_CRIT)
            lines.append(f'<span style="color:{col};">{field:<30}  {bar}  {pct:5.1f}%</span>')

        self._cov_lbl.setTextFormat(Qt.TextFormat.RichText)
        self._cov_lbl.setText("<br>".join(lines))

    def _write_annotations(self, anns: list[dict], paths: list[str]) -> None:
        """Merge clipper annotations into meta_cache (best-effort)."""
        try:
            mc = self._ctrl.meta_cache
        except AttributeError:
            return
        for path, ann in zip(paths, anns):
            try:
                existing = mc.get_annotation(path) or {}
                mc.put_annotation(path, {**existing, **ann})
            except Exception:  # noqa: BLE001
                pass

    # ── checkpoint check ──────────────────────────────────────────────────────

    def _check_checkpoints(self) -> None:
        """Update status panel from saved checkpoints on startup."""
        if _CLIPPER_PATH.exists():
            mtime = datetime.datetime.fromtimestamp(
                _CLIPPER_PATH.stat().st_mtime
            ).strftime("%Y-%m-%d %H:%M")
            self._mc_status.setText(f"●  saved  ({mtime})")
            self._mc_status.setStyleSheet(
                f"color: {MUTED}; font-size: 9px; font-family: Menlo, monospace;"
            )
        if _XGB_PATH.exists():
            mtime = datetime.datetime.fromtimestamp(
                _XGB_PATH.stat().st_mtime
            ).strftime("%Y-%m-%d %H:%M")
            self._xgb_status.setText(f"●  saved  ({mtime})")
            self._xgb_status.setStyleSheet(
                f"color: {MUTED}; font-size: 9px; font-family: Menlo, monospace;"
            )

    # ── helpers ───────────────────────────────────────────────────────────────

    def _library_items(self) -> list[tuple[str, dict]]:
        try:
            lib = self._ctrl.library
            return [
                (path, lib.get_meta(path) or {})
                for path in lib.playlist
            ]
        except AttributeError:
            return []

    # ── room protocol ─────────────────────────────────────────────────────────

    def on_show(self) -> None:
        self._check_checkpoints()

    def on_refresh(self) -> None:
        pass

    def refresh(self, *args, **kwargs) -> None:
        pass

    def sync_transport(
        self,
        title:    str   = "",
        artist:   str   = "",
        playing:  bool  = False,
        pos:      float = 0.0,
        duration: float = 0.0,
    ) -> None:
        self._mini.sync(title, artist, playing, pos, duration)

    def update_transport(self, *args, **kwargs) -> None:
        self.sync_transport(*args, **kwargs)

    def mark_playing(self, path: Optional[str]) -> None:
        pass

    def set_playing(self, path: Optional[str] = None, **_kwargs) -> None:
        pass
