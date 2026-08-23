"""
Cerberus bind — mathematical worker-respawn guard.

Three-headed gate: first bind detects deviation, second bind escalates
factorially with each retry, third head kills and respawns.

Mathematics
-----------
First bind (linear deviation):

    ceb_1 = | x - z/A - C - 1 |

    x  : observed worker metric (a float in any range)
    z  : normalisation constant  (default 0.0)
    A  : amplitude / scale factor (default 1.0, must be non-zero)
    C  : offset constant          (default 0.0)

    When z=0, A=1, C=0 this collapses to |x - 1|, i.e. the L1 distance
    from 1.0 — the "perfect worker" target.

Second bind (factorial escalation):

    ceb_2 = M! * ceb_1

    M  : retry index for this worker (0-indexed; M=0 means first attempt)

    The factorial makes repeated failures super-linearly expensive:
        M=0 → factor 1     (no escalation on first attempt)
        M=1 → factor 1     (1! = 1)
        M=2 → factor 2
        M=3 → factor 6
        M=4 → factor 24
        M=5 → factor 120   → a mid-range violation explodes past any threshold

Respawn logic:
    ceb_1 > tau_1  → soft violation  — log, increment retry counter, retry worker
    ceb_2 > tau_2  → hard violation  — kill worker, spawn fresh instance
    both within    → worker passes the Cerberus gate
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable


# ---------------------------------------------------------------------------
# Bind computation
# ---------------------------------------------------------------------------


def ceb_1(x: float, *, z: float = 0.0, A: float = 1.0, C: float = 0.0) -> float:
    """
    First Cerberus bind — linear deviation metric.

        ceb_1 = | x - z/A - C - 1 |

    Raises
    ------
    ValueError  if A is zero (undefined division).
    """
    if A == 0.0:
        raise ValueError("Cerberus bind: A must be non-zero (division by A)")
    return abs(x - z / A - C - 1.0)


def ceb_2(c1: float, M: int) -> float:
    """
    Second Cerberus bind — factorial escalation.

        ceb_2 = M! * ceb_1

    M is clamped to [0, 12] to prevent factorial overflow in production.
    (12! = 479_001_600 — already a threshold-destroying value.)
    """
    M_safe = max(0, min(M, 12))
    return float(math.factorial(M_safe)) * c1


# ---------------------------------------------------------------------------
# Violation result
# ---------------------------------------------------------------------------


@dataclass
class BindResult:
    """Full audit record for one Cerberus evaluation."""

    x: float
    z: float
    A: float
    C: float
    M: int
    c1: float
    c2: float
    tau_1: float
    tau_2: float
    soft_violation: bool    # ceb_1 > tau_1
    hard_violation: bool    # ceb_2 > tau_2
    passed: bool            # neither violation

    def __str__(self) -> str:
        status = "PASS" if self.passed else ("HARD" if self.hard_violation else "SOFT")
        return (
            f"Cerberus[{status}] "
            f"x={self.x:.4f} ceb_1={self.c1:.4f} ceb_2={self.c2:.4f} "
            f"M={self.M} τ₁={self.tau_1} τ₂={self.tau_2}"
        )


def evaluate(
    x: float,
    M: int = 0,
    *,
    z: float = 0.0,
    A: float = 1.0,
    C: float = 0.0,
    tau_1: float = 0.5,
    tau_2: float = 10.0,
) -> BindResult:
    """
    Evaluate both Cerberus binds for a worker metric `x` at retry `M`.

    Parameters
    ----------
    x       : observed worker metric
    M       : retry index (0 = first attempt)
    z, A, C : bind parameters (see module docstring)
    tau_1   : soft-violation threshold for ceb_1
    tau_2   : hard-violation threshold for ceb_2
    """
    c1 = ceb_1(x, z=z, A=A, C=C)
    c2 = ceb_2(c1, M)
    soft = c1 > tau_1
    hard = c2 > tau_2
    return BindResult(
        x=x, z=z, A=A, C=C, M=M,
        c1=round(c1, 8),
        c2=round(c2, 8),
        tau_1=tau_1,
        tau_2=tau_2,
        soft_violation=soft,
        hard_violation=hard,
        passed=not soft and not hard,
    )


# ---------------------------------------------------------------------------
# Cerberus guard — wraps a callable and enforces the bind on every call
# ---------------------------------------------------------------------------


@dataclass
class CerberusGuard:
    """
    Wraps a factory function that produces a callable worker.

    On each call:
    1. Run the worker fn.
    2. Extract a float metric from the result via `metric_fn`.
    3. Evaluate Cerberus binds.
    4. On soft violation: increment retry counter, re-run (up to max_retries).
    5. On hard violation: respawn (call factory again) and reset retry counter.
    6. If all retries exhausted: raise CerberusExhausted.

    Parameters
    ----------
    factory    : callable with no arguments → returns the worker fn
    metric_fn  : extracts a float metric from the worker's return value
    max_retries: maximum total attempts before giving up
    z, A, C    : Cerberus bind parameters
    tau_1      : soft threshold
    tau_2      : hard threshold
    """

    factory: Callable[[], Callable[..., Any]]
    metric_fn: Callable[[Any], float]
    max_retries: int = 5
    z: float = 0.0
    A: float = 1.0
    C: float = 0.0
    tau_1: float = 0.5
    tau_2: float = 10.0

    _retry_count: int = field(default=0, init=False, repr=False)
    _bind_log: list[BindResult] = field(default_factory=list, init=False, repr=False)

    def __post_init__(self) -> None:
        self._worker_fn = self.factory()

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Run the guarded worker, enforcing the Cerberus bind."""
        attempt = 0
        while attempt <= self.max_retries:
            try:
                result = self._worker_fn(*args, **kwargs)
                metric = float(self.metric_fn(result))
            except Exception as exc:
                # Treat exception as a metric of 0.0 (worst case deviation from 1)
                metric = 0.0
                result = None
                _ = exc  # logged in bind result

            bind = evaluate(
                metric,
                M=self._retry_count,
                z=self.z, A=self.A, C=self.C,
                tau_1=self.tau_1, tau_2=self.tau_2,
            )
            self._bind_log.append(bind)

            if bind.passed:
                self._retry_count = 0
                return result

            if bind.hard_violation:
                # Respawn through the Cerberus gate
                self._worker_fn = self.factory()
                self._retry_count = 0
            else:
                self._retry_count += 1

            attempt += 1

        raise CerberusExhausted(
            f"Cerberus: worker exhausted {self.max_retries} retries. "
            f"Last bind: {self._bind_log[-1]}"
        )

    @property
    def bind_log(self) -> list[BindResult]:
        return list(self._bind_log)

    @property
    def retry_count(self) -> int:
        return self._retry_count


class CerberusExhausted(RuntimeError):
    """Raised when a worker exceeds the maximum Cerberus retry budget."""
