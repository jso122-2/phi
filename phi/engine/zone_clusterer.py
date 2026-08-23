# -*- coding: utf-8 -*-
"""phi.engine.zone_clusterer — background k-means clustering on anchored tracks.

Partitions the anchored track library into 8 zones using k-means on the
4-dimensional feature space:

    [clipper_x, clipper_y, d4_a / 20.0, d4_b / 20.0]

The first two dimensions are the BPM × Key projection in [0,1]²; the last two
normalise the dragon-curve D4 scores (range ≈ [0, 20]) into the same scale.

Zones are indexed 0–7 to match the 8 harmonic shards in the CAIRRN ring.
Zone assignment is written back to the ``annotations`` table of MetaCache and
emitted via the ``clustered`` signal for in-memory caching in CurveDaemon.

Also reads the playback log (``~/.phi/logs/playback_*.jsonl``) to build an 8×8
zone-to-zone transition matrix.  This is exposed for future use (queue ranking,
arc scoring, etc.) but not yet wired into any scoring path.

Minimum 10 anchored tracks required to trigger clustering; with fewer, the
thread exits silently.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from sklearn.cluster import KMeans
from PySide6.QtCore import QThread, Signal

from phi.config import PHI_DIR

if TYPE_CHECKING:
    from phi.meta.cache import MetaCache
    from phi.core.library import Library

log = logging.getLogger("phi.zone_clusterer")

_LOG_DIR     = PHI_DIR / "logs"
_MIN_TRACKS  = 10
_N_ZONES     = 8
_MAX_PATHS   = 5_000   # cap to avoid runaway SQL reads on huge libraries
_KMEANS_SEED = 42


class ZoneClusterer(QThread):
    """Background thread: cluster anchored tracks into 8 zones.

    Signals
    -------
    clustered(zone_map, transition_matrix)
        zone_map          : dict[str, int]  — {path: zone_id (0–7)}
        transition_matrix : np.ndarray[8,8] — T[i,j] = P(zone_j | was in zone_i)
                            from playback-log history.  Rows sum to 1 (or 0 if
                            no transitions observed for that zone).

    Usage
    -----
    Instantiate once in CurveDaemon and call ``start_if_ready()`` on each
    ``on_library_refresh()`` event.  The thread self-exits when done.

    Args:
        meta_cache : App-wide ``MetaCache`` instance.
        library    : App-wide ``Library`` instance.
        parent     : Optional Qt parent.
    """

    # zone_map: {path: zone_id},  T: ndarray[8,8]
    clustered = Signal(dict, object)

    def __init__(
        self,
        meta_cache: "MetaCache",
        library:    "Library",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._meta_cache = meta_cache
        self._library    = library

    # ── public API ────────────────────────────────────────────────────────────

    def start_if_ready(self) -> None:
        """Start the clustering thread if ≥ _MIN_TRACKS anchored and not running."""
        if self.isRunning():
            log.debug("ZoneClusterer already running — skipping start")
            return
        self.start()

    # ── QThread.run ───────────────────────────────────────────────────────────

    def run(self) -> None:
        """Main background work: load → cluster → write → emit."""
        try:
            self._run_inner()
        except Exception:
            log.warning("ZoneClusterer failed", exc_info=True)

    def _run_inner(self) -> None:
        paths = list(self._library.playlist)[:_MAX_PATHS]

        # ── 1. Load anchored tracks from annotations ──────────────────────────
        anchored: list[dict] = []
        for path in paths:
            ann = self._meta_cache.get_annotation(path)
            if not ann:
                continue
            cx = ann.get("clipper_x")
            cy = ann.get("clipper_y")
            if cx is None or cy is None:
                continue
            anchored.append({
                "path":      path,
                "clipper_x": float(cx),
                "clipper_y": float(cy),
                "d4_a":      float(ann.get("d4_a") or 10.0),
                "d4_b":      float(ann.get("d4_b") or 10.0),
            })

        n = len(anchored)
        log.debug("ZoneClusterer: %d anchored tracks found", n)

        if n < _MIN_TRACKS:
            log.debug(
                "ZoneClusterer: need %d anchored tracks, have %d — skipping",
                _MIN_TRACKS, n,
            )
            return

        # ── 2. Feature matrix: [x, y, d4_a/20, d4_b/20] ─────────────────────
        X = np.array(
            [
                [
                    t["clipper_x"],
                    t["clipper_y"],
                    t["d4_a"] / 20.0,
                    t["d4_b"] / 20.0,
                ]
                for t in anchored
            ],
            dtype=np.float32,
        )

        k = min(_N_ZONES, n)
        km = KMeans(n_clusters=k, random_state=_KMEANS_SEED, n_init=5)
        labels: np.ndarray = km.fit_predict(X)

        zone_map: dict[str, int] = {
            t["path"]: int(label)
            for t, label in zip(anchored, labels)
        }

        # ── 3. Write zone_ids back to annotations ─────────────────────────────
        ann_updates: dict[str, dict] = {}
        for t, label in zip(anchored, labels):
            ann = self._meta_cache.get_annotation(t["path"]) or {}
            ann["zone_id"] = int(label)
            ann_updates[t["path"]] = ann

        if ann_updates:
            self._meta_cache.put_many_annotations(ann_updates)
            log.debug("ZoneClusterer: wrote %d zone_id annotations", len(ann_updates))

        # ── 4. Build transition matrix from playback logs ─────────────────────
        T = self._build_transition_matrix(zone_map)

        # ── 5. Emit ───────────────────────────────────────────────────────────
        self.clustered.emit(zone_map, T)
        log.info(
            "ZoneClusterer: clustered %d tracks into %d zones", n, k
        )

    # ── transition matrix ─────────────────────────────────────────────────────

    def _build_transition_matrix(self, zone_map: dict[str, int]) -> np.ndarray:
        """Build an 8×8 row-normalised transition matrix from playback logs.

        Reads all ``~/.phi/logs/playback_*.jsonl`` files.  Each adjacent pair
        of ``play`` events contributes one transition: zone_map[prev] → zone_map[cur].

        Returns:
            T[i,j] = P(zone_j | zone_i) from playback history.
            Rows with no observed transitions remain at 0 (not normalised).
        """
        counts = np.zeros((_N_ZONES, _N_ZONES), dtype=np.float64)

        log_files = sorted(_LOG_DIR.glob("playback_*.jsonl")) if _LOG_DIR.exists() else []
        prev_path: str | None = None

        for log_file in log_files:
            try:
                lines = log_file.read_text(encoding="utf-8").splitlines()
            except OSError:
                continue

            for line in lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if event.get("event") == "skip":
                    prev_path = None   # skip breaks the arc
                    continue

                if event.get("event") == "play":
                    cur_path = event.get("path", "")
                    if prev_path and prev_path in zone_map and cur_path in zone_map:
                        i = zone_map[prev_path]
                        j = zone_map[cur_path]
                        counts[i, j] += 1.0
                    prev_path = cur_path

        # Row-normalise
        row_sums = counts.sum(axis=1, keepdims=True)
        T = np.where(row_sums > 0, counts / row_sums, 0.0)
        return T
