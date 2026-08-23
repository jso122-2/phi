"""
Bounded attractor simulations — Scribble-1 math.

Key facts encoded here
----------------------
d/dx(-e^x) = -e^x
  The negative exponential is closed under differentiation: its derivative
  is itself (sign preserved). This means no finite fixed point is stable
  under direct iteration of -e^x — the map diverges everywhere.

±1.96 as stable states
  1.96 is the 95 % Gaussian z-score: P(-1.96 < Z < 1.96) ≈ 0.95.
  It emerges as a *natural stability boundary* for normalised systems.

  To manufacture ±1.96 as attractors we use a symmetric double-well
  potential whose minima sit at ±α (α = 1.96):

      V(x)  = (x² - α²)²
      V'(x) = 4x(x² - α²)   ← gradient (force)

  Gradient-descent iteration:
      x_{n+1} = x_n - lr · V'(x_n)

  Fixed points of V' are x = 0 (unstable saddle) and x = ±α (stable).
  Stability check: V''(±α) = 4(3α² - α²) = 8α² > 0  ✓

Negative-exponential map (for reference)
  f(x)   = -e^x,   f'(x) = -e^x
  |f'(x)| = e^x > 1 for all x > 0  → no stable fixed point in ℝ⁺.
  The map is included here so you can watch it diverge and contrast with
  the double-well.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Callable


ALPHA: float = 1.96  # attractor locations ±α


# ---------------------------------------------------------------------------
# Double-well potential
# ---------------------------------------------------------------------------

def potential(x: float, alpha: float = ALPHA) -> float:
    """V(x) = (x² - α²)²  — minima at ±α."""
    return (x**2 - alpha**2) ** 2


def potential_grad(x: float, alpha: float = ALPHA) -> float:
    """V'(x) = 4x(x² - α²)."""
    return 4.0 * x * (x**2 - alpha**2)


def potential_hess(x: float, alpha: float = ALPHA) -> float:
    """V''(x) = 4(3x² - α²)."""
    return 4.0 * (3.0 * x**2 - alpha**2)


def stability_at(x: float, alpha: float = ALPHA) -> str:
    """Return 'stable', 'unstable', or 'saddle' based on V''."""
    h = potential_hess(x, alpha)
    if abs(potential_grad(x, alpha)) > 1e-9:
        return "not a fixed point"
    return "stable" if h > 0 else "unstable"


# ---------------------------------------------------------------------------
# Negative-exponential map
# ---------------------------------------------------------------------------

def neg_exp(x: float) -> float:
    """f(x) = -e^x.  Note: f'(x) = -e^x = f(x)."""
    return -math.exp(x)


def neg_exp_deriv(x: float) -> float:
    """f'(x) = -e^x  (same as f — closed under differentiation)."""
    return neg_exp(x)


# Fixed point of f(x) = -e^x: x* = -W(1) where W is the Lambert W function.
# Numerically x* ≈ -0.56714329...  Verify: -e^(-0.56714) ≈ -0.56714. ✓
# |f'(x*)| = e^(x*) = e^(-W(1)) = W(1) ≈ 0.5671 < 1  → stable fixed point.
NEG_EXP_FIXED_POINT: float = -0.5671432904097838


# ---------------------------------------------------------------------------
# Simulation engine
# ---------------------------------------------------------------------------

@dataclass
class Trajectory:
    x0: float
    steps: list[float] = field(default_factory=list)
    converged: bool = False
    converged_at: float | None = None

    def record(self, x: float) -> None:
        self.steps.append(x)


def run_double_well(
    x0: float,
    lr: float = 0.05,
    max_step: float = 0.5,
    max_iter: int = 2000,
    tol: float = 1e-6,
    alpha: float = ALPHA,
) -> Trajectory:
    """
    Gradient descent on V(x) = (x² - α²)².

    Converges to +α if x0 > 0, -α if x0 < 0, unstable at x0 = 0.
    Uses a capped step size (`max_step`) to stay stable for large |x0|.

    Parameters
    ----------
    x0       : starting position
    lr       : nominal learning rate
    max_step : maximum allowed step per iteration (prevents 2-cycles at large |x0|)
    max_iter : iteration cap
    tol      : convergence threshold on |V'(x)|
    alpha    : well locations (default 1.96)
    """
    traj = Trajectory(x0=x0)
    x = x0
    traj.record(x)

    for _ in range(max_iter):
        g = potential_grad(x, alpha)
        raw_step = lr * g
        step = max(-max_step, min(max_step, raw_step))
        x = x - step
        traj.record(x)
        if abs(g) < tol:
            traj.converged = True
            traj.converged_at = x
            break

    return traj


def run_neg_exp_map(
    x0: float,
    max_iter: int = 200,
    clip: float = 50.0,
    tol: float = 1e-8,
) -> Trajectory:
    """
    Iterate f(x) = -e^x.

    Despite d/dx(-e^x) = -e^x, the map *does* converge for most starting
    points to the stable fixed point x* = -W(1) ≈ -0.5671 (Lambert W),
    because |f'(x*)| = e^(x*) = W(1) ≈ 0.567 < 1.

    For very large positive x0 the exponential overflows before convergence,
    so values are clipped at ±clip.
    """
    traj = Trajectory(x0=x0)
    x = x0
    traj.record(x)

    for _ in range(max_iter):
        try:
            x_next = neg_exp(x)
        except OverflowError:
            x_next = -clip
        x_next = max(-clip, min(clip, x_next))
        traj.record(x_next)
        if abs(x_next - x) < tol:
            traj.converged = True
            traj.converged_at = x_next
            break
        x = x_next

    return traj


# ---------------------------------------------------------------------------
# Batch runner
# ---------------------------------------------------------------------------

def sweep_initial_conditions(
    x0_values: list[float],
    sim_fn: Callable[..., Trajectory],
    **kwargs,
) -> list[Trajectory]:
    """Run sim_fn for each starting point and return all trajectories."""
    return [sim_fn(x0, **kwargs) for x0 in x0_values]


# ---------------------------------------------------------------------------
# Summary helpers
# ---------------------------------------------------------------------------

def summarise(traj: Trajectory, alpha: float = ALPHA) -> dict:
    """Return a human-readable summary dict for a trajectory."""
    final = traj.steps[-1] if traj.steps else traj.x0
    return {
        "x0": traj.x0,
        "steps": len(traj.steps),
        "final_x": round(final, 6),
        "converged": traj.converged,
        "target": f"+{alpha}" if final > 0 else f"-{alpha}",
        "error_to_attractor": round(abs(abs(final) - alpha), 6),
    }


# ---------------------------------------------------------------------------
# Overdamped Langevin + Kramers MFPT
# ---------------------------------------------------------------------------

def kramers_rate(
    noise_scale: float,
    lr: float = 0.05,
    alpha: float = ALPHA,
) -> dict:
    """
    Overdamped Kramers escape rate for V(x) = (x² − α²)² (γ = 1).

        λ = (ω₀ · ωₛ / 2π) · exp(−ΔV / D)

    ω₀ = √V″(±α) = 2√2·α,  ωₛ = √|V″(0)| = 2α,  ΔV = α⁴,  D = noise_scale².
    τ_steps = (1/λ) / lr  converts continuous time to discrete Langevin steps.
    """
    D = noise_scale ** 2
    delta_V = alpha ** 4
    omega_0 = math.sqrt(potential_hess(alpha, alpha))       # √(8α²) = 2√2 α
    omega_s = math.sqrt(abs(potential_hess(0.0, alpha)))    # √(4α²) = 2α

    if D <= 0.0:
        return {
            "rate": 0.0,
            "tau": float("inf"),
            "tau_steps": float("inf"),
            "delta_V": delta_V,
            "exponent": float("inf"),
            "omega_0": omega_0,
            "omega_s": omega_s,
            "D": D,
        }

    exponent = delta_V / D
    rate = (omega_0 * omega_s / (2.0 * math.pi)) * math.exp(-exponent)
    tau = (1.0 / rate) if rate > 0.0 else float("inf")
    tau_steps = (tau / lr) if lr > 0.0 else float("inf")
    return {
        "rate": rate,
        "tau": tau,
        "tau_steps": tau_steps,
        "delta_V": delta_V,
        "exponent": exponent,
        "omega_0": omega_0,
        "omega_s": omega_s,
        "D": D,
    }


def run_langevin(
    x0: float,
    noise_scale: float = 2.0,
    lr: float = 0.05,
    max_iter: int = 500,
    alpha: float = ALPHA,
    seed: int | None = None,
) -> Trajectory:
    """
    Discrete overdamped Langevin on V(x) = (x² − α²)²:

        x_{n+1} = x_n − lr · V'(x_n) + √(2·D·lr) · ξ    ξ ~ N(0,1)

    noise_scale=0 recovers deterministic gradient descent.
    Positions are clipped to ±clip so a large noise draw cannot overflow V'.
    """
    rng = random.Random(seed)
    D = noise_scale ** 2
    noise_amp = math.sqrt(2.0 * D * lr) if D > 0.0 else 0.0
    clip = 50.0

    traj = Trajectory(x0=x0)
    x = x0
    traj.record(x)

    for _ in range(max_iter):
        g = potential_grad(x, alpha)
        x = x - lr * g + noise_amp * rng.gauss(0.0, 1.0)
        x = max(-clip, min(clip, x))
        traj.record(x)

    return traj


def measure_mfpt(
    noise_scale: float = 2.0,
    n_trials: int = 200,
    lr: float = 0.05,
    alpha: float = ALPHA,
    max_iter: int = 10_000,
    seed: int | None = None,
) -> dict:
    """
    Empirical mean first passage time: start at +α, escape when x < 0.

    Trials that never cross zero within max_iter are censored.
    """
    escapes: list[int] = []
    censored = 0
    for i in range(n_trials):
        trial_seed = None if seed is None else seed + i
        traj = run_langevin(
            alpha, noise_scale=noise_scale, lr=lr,
            max_iter=max_iter, alpha=alpha, seed=trial_seed,
        )
        crossed: int | None = None
        for n, x in enumerate(traj.steps):
            if x < 0.0:
                crossed = n
                break
        if crossed is None:
            censored += 1
        else:
            escapes.append(crossed)

    k = kramers_rate(noise_scale, lr=lr, alpha=alpha)
    mean_escape = (sum(escapes) / len(escapes)) if escapes else float("inf")
    kramers_tau = k["tau_steps"]
    ratio = (
        mean_escape / kramers_tau
        if escapes and kramers_tau not in (0.0, float("inf"))
        else None
    )
    return {
        "n_trials": n_trials,
        "n_escaped": len(escapes),
        "n_censored": censored,
        "mean_escape_steps": None if not escapes else round(mean_escape, 2),
        "kramers_tau_steps": (
            None if kramers_tau == float("inf") else round(kramers_tau, 1)
        ),
        "ratio_empirical_kramers": None if ratio is None else round(ratio, 4),
        "noise_scale": noise_scale,
        "D": noise_scale ** 2,
    }
