# -*- coding: utf-8 -*-
"""phi.ui.qt.rooms.dragon_room — Dragon Curve ML room  (entry point of the ML route).

The dragon curve is the aesthetic and score-normalisation basis for the entire
ML pipeline.  This room is the first step: it projects each track onto the
curve using BPM × Key as the coordinate pair, producing (clipper_x, clipper_y)
that flows downstream through Inference → Forge.

Projection
----------
    x = BPM normalised over [60, 200]      — tempo axis
    y = Camelot wheel slot / 23            — harmonic axis (24 positions)

Auto-anchor: when a track is loaded and no prior anchor exists, the room
computes (x, y) from the track's BPM and key_sig metadata and writes it to
meta_cache immediately.  Tracks with no BPM or key data fall back to (0.5, 0.5).

Manual override: click any point on the curve, then press "Override Position"
to replace the auto-computed anchor with the manually chosen position.
Source is recorded as "bpm_key" (auto) or "manual" in meta_cache.

Layout
------
┌──────────────────────────────────────────────────────────────────────┐
│  DRAGON CURVE     ‹ Dragon · Inference · Forge ›   depth: 8  [−][+]  │
├──────────────────────────────────┬───────────────────────────────────┤
│                                  │  SCORES                           │
│   dragon curve canvas            │  D4_A  +7.0000  ████░░░░          │
│   • ACC/purple   right-turn segs │  D4_B  +7.0000                    │
│   • INDIGO       left-turn segs  │                                   │
│                                  │  FOLD BITS                        │
│   ● violet pulse = playback pos  │  [■][□][■][□][□][■][■][■]         │
│     walks along the curve live   │                                   │
│   ✦ gold dot  = committed query  │  SEGMENT                          │
│   ○ ghost     = hover preview    │  42 / 255   t = 0.164             │
│                                  │  D1  (+1,  0)                     │
│   hover  → live ghost scores     │  D3  ( 7,  4)                     │
│   click  → commit query point    │                                   │
│                                  │  TRACK                            │
│                                  │  ♪ Artist — Title                 │
│                                  │  [  Anchor Track  ]               │
│                                  │  d4_a  —   d4_b  —               │
├──────────────────────────────────┴───────────────────────────────────┤
│  mini transport                                                        │
└──────────────────────────────────────────────────────────────────────┘

Room protocol: on_show(), on_refresh(), sync_transport(), mark_playing()
"""
from __future__ import annotations

from typing import Optional

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from phi.config import ACC, BORDER, CARD2, FG, MUTED
from phi.ui.qt.rooms._dragon_canvas import DragonCurveCanvas
from phi.ui.qt.rooms._dragon_coord import bpm_key_to_unit
from phi.ui.qt.rooms._dragon_panel import DragonInfoPanel
from phi.ui.qt.rooms._mini_transport import MiniTransportWidget


_ROUTE = ["Dragon", "Inference", "Forge"]
_ROUTE_IDX = 0


class MLDragonPage(QWidget):
    """
    Dragon Curve ML room — first entry in the ML route.

    Reactive: the playback cursor walks along the curve in sync with the
    currently playing track (updated every 100 ms via sync_transport).

    Interactive:
        • hover  → ghost preview of D4 scores at that point
        • click  → commit query point (gold dot); enables Anchor
        • Anchor Track → saves clipper_x/y + D4 scores to meta_cache,
                         making this track's position permanent for the
                         downstream Inference / Forge pages

    Navigation: ‹ / › header arrows call ctrl.ml_prev_page() / ml_next_page().
    """

    _MIN_DEPTH = 1
    _MAX_DEPTH = 12

    def __init__(
        self,
        parent: QWidget | None = None,
        ctrl:   object         = None,
    ) -> None:
        super().__init__(parent)
        self._ctrl          = ctrl
        self._depth         = 8
        self._current_path  = ""
        self._current_title = ""
        self._current_artist= ""
        self._last_t        = 0.0
        self._query_seg: Optional[int] = None
        self._build()

    # ── layout ────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._make_header())

        centre = QHBoxLayout()
        centre.setContentsMargins(0, 0, 0, 0)
        centre.setSpacing(0)

        self._canvas = DragonCurveCanvas(depth=self._depth, parent=self)
        self._canvas.queried.connect(self._on_queried)
        self._canvas.hovered.connect(self._on_hovered)
        self._canvas.scatter_hovered.connect(self._on_scatter_hovered)
        centre.addWidget(self._canvas, stretch=1)

        self._info = DragonInfoPanel(parent=self)
        self._info.anchor_requested.connect(self._on_anchor)
        self._info.walk_requested.connect(self._on_curve_walk)
        self._info.arc_shape_changed.connect(self._on_arc_shape_changed)
        self._info.arc_mode_toggled.connect(self._on_arc_mode_toggled)
        centre.addWidget(self._info)

        root.addLayout(centre, stretch=1)

        self._mini = MiniTransportWidget(ctrl=self._ctrl, parent=self)
        root.addWidget(self._mini)

    def _make_header(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(36)
        bar.setStyleSheet(
            f"background: {CARD2}; border-bottom: 1px solid {BORDER};"
        )
        row = QHBoxLayout(bar)
        row.setContentsMargins(14, 0, 10, 0)
        row.setSpacing(8)

        title = QLabel("DRAGON CURVE")
        title.setStyleSheet(
            f"color: {ACC}; font-size: 10px; letter-spacing: 3px; "
            f"border: none; background: transparent;"
        )
        row.addWidget(title)

        row.addStretch()

        nav_left = QPushButton("‹")
        nav_left.setFixedWidth(20)
        nav_left.setStyleSheet(
            f"color: {MUTED}; font-size: 13px; padding: 0; "
            f"border: none; background: transparent;"
        )
        nav_left.clicked.connect(self._on_nav_prev)
        row.addWidget(nav_left)

        self._route_lbl = self._make_route_label()
        row.addWidget(self._route_lbl)

        nav_right = QPushButton("›")
        nav_right.setFixedWidth(20)
        nav_right.setStyleSheet(
            f"color: {MUTED}; font-size: 13px; padding: 0; "
            f"border: none; background: transparent;"
        )
        nav_right.clicked.connect(self._on_nav_next)
        row.addWidget(nav_right)

        row.addSpacing(8)

        depth_lbl = QLabel("depth:")
        depth_lbl.setStyleSheet(
            f"color: {MUTED}; font-size: 9px; border: none; background: transparent;"
        )
        row.addWidget(depth_lbl)

        self._depth_lbl = QLabel(str(self._depth))
        self._depth_lbl.setFixedWidth(18)
        self._depth_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._depth_lbl.setStyleSheet(
            f"color: {FG}; font-size: 10px; font-family: Menlo, monospace; "
            f"border: none; background: transparent;"
        )
        row.addWidget(self._depth_lbl)

        _btn = (
            f"color: {MUTED}; font-size: 13px; padding: 0 5px; "
            f"border: none; background: transparent;"
        )
        btn_dec = QPushButton("−")
        btn_dec.setFixedWidth(22)
        btn_dec.setStyleSheet(_btn)
        btn_dec.clicked.connect(self._on_depth_dec)

        btn_inc = QPushButton("+")
        btn_inc.setFixedWidth(22)
        btn_inc.setStyleSheet(_btn)
        btn_inc.clicked.connect(self._on_depth_inc)

        row.addWidget(btn_dec)
        row.addWidget(btn_inc)

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

    # ── slots ─────────────────────────────────────────────────────────────────

    def _on_queried(self, d4_a: float, d4_b: float, bits: object, seg_idx: int) -> None:
        dc = self._canvas._dc
        D1, D2, D3 = dc.d1_d2_d3(seg_idx)
        self._query_seg = seg_idx
        self._info.update_scores(
            d4_a, d4_b, bits,
            seg_idx, dc.n_segments,
            D1, D3,
            t=self._last_t,
            preview=False,
        )

    def _on_hovered(self, d4_a: float, d4_b: float, bits: object, seg_idx: int) -> None:
        dc = self._canvas._dc
        D1, D2, D3 = dc.d1_d2_d3(seg_idx)
        self._info.update_scores(
            d4_a, d4_b, bits,
            seg_idx, dc.n_segments,
            D1, D3,
            t=self._last_t,
            preview=True,
        )

    def _on_anchor(self) -> None:
        """
        Manually anchor the current track at the committed query point
        (or playback cursor if no query has been made).
        """
        if not self._current_path:
            return

        dc = self._canvas._dc

        if self._query_seg is not None:
            seg = self._query_seg
        else:
            seg = int(max(0, min(dc.n_segments - 1, self._last_t * dc.n_segments)))

        pts = dc.points
        lo  = pts.min(axis=0)
        rng = np.maximum(pts.max(axis=0) - lo, 1e-9)
        mid = (pts[seg] + pts[seg + 1]) * 0.5
        x_n = float((mid[0] - lo[0]) / rng[0])
        y_n = float((mid[1] - lo[1]) / rng[1])

        d4_a = self._compute_and_save_anchor(self._current_path, x_n, y_n, source="manual")
        self._canvas.set_anchor(x_n, y_n)
        self._info.set_anchor_status(anchored=True, source="manual", d4_a=d4_a)

    def _on_curve_walk(self) -> None:
        try:
            self._ctrl.on_curve_sort_toggle()
        except AttributeError:
            pass

    def _on_arc_shape_changed(self, shape_key: str) -> None:
        try:
            from phi.engine.arc_engine import ArcShape
            daemon = getattr(self._ctrl, "curve_daemon", None)
            if daemon is None:
                return
            daemon.arc_engine.shape = ArcShape[shape_key]
        except (AttributeError, KeyError):
            pass

    def _on_arc_mode_toggled(self) -> None:
        try:
            daemon = getattr(self._ctrl, "curve_daemon", None)
            if daemon is None:
                return
            engine = daemon.arc_engine
            engine.active = not engine.active
            if engine.active:
                engine.reset()
                daemon._recent_paths.clear()
            self._info.set_arc_active(engine.active, engine.shape.name)
            self._ctrl._flash(
                f"Arc {'ON' if engine.active else 'OFF'}  —  {engine.shape.value}"
            )
        except AttributeError:
            pass

    def _on_depth_dec(self) -> None:
        new = max(self._MIN_DEPTH, self._depth - 1)
        if new != self._depth:
            self._depth = new
            self._depth_lbl.setText(str(new))
            self._canvas.set_depth(new)

    def _on_depth_inc(self) -> None:
        new = min(self._MAX_DEPTH, self._depth + 1)
        if new != self._depth:
            self._depth = new
            self._depth_lbl.setText(str(new))
            self._canvas.set_depth(new)

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

    # ── room protocol ─────────────────────────────────────────────────────────

    def on_show(self) -> None:
        self._load_scatter()
        self._canvas.update()

    def on_refresh(self) -> None:
        self._load_scatter()

    def refresh(self, *args, **kwargs) -> None:
        self.on_refresh()

    def sync_transport(
        self,
        title:    str   = "",
        artist:   str   = "",
        playing:  bool  = False,
        pos:      float = 0.0,
        duration: float = 0.0,
    ) -> None:
        self._current_title  = title
        self._current_artist = artist

        if duration > 0 and playing:
            t = max(0.0, min(1.0, pos / duration))
            self._last_t = t
            self._canvas.set_playback(t)
            self._info.update_playback_t(t)
        elif not playing:
            self._canvas.set_playback(None)
            self._canvas.set_bpm(None)

        if playing and self._current_path:
            bpm = self._current_track_bpm()
            self._canvas.set_bpm(bpm)

        self._info.update_track(title, artist, has_track=bool(title or artist))
        self._mini.sync(title, artist, playing, pos, duration)

        try:
            self._info.set_curve_walk_active(self._ctrl.queue.curve_walk)
        except AttributeError:
            pass

        try:
            engine = self._ctrl.curve_daemon.arc_engine
            self._info.set_arc_active(engine.active, engine.shape.name)
        except AttributeError:
            pass

    def update_transport(self, *args, **kwargs) -> None:
        self.sync_transport(*args, **kwargs)

    def mark_playing(self, path: Optional[str]) -> None:
        self._current_path = path or ""
        self._query_seg    = None

        if not path:
            self._canvas.set_anchor(None, None)
            self._info.set_anchor_status(anchored=False)
            return

        saved: dict = {}
        try:
            saved = self._ctrl.meta_cache.get_annotation(path) or {}
        except AttributeError:
            pass

        x_n  = saved.get("clipper_x")
        y_n  = saved.get("clipper_y")
        d4_a = saved.get("d4_a")

        if x_n is not None and y_n is not None:
            src = saved.get("anchor_source", "manual")
            self._canvas.set_anchor(float(x_n), float(y_n))
            self._info.set_anchor_status(
                anchored=True,
                source=src,
                d4_a=d4_a,
                bpm=saved.get("clipper_bpm"),
                key_sig=saved.get("clipper_key"),
            )
            return

        track_meta: dict = {}
        try:
            track_meta = self._ctrl.library.get_meta(path) or {}
        except AttributeError:
            pass
        if not track_meta:
            track_meta = saved

        bpm     = track_meta.get("bpm")
        key_sig = track_meta.get("key") or track_meta.get("key_sig")

        if bpm is not None or key_sig is not None:
            x_n, y_n = bpm_key_to_unit(bpm, key_sig)
            d4_a     = self._compute_and_save_anchor(
                path, x_n, y_n,
                source="bpm_key",
                extra={"clipper_bpm": bpm, "clipper_key": key_sig},
            )
            self._canvas.set_anchor(float(x_n), float(y_n))
            self._info.set_anchor_status(
                anchored=True,
                source="auto",
                d4_a=d4_a,
                bpm=bpm,
                key_sig=key_sig,
            )
        else:
            self._canvas.set_anchor(None, None)
            self._info.set_anchor_status(anchored=False)

    def _compute_and_save_anchor(
        self,
        path:   str,
        x_n:    float,
        y_n:    float,
        source: str,
        extra:  Optional[dict] = None,
    ) -> float:
        """Compute D4 scores for (x_n, y_n), write to meta_cache, return d4_a."""
        dc         = self._canvas._dc
        cx, cy     = dc.unit_to_curve(x_n, y_n)
        seg        = dc.nearest_segment(cx, cy)
        D1, D2, D3 = dc.d1_d2_d3(seg)
        d4_a       = dc.score_a(D1, D2, D3)
        d4_b       = dc.score_b(D1, D2, D3)
        bits       = dc.fold_bits(seg)

        payload: dict = {
            "clipper_x":     x_n,
            "clipper_y":     y_n,
            "d4_a":          d4_a,
            "d4_b":          d4_b,
            "fold_bits":     bits.tolist(),
            "anchor_source": source,
            **(extra or {}),
        }
        try:
            existing_ann = self._ctrl.meta_cache.get_annotation(path) or {}
            self._ctrl.meta_cache.put_annotation(path, {**existing_ann, **payload})
        except AttributeError:
            pass

        return float(d4_a)

    # ── scatter + BPM helpers ─────────────────────────────────────────────────

    def _current_track_bpm(self) -> Optional[float]:
        meta: dict = {}
        try:
            meta = self._ctrl.library.get_meta(self._current_path) or {}
        except AttributeError:
            pass
        if not meta:
            try:
                meta = self._ctrl.meta_cache.get(self._current_path) or {}
            except AttributeError:
                pass
        bpm = meta.get("bpm") or meta.get("clipper_bpm")
        try:
            return float(bpm) if bpm else None
        except (TypeError, ValueError):
            return None

    def _load_scatter(self) -> None:
        """
        Load all library tracks that have a clipper_x / clipper_y anchor into
        the canvas scatter overlay.
        """
        playlist_set: set[str] = set()
        try:
            playlist_set = set(self._ctrl.library.playlist)
        except AttributeError:
            pass

        anchored: dict[str, dict] = {}
        try:
            anchored = self._ctrl.meta_cache.get_anchored_annotations("clipper_x") or {}
        except Exception:
            pass

        data: list[dict] = []
        for path, ann in list(anchored.items())[:2000]:
            if playlist_set and path not in playlist_set:
                continue
            x_n = ann.get("clipper_x")
            y_n = ann.get("clipper_y")
            if x_n is None or y_n is None:
                continue

            lib_meta: dict = {}
            try:
                lib_meta = self._ctrl.library.meta_cache.get(path) or {}
            except AttributeError:
                pass

            bpm = lib_meta.get("bpm") or ann.get("clipper_bpm") or 0
            data.append({
                "path":      path,
                "clipper_x": float(x_n),
                "clipper_y": float(y_n),
                "bpm":       float(bpm) if bpm else 0.0,
                "title":     lib_meta.get("title", ""),
                "artist":    lib_meta.get("artist", ""),
                "d4_a":      ann.get("d4_a"),
                "d4_b":      ann.get("d4_b"),
                "fold_bits": ann.get("fold_bits"),
                "zone_id":   ann.get("zone_id", -1),
            })

        self._canvas.load_scatter(data)

    def _on_scatter_hovered(self, meta: dict, path: str) -> None:
        dc   = self._canvas._dc
        bits = meta.get("fold_bits")
        d4_a = meta.get("d4_a")
        d4_b = meta.get("d4_b")

        if bits is not None and d4_a is not None and d4_b is not None:
            x_n = float(meta.get("clipper_x", 0.5))
            y_n = float(meta.get("clipper_y", 0.5))
            cx, cy      = dc.unit_to_curve(x_n, y_n)
            seg         = dc.nearest_segment(cx, cy)
            D1, _D2, D3 = dc.d1_d2_d3(seg)
            self._info.update_scores(
                float(d4_a), float(d4_b),
                np.array(bits, dtype=np.float32),
                seg, dc.n_segments,
                D1, D3,
                preview=True,
            )
        title  = meta.get("title", "")
        artist = meta.get("artist", "")
        self._info.update_track(title, artist, has_track=True)

    def set_playing(self, path: Optional[str] = None, **kwargs) -> None:
        self.mark_playing(path)
