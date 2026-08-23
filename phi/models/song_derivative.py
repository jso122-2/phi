# -*- coding: utf-8 -*-
"""phi.models.song_derivative — hierarchical XGBoost derivative scorer.

Computes four derivative scores (D_1 → D_4) for every song in the library.
All input features are percentile-rank quantized to [0, 1] so that features
measured in different units (Hz, BPM, listener counts) compete on equal footing.

Architecture
------------

            D_4  (master — rolling mean of D_3 across sorted library)
          /      \\
       D_1         D_2      (two XGBoost arms)
          \\      /
            D_3  (inbetween mean of D_1 and D_2)

Dragon-curve fold:
  D_1 = XGBoost on acoustic + tonal features  → raw acoustic quality
  D_2 = XGBoost on social + D_1 as context   → "fold" of D_1 into social space
  D_3 = (D_1 + D_2) / 2                       → inbetween of the two arms
  D_4 = rolling_mean(D_3, window)             → smoothed master curve across library

D_4 is the primitive handed to subsequent ML systems (e.g. OctopusOrganizer,
PhiGraph embeddings, TrackRanker feature augmentation).

Usage (CLI)
-----------
  python -m phi.models.song_derivative
  python -m phi.models.song_derivative --out /tmp/scores.json

Usage (Python)
--------------
  from phi.models.song_derivative import SongDerivativeModel
  model  = SongDerivativeModel()
  scores = model.score_library()          # dict[path, {d1, d2, d3, d4}]
"""
from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path
from typing import Optional

import numpy as np

# XGBoost 3.x + macOS: pthread_mutex_init fails when OpenMP tries to
# spawn multiple threads inside a macOS sandbox context.
os.environ.setdefault("OMP_NUM_THREADS", "1")

from phi.models._derivative_features import (
    GROUP_A,
    GROUP_B,
    _ALL_FEATURE_COLS,
    _assemble_rows,
    social_coverage,
)
from phi.models._derivative_loaders import _load_state

# Re-export public surface
__all__ = [
    "SongDerivativeModel",
    "score_library",
    "social_coverage",
    "GROUP_A",
    "GROUP_B",
]


# ── Rolling mean ──────────────────────────────────────────────────────────────

def _rolling_mean(values: np.ndarray, window: int) -> np.ndarray:
    """
    Rolling mean with equal-weight window, sorted by value order.

    The output traces the smooth curve across the sorted library
    (D_4 "as the curve mutates").
    """
    n      = len(values)
    result = np.empty(n, dtype=np.float64)
    hw     = window // 2
    for i in range(n):
        lo = max(0, i - hw)
        hi = min(n, i + hw + 1)
        result[i] = np.nanmean(values[lo:hi])
    return result


# ── Core model ────────────────────────────────────────────────────────────────

class SongDerivativeModel:
    """
    Four-derivative hierarchical scorer for a phi music library.

    Parameters
    ----------
    window_frac   Fraction of library used as D_4 rolling window (default 0.15)
    n_estimators  XGBoost trees per model (default 100)
    max_depth     XGBoost tree depth (default 4)
    """

    def __init__(
        self,
        window_frac:  float = 0.15,
        n_estimators: int   = 100,
        max_depth:    int   = 4,
    ) -> None:
        self.window_frac  = window_frac
        self.n_estimators = n_estimators
        self.max_depth    = max_depth
        self._a_idx = [_ALL_FEATURE_COLS.index(c) for c in GROUP_A]
        self._b_idx = [_ALL_FEATURE_COLS.index(c) for c in GROUP_B]

    def score_library(
        self,
        paths: Optional[list[str]] = None,
    ) -> dict[str, dict[str, float]]:
        """
        Score all (or specified) library tracks.

        Returns
        -------
        dict[path, {d1, d2, d3, d4, target}]
        """
        try:
            from xgboost import XGBRegressor
        except ImportError:
            raise ImportError("xgboost is required: pip install xgboost")

        if paths is None:
            state = _load_state()
            paths = [p for p in state.get("playlist", []) if Path(p).exists()]

        if not paths:
            return {}

        X_q, y, valid = _assemble_rows(paths)
        n = len(valid)
        if n == 0:
            return {}

        Xa_full = X_q[:, self._a_idx]
        Xb_full = X_q[:, self._b_idx]

        Xa, _a_live = self._drop_dead_cols(Xa_full)
        Xb, _b_live = self._drop_dead_cols(Xb_full)

        y_valid  = y[~np.isnan(y)]
        y_median = float(np.median(y_valid)) if len(y_valid) > 0 else 0.5
        y_train  = np.where(np.isnan(y), y_median, y)

        # D_1 — acoustic derivative
        if Xa.shape[1] == 0:
            d1 = np.full(n, 0.5, dtype=np.float64)
        else:
            m1 = XGBRegressor(
                n_estimators  = self.n_estimators,
                max_depth     = self.max_depth,
                learning_rate = 0.1,
                subsample     = 0.8,
                tree_method   = "hist",
                nthread       = 1,
                random_state  = 42,
                verbosity     = 0,
            )
            a_has_data = ~np.isnan(Xa).all(axis=1)
            m1.fit(Xa[a_has_data], y_train[a_has_data])
            d1 = self._norm(m1.predict(Xa).astype(np.float64))

        # D_2 — social derivative (folds D_1 in as context)
        Xb_folded = np.concatenate([Xb, d1.reshape(-1, 1)], axis=1)

        if Xb_folded.shape[1] <= 1:
            d2 = d1.copy()
        else:
            m2 = XGBRegressor(
                n_estimators  = self.n_estimators,
                max_depth     = self.max_depth,
                learning_rate = 0.1,
                subsample     = 0.8,
                tree_method   = "hist",
                nthread       = 1,
                random_state  = 43,
                verbosity     = 0,
            )
            b_has_data = ~np.isnan(Xb_folded).all(axis=1)
            m2.fit(Xb_folded[b_has_data], y_train[b_has_data])
            d2 = self._norm(m2.predict(Xb_folded).astype(np.float64))

        # D_3 — inbetween mean
        d3 = (d1 + d2) / 2.0

        # D_4 — rolling mean across sorted library
        window  = max(5, int(n * self.window_frac))
        order   = np.argsort(d3)
        d3_sort = d3[order]
        d4_sort = _rolling_mean(d3_sort, window)
        d4      = np.empty(n, dtype=np.float64)
        d4[order] = d4_sort

        results: dict[str, dict[str, float]] = {}
        for i, path in enumerate(valid):
            results[path] = {
                "d1":     round(float(d1[i]),  4),
                "d2":     round(float(d2[i]),  4),
                "d3":     round(float(d3[i]),  4),
                "d4":     round(float(d4[i]),  4),
                "target": round(float(y[i]), 4) if not math.isnan(y[i]) else None,
            }
        return results

    @staticmethod
    def _norm(v: np.ndarray) -> np.ndarray:
        lo, hi = v.min(), v.max()
        if hi == lo:
            return np.full_like(v, 0.5)
        return (v - lo) / (hi - lo)

    @staticmethod
    def _drop_dead_cols(X: np.ndarray) -> tuple[np.ndarray, list[int]]:
        """Remove all-NaN columns (XGBoost hist method can segfault on these)."""
        live = [j for j in range(X.shape[1]) if not np.isnan(X[:, j]).all()]
        if not live:
            return np.empty((X.shape[0], 0), dtype=X.dtype), []
        return X[:, live], live


# ── Convenience wrapper ───────────────────────────────────────────────────────

def score_library(paths: Optional[list[str]] = None) -> dict[str, dict[str, float]]:
    """Score all library tracks with default parameters."""
    return SongDerivativeModel().score_library(paths)


# ── CLI ───────────────────────────────────────────────────────────────────────

def _main(argv: list[str] | None = None) -> None:
    import argparse

    parser = argparse.ArgumentParser(
        prog="python -m phi.models.song_derivative",
        description="Compute D_1 → D_4 hierarchical derivative scores for all library tracks.",
    )
    parser.add_argument(
        "--out", "-o", type=Path, default=None,
        help="Write scores to JSON file (default: print to stdout)",
    )
    parser.add_argument(
        "--window", type=float, default=0.15,
        help="D_4 rolling window as fraction of library size (default: 0.15)",
    )
    parser.add_argument(
        "--top", type=int, default=20,
        help="Print top N tracks by D_4 when not writing to file (default: 20)",
    )
    parser.add_argument(
        "--coverage", action="store_true",
        help="Print GROUP_B social feature coverage and exit",
    )
    args = parser.parse_args(argv)

    if args.coverage:
        cov = social_coverage()
        n = cov["n_tracks"]
        print(f"D_2 social coverage report — {n} tracks\n")
        tier1 = ["year", "duration", "artist_lib_count", "album_lib_count"]
        tier2 = [f for f in GROUP_B if f not in tier1]
        print("  Tier 1 — library-context (always available):")
        for f in tier1:
            pct = cov["coverage"].get(f, 0.0)
            bar = "█" * int(pct * 20) + "░" * (20 - int(pct * 20))
            print(f"    {f:<30}  {bar}  {pct*100:5.1f}%")
        print("\n  Tier 2 — external API (enrichment-dependent):")
        for f in tier2:
            pct = cov["coverage"].get(f, 0.0)
            bar = "█" * int(pct * 20) + "░" * (20 - int(pct * 20))
            print(f"    {f:<30}  {bar}  {pct*100:5.1f}%")
        sys.exit(0)

    print("Loading library and computing derivatives…", flush=True)
    model  = SongDerivativeModel(window_frac=args.window)
    scores = model.score_library()

    if not scores:
        print("No tracks found.  Run phi at least once to populate the library.",
              file=sys.stderr)
        sys.exit(1)

    n = len(scores)
    print(f"Scored {n} tracks.", flush=True)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(scores, indent=2, ensure_ascii=False))
        print(f"Scores written to {args.out}")
    else:
        ranked = sorted(scores.items(), key=lambda kv: -kv[1]["d4"])[:args.top]
        header = f"{'D4':>6}  {'D3':>6}  {'D1':>6}  {'D2':>6}  Track"
        print("\n" + header)
        print("-" * len(header))
        for path, s in ranked:
            name = os.path.basename(path)[:50]
            print(f"{s['d4']:6.3f}  {s['d3']:6.3f}  {s['d1']:6.3f}  {s['d2']:6.3f}  {name}")


if __name__ == "__main__":
    _main()
