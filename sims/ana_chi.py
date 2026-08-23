"""
Ana-Chi attractor system — Jackson's Pocket primitives.

𝒜_χ = 1.5414 is the chameleon constant: the field's natural resting state,
discovered empirically through 8 phases of hierarchical diamond folding
analysis (Scribble-061, Jackson's Pocket Primitives catalogue).

The system has 5 stable attractor basins across the χ ∈ [0.03, 2.67] state
space.  Three of them are "rattling pockets" — positions of sensitive
dependence where small Δχ causes large changes in fractal behaviour.

Attractor map
-------------
  name          χ value    gravity    rattle    colour    memory decay
  ──────────    ────────   ───────    ──────    ──────    ────────────
  boundary      0.0300     0.50       no        blue      0.90
  mirror        0.9900     1.50       yes       purple    0.93
  true_center   1.5414     3.00       no        white     0.98   ← 𝒜_χ
  white_peak    1.9600     2.00       yes       red       0.95   ← = ALPHA
  escape        2.6700     1.00       yes       orange    0.90

CAIRRN hub → Ana-Chi basin mapping
-----------------------------------
  HOME          → true_center   (1.5414)  equilibrium
  MATH          → white_peak    (1.9600)  singularity  = double-well ALPHA
  CODE          → mirror        (0.9900)  stable / slow
  COMMANDS      → escape        (2.6700)  rapid action
  agent-context → boundary      (0.0300)  interface layer

Key formulae (Jackson's Pocket Primitives, Layer 2 & 3)
---------------------------------------------------------
  Cosine drape     D(r,s,χ) = [cos(r·s·χ) - cos(r·s·χ + 0.01)] × 100
  Rattling prox    P(χ)     = exp(-|χ - χ_rattle| / 0.5)
  Temporal decay   rate(g)  = 0.90 + clamp(g/5, 0, 1) × 0.08
  Multi-basin pot  V(χ)     = -Σ_i  gravity_i × exp(-( χ - χ_i )² / 2σ²)
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Final

# ---------------------------------------------------------------------------
# Core constant
# ---------------------------------------------------------------------------

ANA_CHI_CONSTANT: Final[float] = 1.5414
"""
The chameleon constant — natural equilibrium of Jackson's Pocket.
Not a cliff position; the field's resting state.
Longest temporal memory (decay 0.98).  Walls breathe evenly.
"""

# Sigma for the Gaussian well potentials
_SIGMA: float = 0.40

# Decay constant for rattling-proximity exponential (0.5 from the catalogue)
_RATTLE_DECAY: float = 0.50

# Rattle pocket chi values (from Jackson's Pocket Primitives, Layer 2)
RATTLE_CHI: Final[tuple[float, ...]] = (0.9900, 1.9600, 2.6700)


# ---------------------------------------------------------------------------
# Attractor basin dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AnaChiBasin:
    """One of the five Ana-Chi stable attractor basins."""
    name: str
    chi: float          # χ position in state space
    gravity: float      # depth of potential well (higher = stronger pull)
    rattling: bool      # True if this is a rattling pocket
    colour: str         # qualitative colour label
    memory_decay: float # temporal-decay rate ∈ [0.90, 0.98]

    def temporal_decay(self, memory: float) -> float:
        """Advance one memory decay step: memory × rate."""
        return memory * self.memory_decay

    def proximity(self, chi: float) -> float:
        """
        Exponential proximity to this basin from a given χ position.

        P(χ) = exp(-|χ - χ_basin| / _SIGMA)

        Returns 1.0 at the basin centre, decays toward 0 at distance.
        """
        return math.exp(-abs(chi - self.chi) / _SIGMA)

    def well_value(self, chi: float) -> float:
        """Gaussian potential well at this basin: -gravity × exp(-(χ-χᵢ)²/2σ²)."""
        diff = chi - self.chi
        return -self.gravity * math.exp(-(diff * diff) / (2.0 * _SIGMA * _SIGMA))

    def well_gradient(self, chi: float) -> float:
        """Gradient of the Gaussian well: +gravity × (χ-χᵢ)/σ² × exp(-(χ-χᵢ)²/2σ²)."""
        diff = chi - self.chi
        return self.gravity * (diff / (_SIGMA * _SIGMA)) * math.exp(
            -(diff * diff) / (2.0 * _SIGMA * _SIGMA)
        )


# ---------------------------------------------------------------------------
# The five basins (ordered by χ value)
# ---------------------------------------------------------------------------

BASINS: Final[tuple[AnaChiBasin, ...]] = (
    AnaChiBasin(name="boundary",    chi=0.0300, gravity=0.50, rattling=False, colour="blue",   memory_decay=0.90),
    AnaChiBasin(name="mirror",      chi=0.9900, gravity=1.50, rattling=True,  colour="purple", memory_decay=0.93),
    AnaChiBasin(name="true_center", chi=1.5414, gravity=3.00, rattling=False, colour="white",  memory_decay=0.98),
    AnaChiBasin(name="white_peak",  chi=1.9600, gravity=2.00, rattling=True,  colour="red",    memory_decay=0.95),
    AnaChiBasin(name="escape",      chi=2.6700, gravity=1.00, rattling=True,  colour="orange", memory_decay=0.90),
)

_BASIN_BY_NAME: Final[dict[str, AnaChiBasin]] = {b.name: b for b in BASINS}

# CAIRRN station-hub → Ana-Chi basin name
HUB_BASIN: Final[dict[str, str]] = {
    "HOME":          "true_center",
    "MATH":          "white_peak",
    "CODE":          "mirror",
    "COMMANDS":      "escape",
    "agent-context": "boundary",
}


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def get_basin(name: str) -> AnaChiBasin:
    """Return the AnaChiBasin for a given name.  Raises KeyError if unknown."""
    return _BASIN_BY_NAME[name]


def hub_basin(hub_name: str) -> AnaChiBasin | None:
    """Return the Ana-Chi basin for a CAIRRN hub, or None if unmapped."""
    bname = HUB_BASIN.get(hub_name)
    return _BASIN_BY_NAME.get(bname) if bname else None


def nearest_basin(chi: float) -> AnaChiBasin:
    """Return the basin with the smallest |χ - χ_basin|."""
    return min(BASINS, key=lambda b: abs(chi - b.chi))


def basin_at_hub(hub_name: str) -> AnaChiBasin:
    """Return the basin for a hub, defaulting to true_center if unmapped."""
    return hub_basin(hub_name) or _BASIN_BY_NAME["true_center"]


# ---------------------------------------------------------------------------
# Wall-modulation primitives (Jackson's Pocket Primitives, Layer 3)
# ---------------------------------------------------------------------------


def cosine_drape(r: float, s: float, chi: float) -> float:
    """
    Cosine-drape formula D(r, s, χ):

        D = [ cos(r·s·χ) − cos(r·s·χ + 0.01) ] × 100

    This is the finite-difference derivative of cos(r·s·χ) with step 0.01,
    amplified ×100.  The "impossibly close cosine difference" — produces the
    nuzzling felt-texture described in Scribble-061.

    Parameters
    ----------
    r   : radial distance √(x²+y²) ≥ 0
    s   : scale factor ∈ {1, 2, 4, 8}
    chi : Ana-Chi value χ ∈ [0.03, 2.67]
    """
    x = r * s * chi
    return (math.cos(x) - math.cos(x + 0.01)) * 100.0


def rattling_proximity(chi: float) -> dict[str, float]:
    """
    Exponential proximity to each rattling pocket:

        P(χ) = exp( −|χ − χ_rattle| / 0.5 )

    for χ_rattle ∈ {0.99, 1.96, 2.67}.

    Returns a dict with proximity values for all three rattling pockets.
    At a rattle centre P = 1.0, at distance 1.0 P ≈ 0.135.
    """
    return {
        "mirror":     math.exp(-abs(chi - 0.9900) / _RATTLE_DECAY),
        "white_peak": math.exp(-abs(chi - 1.9600) / _RATTLE_DECAY),
        "escape":     math.exp(-abs(chi - 2.6700) / _RATTLE_DECAY),
    }


def temporal_decay_rate(gravity: float) -> float:
    """
    Memory decay rate from attractor gravity:

        rate = 0.90 + clamp(g/5, 0, 1) × 0.08

    High-gravity attractors (true_center g=3.0) → rate 0.948 ≈ 0.98.
    Low-gravity (boundary g=0.5) → rate 0.908 ≈ 0.90.

    Note: basin.memory_decay stores the exact per-basin value from the
    catalogue; this formula is the continuous version for arbitrary g.
    """
    clamped = max(0.0, min(gravity / 5.0, 1.0))
    return 0.90 + clamped * 0.08


# ---------------------------------------------------------------------------
# Multi-basin potential and simulation
# ---------------------------------------------------------------------------


def potential(chi: float) -> float:
    """
    Multi-basin Gaussian potential:

        V(χ) = Σ_i  −gravity_i × exp( −(χ − χ_i)² / 2σ² )

    Minima sit at each basin centre.  The global minimum (deepest well) is at
    true_center (gravity 3.0).  V'(χ) < 0 means gradient is pushing χ down
    (toward a minimum).
    """
    return sum(b.well_value(chi) for b in BASINS)


def potential_grad(chi: float) -> float:
    """
    Gradient V'(χ) = Σ_i gravity_i · (χ−χ_i)/σ² · exp(−(χ−χ_i)²/2σ²).

    Positive → push rightward; negative → push leftward.
    Zero at every basin centre.
    """
    return sum(b.well_gradient(chi) for b in BASINS)


@dataclass
class AnaChiTrajectory:
    """Result of a single Ana-Chi gradient-descent simulation."""
    chi_0: float
    steps: list[float] = field(default_factory=list)
    converged: bool = False
    converged_at: float | None = None
    final_basin: str = "unknown"

    def record(self, chi: float) -> None:
        self.steps.append(chi)


def run_ana_chi_flow(
    chi_0: float,
    lr: float = 0.02,
    max_iter: int = 2000,
    tol: float = 1e-7,
) -> AnaChiTrajectory:
    """
    Gradient descent on the multi-basin Ana-Chi potential.

    V(χ) = −Σ_i gravity_i · exp(−(χ−χᵢ)²/2σ²)
    χ_{n+1} = χ_n − lr · V'(χ_n)

    Starting from chi_0, the trajectory converges to the nearest basin
    weighted by gravity.  true_center (gravity 3.0) has the widest basin
    of attraction; escape (gravity 1.0) the narrowest.

    Parameters
    ----------
    chi_0    : initial χ position (should be in [0.0, 3.0] for physical range)
    lr       : gradient-descent learning rate (default 0.02)
    max_iter : iteration cap
    tol      : convergence threshold on |V'(χ)|
    """
    traj = AnaChiTrajectory(chi_0=chi_0)
    # Clamp immediately so all recorded steps stay in the physical range
    chi = max(0.0, min(3.0, float(chi_0)))
    traj.record(chi)

    for _ in range(max_iter):
        g = potential_grad(chi)
        chi = chi - lr * g
        # Soft clamp to physical range [0.0, 3.0]
        chi = max(0.0, min(3.0, chi))
        traj.record(chi)
        if abs(g) < tol:
            traj.converged = True
            traj.converged_at = chi
            break

    traj.final_basin = nearest_basin(chi).name
    return traj


def summarise_flow(traj: AnaChiTrajectory) -> dict:
    """Return a human-readable summary dict for an Ana-Chi trajectory."""
    final = traj.steps[-1] if traj.steps else traj.chi_0
    b = nearest_basin(final)
    prox = rattling_proximity(final)
    return {
        "chi_0": traj.chi_0,
        "final_chi": round(final, 6),
        "converged": traj.converged,
        "converged_at": round(traj.converged_at, 6) if traj.converged_at else None,
        "steps": len(traj.steps),
        "final_basin": b.name,
        "basin_chi": b.chi,
        "basin_colour": b.colour,
        "error_to_basin": round(abs(final - b.chi), 6),
        "rattling_proximity": {k: round(v, 4) for k, v in prox.items()},
    }


# ---------------------------------------------------------------------------
# CAIRRN modulation helpers
# ---------------------------------------------------------------------------


def hub_chi_weights(activated_hubs: list[str]) -> dict[str, float]:
    """
    Given a list of activated CAIRRN hubs, return a χ-space activation map:
    how much each Ana-Chi basin is energised by the current hub state.

    Returns {basin_name: weight} where weight = sum of rattling proximity
    values from hubs mapped to that basin.
    """
    weights: dict[str, float] = {b.name: 0.0 for b in BASINS}
    for hub in activated_hubs:
        b = hub_basin(hub)
        if b is None:
            continue
        # Add the hub's gravity-weighted contribution to its basin
        weights[b.name] += b.gravity
    return weights


def coherence(chi: float) -> float:
    """
    Ana-Chi coherence — proximity to the true_center (𝒜_χ = 1.5414).

    Returns 1.0 at true_center, decays exponentially with distance.
    This is the SSDDCS Semantic Smoother signal: how close the current
    state is to natural equilibrium.
    """
    return math.exp(-abs(chi - ANA_CHI_CONSTANT) / _SIGMA)


def biphasic_signal(chi: float) -> dict[str, float | str]:
    """
    The 97% / 0.3% biphasic signal of 𝒜_χ.

    structural_order = coherence(chi) (proximity to 1.5414)
    continuous_freedom = 1.0 - structural_order

    At true_center: structural_order = 1.0 (pure structural sovereignty).
    At escape (2.67): structural_order ≈ 0.11 (high freedom, low order).
    """
    so = coherence(chi)
    return {
        "chi": round(chi, 6),
        "structural_order": round(so, 6),
        "continuous_freedom": round(1.0 - so, 6),
        "nearest_basin": nearest_basin(chi).name,
    }


# ---------------------------------------------------------------------------
# S_dual — dual-arm shimmer envelope
#
# S_dual(t, χ) = 0.5·exp(−χ·t) + 0.5·exp(−t/χ)
#
# Two exponential arms with reciprocal decay rates (χ and 1/χ), weighted
# equally at 0.5 each.  The conservation law χ·(1/χ) = 1 ensures the
# geometric mean of the decay rates is always 1 — the product is fixed.
#
# Budget property (AM-GM gap)
# ───────────────────────────
# The total memory carried by S_dual over infinite continuous time is:
#
#     ∫₀^∞ S_dual(t, χ) dt = (χ + 1/χ) / 2   ← arithmetic mean of rates
#
# By AM-GM this is always ≥ 1, with equality only at χ = 1 (symmetric arms).
# The surplus above the unit baseline is the "shimmer budget" — how much
# extra activation a quality event earns before S_dual decays to zero:
#
#     surplus(χ) = (χ + 1/χ)/2 − 1 = (χ − 1)² / (2χ)
#
# At 𝒜_χ = 1.5414:  surplus ≈ (0.5414)² / 3.0828 ≈ 0.0951  (~9.5 %)
#
# Design formula — target surplus s → required χ:
#
#     χ = (1 + s) + √(s · (s + 2))       ← larger root (fast arm leads)
#     χ = (1 + s) − √(s · (s + 2))       ← smaller root (slow arm leads)
#
# Both roots produce the same budget; the choice of root determines which
# arm decays faster.  At χ > 1 the fast arm (rate χ) decays first and the
# slow arm (rate 1/χ < 1) carries the tail memory.
#
# Discrete tick budget
# ─────────────────────
# In a tick-based system (step size 1) the discrete sum replaces the integral:
#
#     Σ_{n=0}^∞ S_dual(n, χ)  =  0.5/(1−e^{−χ})  +  0.5/(1−e^{−1/χ})
#
# At 𝒜_χ: ≈ 0.636 + 1.047 = 1.683  (vs continuous 1.095)
# Discrete surplus ≈ (1.683 − 1.582) / 1.582 ≈ 6.4%  (vs ~9.5% continuous)
# The fast arm is undersampled at 1 tick/step but the budget loss is modest.
#
# Arm half-lives
# ───────────────
#   fast arm:  t½_fast = ln(2) / χ           ← shorter half-life
#   slow arm:  t½_slow = χ · ln(2)           ← longer half-life
#   ratio:     t½_slow / t½_fast = χ²
#
# At 𝒜_χ = 1.5414:
#   t½_fast ≈ 0.45 ticks  (sub-tick — undersampled at 1-tick resolution)
#   t½_slow ≈ 1.07 ticks  (just above Nyquist at 1-tick step)
#   ratio   ≈ 2.376       (= χ²)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SDualSpec:
    """
    All derived quantities for S_dual at a fixed χ.

    Compute once per basin and reuse — all fields are pure functions of chi.
    """
    chi: float

    @property
    def budget(self) -> float:
        """Memory surplus = (χ−1)² / (2χ).  Zero at χ=1; grows quadratically."""
        return (self.chi - 1.0) ** 2 / (2.0 * self.chi)

    @property
    def budget_pct(self) -> float:
        """Memory surplus as a percentage (budget × 100)."""
        return self.budget * 100.0

    @property
    def integral(self) -> float:
        """∫₀^∞ S_dual dt = (χ + 1/χ) / 2.  Always ≥ 1.0."""
        return (self.chi + 1.0 / self.chi) / 2.0

    @property
    def halflife_fast(self) -> float:
        """Half-life of the fast (rate χ) arm in ticks: ln(2)/χ."""
        return math.log(2.0) / self.chi

    @property
    def halflife_slow(self) -> float:
        """Half-life of the slow (rate 1/χ) arm in ticks: χ·ln(2)."""
        return self.chi * math.log(2.0)

    @property
    def halflife_ratio(self) -> float:
        """Ratio of slow-to-fast half-lives: χ²."""
        return self.chi ** 2

    def discrete_sum(self, n_ticks: int = 10_000) -> float:
        """
        Finite discrete approximation to Σ_{n=0}^{N} S_dual(n).

        Uses the closed-form geometric-series formula for infinite n:
            0.5 / (1 − e^{−χ})  +  0.5 / (1 − e^{−1/χ})

        The n_ticks argument is unused (kept for API symmetry); the closed
        form is exact.
        """
        fast_sum = 0.5 / (1.0 - math.exp(-self.chi))
        slow_sum = 0.5 / (1.0 - math.exp(-1.0 / self.chi))
        return fast_sum + slow_sum

    def evaluate(self, t: float) -> float:
        """S_dual(t) = 0.5·exp(−χ·t) + 0.5·exp(−t/χ)."""
        return 0.5 * math.exp(-self.chi * t) + 0.5 * math.exp(-t / self.chi)

    def as_dict(self) -> dict:
        return {
            "chi":            round(self.chi, 6),
            "integral":       round(self.integral, 6),
            "budget":         round(self.budget, 6),
            "budget_pct":     round(self.budget * 100, 2),
            "halflife_fast":  round(self.halflife_fast, 4),
            "halflife_slow":  round(self.halflife_slow, 4),
            "halflife_ratio": round(self.halflife_ratio, 4),
            "discrete_sum":   round(self.discrete_sum(), 6),
        }


def s_dual(t: float, chi: float = ANA_CHI_CONSTANT) -> float:
    """
    S_dual(t, χ) = 0.5·exp(−χ·t) + 0.5·exp(−t/χ)

    Dual-arm exponential shimmer envelope.

    Parameters
    ----------
    t   : time in ticks (≥ 0)
    chi : Ana-Chi constant χ > 0 (default: 𝒜_χ = 1.5414)
    """
    return 0.5 * math.exp(-chi * t) + 0.5 * math.exp(-t / chi)


def s_dual_budget(chi: float) -> float:
    """
    Memory surplus above the unit baseline: (χ − 1)² / (2χ).

    Equals zero at χ=1 (no surplus — pure single-exponential).
    Grows quadratically as χ deviates from 1 in either direction.
    At 𝒜_χ = 1.5414: budget ≈ 0.0951 (~9.5 %).
    """
    return (chi - 1.0) ** 2 / (2.0 * chi)


def chi_from_budget(s: float) -> tuple[float, float]:
    """
    Invert the budget formula: given target surplus s, return the two χ roots.

        χ² − (2 + 2s)·χ + 1 = 0
        χ = (1 + s) ± √(s·(s + 2))

    Both roots produce identical shimmer integrals (symmetric budget).
    Larger root: fast arm leads (χ > 1).
    Smaller root: slow arm leads (χ < 1).

    Parameters
    ----------
    s : target memory surplus ≥ 0  (e.g. 0.10 for 10 %)

    Returns
    -------
    (chi_large, chi_small) — both χ > 0, chi_large · chi_small = 1
    """
    if s < 0.0:
        raise ValueError(f"surplus must be ≥ 0; got {s}")
    disc = math.sqrt(max(0.0, s * (s + 2.0)))
    large = (1.0 + s) + disc
    small = (1.0 + s) - disc
    return large, small


def s_dual_table(chis: list[float] | None = None) -> list[dict]:
    """
    Return a table of SDualSpec.as_dict() rows for a list of χ values.

    Default χ values are the five Ana-Chi basin centres.
    """
    if chis is None:
        chis = [b.chi for b in BASINS]
    return [SDualSpec(chi=c).as_dict() for c in chis]


# Canonical S_dual spec for the system equilibrium point (𝒜_χ = 1.5414)
ANA_CHI_S_DUAL: SDualSpec = SDualSpec(chi=ANA_CHI_CONSTANT)
