"""F_TP_RAR wrap and skip/time/confidence extractors."""
from __future__ import annotations

from datetime import datetime

from workers.cairrn.formulas import f_secondary_model_select, f_tp_rar

from ._constants import NOVELTY_HALF_LIFE, TP_RAR_LAMBDA


def tp_rar_score(
    c_e: float,
    cl_e: float,
    dt: float,
    p: float,
    lam: float = TP_RAR_LAMBDA,
    conf_ma: float = 1.0,
) -> float:
    """F_TP_RAR with λ from novelty half-life. Raises nothing; NaN is not produced."""
    return f_tp_rar(float(c_e), float(cl_e), lam, float(dt), float(p), conf_ma)


def _confidence_level(ann: dict, stats: dict) -> float:
    """cl_E from key/BPM confidence and completion. Neutral 0.5 if unknown."""
    vals: list[float] = []
    for key in ("key_confidence", "bpm_confidence"):
        v = ann.get(key)
        if v is None:
            continue
        try:
            vals.append(max(0.0, min(1.0, float(v))))
        except (TypeError, ValueError):
            pass
    cr = stats.get("completion_rate")
    if cr is not None:
        try:
            vals.append(max(0.0, min(1.0, float(cr))))
        except (TypeError, ValueError):
            pass
    if not vals:
        return 0.5
    return sum(vals) / len(vals)


def _time_delta(stats: dict) -> float:
    """Δt in novelty half-lives plus abandon fraction (1 − completion_rate)."""
    days_hl = 0.0
    last_played = stats.get("last_played")
    if last_played:
        try:
            last_dt = datetime.fromisoformat(last_played)
            days = (datetime.now() - last_dt).total_seconds() / 86400.0
            days_hl = max(0.0, days / NOVELTY_HALF_LIFE)
        except (ValueError, TypeError):
            days_hl = 0.0
    abandon = 0.0
    cr = stats.get("completion_rate")
    if cr is not None:
        try:
            abandon = max(0.0, min(1.0, 1.0 - float(cr)))
        except (TypeError, ValueError):
            abandon = 0.0
    return days_hl + abandon


def _skip_pressure(stats: dict) -> float:
    """p = skip_count / plays in [0, 1]. 0 if never played."""
    try:
        plays = int(stats.get("plays", 0) or 0)
        skips = int(stats.get("skip_count", 0) or 0)
    except (TypeError, ValueError):
        return 0.0
    if plays <= 0:
        return 0.0
    return max(0.0, min(1.0, skips / plays))


def keep_fill(pairs: list[tuple[str, float]], ma_floor: float) -> list[str]:
    """Paths at/above mean first, then the rest. Order inside each group preserved."""
    if not pairs:
        return []
    vals = [v for _p, v in pairs]
    ma = sum(vals) / len(vals)
    if abs(ma) < ma_floor:
        ma = ma_floor
    kept = [p for p, v in pairs if not f_secondary_model_select(v, ma)]
    rest = [p for p, v in pairs if f_secondary_model_select(v, ma)]
    return kept + rest
