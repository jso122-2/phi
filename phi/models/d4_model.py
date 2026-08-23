# -*- coding: utf-8 -*-
"""phi.models.d4_model — D4 XGBoost regression model (baseline).

Baseline ML model from scribble-002 / dragon curve design:

Feature vector  (45 dimensions):
    [0:36]   clipper_emb   — 36-d reduction from GeminiClipper (6×6 matrix, col-major)
    [36:44]  fold_bits     — 8-bit dragon curve positional encoding
    [44]     d4_b          — D4_B fold-direction score

Target:
    d4_a  — D4_A norm-ratio score  (rolling mean of ‖D3‖/‖D1‖ − D2)

Training:
    GeminiClipper.run_batch()  →  annotation dicts + rolling_d4a target array
    D4XGBoostModel.fit(annotations, rolling_d4a)

Inference:
    PhiModel.run(path, meta)  →  {"d4_pred": float}
    Requires GeminiClipper annotations already in meta (clipper_emb, fold_bits, d4_b).

Checkpoint: joblib dump of the fitted XGBRegressor + feature metadata.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import numpy as np

from phi.models.base import PhiModel

logger = logging.getLogger(__name__)

# Feature layout constants — single source of truth
_EMB_DIM   = 36
_FOLD_DIM  = 8
_FEAT_DIM  = _EMB_DIM + _FOLD_DIM + 1   # 45


def _build_feature_row(ann: dict) -> Optional[np.ndarray]:
    """
    Build a single 45-d feature vector from a GeminiClipper annotation dict.

    Returns None if any required key is missing or malformed.
    """
    try:
        emb   = ann["clipper_emb"]      # list[float] len=36
        bits  = ann["fold_bits"]        # list[float] len=8
        d4_b  = float(ann["d4_b"])      # scalar
    except (KeyError, TypeError, ValueError):
        return None

    if len(emb) != _EMB_DIM or len(bits) != _FOLD_DIM:
        return None

    row = np.empty(_FEAT_DIM, dtype=np.float32)
    row[:_EMB_DIM]              = emb
    row[_EMB_DIM:_EMB_DIM + _FOLD_DIM] = bits
    row[-1]                     = d4_b
    return row


def _build_feature_matrix(
    annotations: list[dict],
) -> tuple[np.ndarray, np.ndarray]:
    """
    Build (X, valid_mask) from a list of annotation dicts.

    Returns:
        X:          ndarray shape (N, 45) — feature matrix (zeros for invalid rows)
        valid_mask: ndarray shape (N,) bool — True where row is usable
    """
    N = len(annotations)
    X = np.zeros((N, _FEAT_DIM), dtype=np.float32)
    valid = np.zeros(N, dtype=bool)
    for i, ann in enumerate(annotations):
        row = _build_feature_row(ann)
        if row is not None:
            X[i] = row
            valid[i] = True
    return X, valid


# ─────────────────────────────────────────────────────────────────────────────
# D4XGBoostModel
# ─────────────────────────────────────────────────────────────────────────────

class D4XGBoostModel(PhiModel):
    """
    XGBoost regressor that predicts D4_A from GeminiClipper features.

    Feature vector (45-d):
        clipper_emb (36) + fold_bits (8) + d4_b (1)

    Target:
        d4_a — rolling mean of ‖D3‖/‖D1‖ − D2 (from DragonCurve)

    Usage:
        # Training
        clipper = GeminiClipper()
        anns, rolling_d4a = clipper.run_batch(items)
        model = D4XGBoostModel()
        model.fit(anns, rolling_d4a)
        model.save("checkpoints/d4_xgb.joblib")

        # Inference (via phi pipeline — clipper must have run first)
        pred = model.run(path, meta)   # meta already has clipper_emb etc.
    """

    name        = "d4_xgboost"
    version     = "1.0.0"
    description = "XGBoost D4_A regressor — dragon curve baseline model"

    # Default XGBoost hyperparameters (tunable via fit())
    _DEFAULT_PARAMS: dict = {
        "n_estimators":     400,
        "max_depth":        6,
        "learning_rate":    0.05,
        "subsample":        0.8,
        "colsample_bytree": 0.8,
        "reg_alpha":        0.1,
        "reg_lambda":       1.0,
        "objective":        "reg:squarederror",
        "n_jobs":           -1,
        "random_state":     42,
    }

    def __init__(self, xgb_params: Optional[dict] = None) -> None:
        self._xgb_params = {**self._DEFAULT_PARAMS, **(xgb_params or {})}
        self._model = None          # fitted XGBRegressor (None before fit)
        self._n_train: int = 0

    # ── Internals ─────────────────────────────────────────────────────────────

    def _make_regressor(self):
        try:
            from xgboost import XGBRegressor  # type: ignore[import]
        except ImportError as exc:
            raise ImportError("xgboost is required: pip install xgboost") from exc
        return XGBRegressor(**self._xgb_params)

    # ── Training ──────────────────────────────────────────────────────────────

    def fit(
        self,
        annotations: list[dict],
        rolling_d4a: np.ndarray,
        eval_frac: float = 0.1,
    ) -> dict:
        """
        Train the XGBoost regressor.

        Args:
            annotations: list of GeminiClipper annotation dicts (one per track)
            rolling_d4a: ndarray shape (N,) — causal rolling mean of D4_A,
                         produced by GeminiClipper.run_batch()
            eval_frac:   fraction of data held out as validation set

        Returns:
            dict with training metadata: n_train, n_val, best_iteration, val_rmse
        """
        assert len(annotations) == len(rolling_d4a), (
            f"annotations ({len(annotations)}) and rolling_d4a ({len(rolling_d4a)}) "
            f"must have the same length"
        )

        X, valid = _build_feature_matrix(annotations)
        y = rolling_d4a.astype(np.float32)

        X = X[valid]
        y = y[valid]
        N = len(X)

        if N < 4:
            raise ValueError(f"Need at least 4 valid samples to train, got {N}")

        # Train / val split (no shuffle — causal order preserved)
        split = max(1, int(N * (1 - eval_frac)))
        X_tr, X_val = X[:split], X[split:]
        y_tr, y_val = y[:split], y[split:]

        regressor = self._make_regressor()
        regressor.fit(
            X_tr,
            y_tr,
            eval_set=[(X_val, y_val)],
            verbose=False,
        )

        self._model = regressor
        self._n_train = split

        val_preds = regressor.predict(X_val)
        val_rmse  = float(np.sqrt(np.mean((val_preds - y_val) ** 2)))

        logger.info(
            "D4XGBoostModel.fit: n_train=%d n_val=%d val_rmse=%.4f",
            split, len(X_val), val_rmse,
        )
        return {
            "n_train":  split,
            "n_val":    len(X_val),
            "val_rmse": val_rmse,
        }

    # ── PhiModel interface ────────────────────────────────────────────────────

    def can_process(self, path: str, meta: dict) -> bool:
        # Requires clipper annotations and a fitted model
        return (
            self._model is not None
            and meta.get("clipper_emb") is not None
            and meta.get("d4_pred") is None
        )

    def run(self, path: str, meta: dict) -> dict:
        """
        Predict D4_A for a single track.

        Requires GeminiClipper annotations already in meta.

        Returns:
            {"d4_pred": float}  — predicted D4_A score, or {} on failure
        """
        if self._model is None:
            logger.warning("D4XGBoostModel.run: model not fitted — call fit() first")
            return {}

        row = _build_feature_row(meta)
        if row is None:
            logger.warning("D4XGBoostModel.run(%s): missing clipper annotations", path)
            return {}

        try:
            pred = float(self._model.predict(row.reshape(1, -1))[0])
            return {"d4_pred": pred}
        except Exception as exc:
            logger.warning("D4XGBoostModel.run(%s) failed: %s", path, exc)
            return {}

    def predict_batch(self, annotations: list[dict]) -> np.ndarray:
        """
        Predict D4_A for a list of annotation dicts.

        Returns:
            ndarray shape (N,) — predicted D4_A (0.0 for invalid rows)
        """
        if self._model is None:
            raise RuntimeError("Model not fitted — call fit() first")
        X, valid = _build_feature_matrix(annotations)
        preds = np.zeros(len(annotations), dtype=np.float32)
        if valid.any():
            preds[valid] = self._model.predict(X[valid]).astype(np.float32)
        return preds

    # ── Feature importance ────────────────────────────────────────────────────

    def feature_importance(self) -> dict:
        """
        Return feature importance scores grouped by component.

        Returns:
            dict with keys: emb_mean, fold_mean, d4b_score
        """
        if self._model is None:
            raise RuntimeError("Model not fitted")
        fi = self._model.feature_importances_    # shape (45,)
        return {
            "emb_mean":   float(fi[:_EMB_DIM].mean()),
            "fold_mean":  float(fi[_EMB_DIM:_EMB_DIM + _FOLD_DIM].mean()),
            "d4b_score":  float(fi[-1]),
            "raw":        fi.tolist(),
        }

    # ── Persistence ───────────────────────────────────────────────────────────

    def save(self, path: str | Path) -> None:
        """Save fitted model to a joblib file."""
        try:
            import joblib  # type: ignore[import]
        except ImportError as exc:
            raise ImportError("joblib is required: pip install joblib") from exc
        if self._model is None:
            raise RuntimeError("Cannot save: model not fitted")
        payload = {
            "model":      self._model,
            "xgb_params": self._xgb_params,
            "n_train":    self._n_train,
            "feat_dim":   _FEAT_DIM,
        }
        joblib.dump(payload, path)
        logger.info("D4XGBoostModel saved → %s", path)

    @classmethod
    def load(cls, path: str | Path) -> "D4XGBoostModel":
        """Load a saved model from a joblib file."""
        try:
            import joblib  # type: ignore[import]
        except ImportError as exc:
            raise ImportError("joblib is required: pip install joblib") from exc
        payload = joblib.load(path)
        inst = cls(xgb_params=payload["xgb_params"])
        inst._model   = payload["model"]
        inst._n_train = payload["n_train"]
        if payload.get("feat_dim") != _FEAT_DIM:
            logger.warning(
                "D4XGBoostModel.load: checkpoint feat_dim=%d != current %d",
                payload["feat_dim"], _FEAT_DIM,
            )
        logger.info("D4XGBoostModel loaded ← %s (n_train=%d)", path, inst._n_train)
        return inst
