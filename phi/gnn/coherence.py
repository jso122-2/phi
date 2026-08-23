"""
Coherence Layer — Negative Energy Formulas + Euler Characteristic
Implements a suite of negative-energy regularizers that schedule themselves
across training, enforcing structural consistency through the GNN-SSM stack.

The total coherence energy is a sum of five terms:

    E_coh(h, L, dA, h_layers, G) =
        -α · J(h)               [negentropy: rewards structured, non-Gaussian representations]
      + β · h^T L h             [Laplacian smoothness: penalises incoherent neighbor signals]
      + γ · Φ(dA)              [Lyapunov stability: keeps Euler SSM dynamics contractive]
      + δ · Ω(h_layers)        [layer coherence: bounds cross-layer representation drift]
      + ε · χ(G)               [Euler characteristic: topological graph coherence]

The Euler characteristic term is the graph-theoretic signature:
    χ = V − E + T    (V = nodes, E = edges, T = triangles)
    χ encodes how many "topological holes" exist in the knowledge structure.
    Encouraging χ → χ_target per cluster promotes well-connected communities
    with bounded redundancy.

Topology binding:
    euler_characteristic_loss() accepts either a raw edge_index tensor OR a
    TopologicalInvariant from topology.primitives.  When a TopologicalInvariant
    is supplied, the full χ = V − E + T (including triangles) is used directly
    rather than the approximate V − E fallback.

    CoherenceLayer.forward() also accepts an optional TopologicalInvariant
    whose .chi field overrides euler_chi_target for that step — enabling the
    CoherenceDaemon to pass the live graph geometry into the loss each cycle.

Each term has a scheduled weight (α, β, γ, δ) that anneals on a cosine or
linear schedule so early training is dominated by reconstruction tasks and
later training refines structural coherence.

References:
    - Negentropy: Hyvärinen & Oja (2000), "Independent Component Analysis"
    - Laplacian smoothness: Zhou et al. (2004), "Learning with Local and Global Consistency"
    - Lyapunov SSM stability: Gu et al. (2022), "Efficiently Modeling Long Sequences with S4"
    - Layer coherence: analogous to self-distillation / BYOL consistency objectives
"""
import math
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    _TORCH_OK = True
except ImportError:
    torch = None  # type: ignore[assignment]
    nn = None     # type: ignore[assignment]
    F = None      # type: ignore[assignment]
    _TORCH_OK = False

if TYPE_CHECKING:
    from phi.topology.primitives import TopologicalInvariant


# ──────────────────────────────────────────────────────────────────────────────
# Individual negative-e terms
# ──────────────────────────────────────────────────────────────────────────────

def negentropy_loss(h: torch.Tensor, eps: float = 1e-8) -> torch.Tensor:
    """
    Approximated negentropy regularizer.

    Negentropy J(h) = H(h_gauss) - H(h) measures how far h is from Gaussian.
    We want to MAXIMIZE J (reward structure), so the loss is -J.

    Approximation via kurtosis proxy (fast, no density estimation):
        J(h) ≈ (1/12) · E[h³]² + (1/48) · kurt(h)²

    We use the simpler: -J ≈ -|kurt(h)| pushing toward platykurtic or
    leptokurtic distributions (both structured; Gaussian = 0 kurtosis = bad).

    Returns positive scalar (to be minimised). Lower = more structured.
    """
    h_flat = h.reshape(-1)
    mu = h_flat.mean()
    sigma = h_flat.std().clamp(min=eps)
    h_norm = (h_flat - mu) / sigma
    kurt = (h_norm ** 4).mean() - 3.0       # excess kurtosis (0 for Gaussian)
    # negentropy proxy: reward non-zero kurtosis
    neg_j = -kurt.abs()
    return neg_j


def laplacian_smoothness_loss(
    h: torch.Tensor,
    edge_index: torch.LongTensor,
    edge_weight: Optional[torch.Tensor] = None,
    normalize: bool = True,
) -> torch.Tensor:
    """
    Graph Laplacian quadratic form: E_smooth = h^T L h

    For each edge (i, j) with weight w: penalizes ||h_i - h_j||² · w
    This is the continuous graph signal energy — low when linked nodes
    have similar representations (desired coherence property).

    Returns positive scalar. Lower = smoother (more coherent) graph signal.

    Args:
        h:            (N, d) node representations
        edge_index:   (2, E) edges as [src; dst]
        edge_weight:  (E,) optional per-edge weights (default = 1)
    """
    if edge_index.numel() == 0:
        return h.new_zeros(1).squeeze()

    src, dst = edge_index[0], edge_index[1]
    w = edge_weight if edge_weight is not None else torch.ones(src.size(0), device=h.device)

    diff = h[src] - h[dst]                           # (E, d)
    sq_dist = (diff ** 2).sum(dim=-1)                # (E,)
    energy = (w * sq_dist).sum()

    if normalize:
        energy = energy / (h.size(0) * h.size(1) + 1e-8)

    return energy


def ssm_lyapunov_loss(
    A_log: torch.Tensor,
    dt: torch.Tensor,
    margin: float = 0.99,
) -> torch.Tensor:
    """
    Lyapunov stability regularizer for the EulerSSM state matrix.

    For EulerSSM, eigenvalue magnitudes are r = sigmoid(r_log) ∈ (0,1),
    which are stable by construction. But r can approach 1 (near-unit =
    very long memory / near-unstable saturation) during training.

    Accepts r_log (from EulerSSM) or A_log (from SelectiveSSM) —
    both represent log-scale contraction parameters.

    Loss: penalize r values approaching `margin` from below.
        r = sigmoid(r_log) ∈ (0, 1)
        L_lyap = mean(ReLU(r - margin))

    Returns positive scalar. Zero when all r ≤ margin.
    """
    r = torch.sigmoid(A_log)     # works for both r_log (EulerSSM) and A_log
    violation = F.relu(r - margin)
    return violation.mean()


def euler_characteristic_loss(
    edge_index: torch.LongTensor,
    num_nodes: int,
    cluster_assignments: Optional[torch.Tensor] = None,
    target_chi: float = 1.0,
    eps: float = 1e-6,
    topo_invariant=None,     # Optional[TopologicalInvariant]
) -> torch.Tensor:
    """
    Euler characteristic coherence loss — bounded to [0, 1).

    Penalises deviation of χ from target_chi:
        loss = 1 − exp(−|χ − χ_target| / χ_scale)

    χ_scale = max(|χ|, |χ_target|, V) ensures scale-invariance across
    graph densities. Loss is always in [0, 1).

    Topology binding:
        When `topo_invariant` (a topology.primitives.TopologicalInvariant) is
        supplied, χ = V − E + T is read directly from the primitive layer —
        the full Euler-Poincaré formula including triangle count T.
        Without it, χ = V − E is used as a fast fallback.

    Note: On fixed edge sets the gradient of this term w.r.t. model parameters
    is zero — it acts as a structural monitor rather than a gradient source.
    Gradient signal for topology comes from the Laplacian term.

    Args:
        edge_index:      (2, E) — graph edges (used when topo_invariant is None)
        num_nodes:       V      (used when topo_invariant is None)
        target_chi:      desired χ (default 1 = single tree-like community)
        topo_invariant:  Optional TopologicalInvariant from topology.primitives;
                         if provided, overrides edge_index / num_nodes for χ.

    Returns:
        Scalar in [0, 1). Zero when χ = target_chi.
    """
    device = edge_index.device

    if topo_invariant is not None:
        # Full χ = V − E + T from the primitive layer
        chi = float(topo_invariant.chi)
        V   = float(topo_invariant.V)
    else:
        if edge_index.numel() == 0:
            return edge_index.new_zeros(1, dtype=torch.float).squeeze()
        V   = float(num_nodes)
        E   = float(edge_index.size(1))
        chi = V - E   # fast approximation (T not computed here)

    deviation = abs(chi - target_chi)
    scale     = max(abs(chi), abs(target_chi), V, 1.0)
    loss_val  = 1.0 - math.exp(-deviation / scale)
    return torch.tensor(loss_val, dtype=torch.float, device=device)


def layer_coherence_loss(
    h_layers: List[torch.Tensor],
    temperature: float = 1.0,
) -> torch.Tensor:
    """
    Cross-layer representation coherence.

    Penalises KL divergence between soft-normalised distributions at
    consecutive layers, bounding representation drift through depth.

    Without this, deeper layers can collapse to a different manifold than
    earlier ones — creating incoherent intermediate representations that
    corrupt the SSM's traversal memory.

    L_layer = mean_l KL( softmax(h_l / T) || softmax(h_{l+1} / T) )

    Returns positive scalar.
    """
    if len(h_layers) < 2:
        return h_layers[0].new_zeros(1).squeeze()

    total = h_layers[0].new_zeros(1).squeeze()
    for l in range(len(h_layers) - 1):
        p = F.softmax(h_layers[l] / temperature, dim=-1)
        q = F.softmax(h_layers[l + 1] / temperature, dim=-1)
        kl = F.kl_div(q.log(), p, reduction="batchmean")
        total = total + kl

    return total / (len(h_layers) - 1)


# ──────────────────────────────────────────────────────────────────────────────
# Coherence weight scheduler
# ──────────────────────────────────────────────────────────────────────────────

class CoherenceWeightSchedule:
    """
    Anneals the four coherence loss weights (α, β, γ, δ) over training.

    Phases:
        0 → warmup_frac:    all weights = 0   (reconstruction only — learn the basics)
        warmup → ramp_frac: cosine ramp up    (gradually introduce coherence)
        ramp → 1.0:         full weights      (coherence fully active)

    This prevents coherence regularization from overwhelming the task signal
    early in training when representations haven't formed yet.
    """

    def __init__(
        self,
        alpha: float = 0.10,   # negentropy weight
        beta: float  = 0.05,   # laplacian smoothness weight
        gamma: float = 0.08,   # SSM Lyapunov stability weight
        delta: float = 0.03,   # layer coherence weight
        epsilon: float = 0.04, # Euler characteristic topological weight
        warmup_frac: float = 0.15,
        ramp_frac: float   = 0.40,
        total_steps: int   = 1000,
    ) -> None:
        self.targets = {"alpha": alpha, "beta": beta, "gamma": gamma, "delta": delta, "epsilon": epsilon}
        self.warmup_frac = warmup_frac
        self.ramp_frac = ramp_frac
        self.total_steps = total_steps
        self._step = 0

    def step(self) -> None:
        self._step += 1

    def weights(self) -> Dict[str, float]:
        t = self._step / max(self.total_steps, 1)
        if t < self.warmup_frac:
            scale = 0.0
        elif t < self.ramp_frac:
            progress = (t - self.warmup_frac) / (self.ramp_frac - self.warmup_frac)
            scale = 0.5 * (1 - math.cos(math.pi * progress))  # cosine ramp
        else:
            scale = 1.0
        return {k: v * scale for k, v in self.targets.items()}

    def load_state(self, step: int) -> None:
        self._step = step


# ──────────────────────────────────────────────────────────────────────────────
# Coherence Layer (nn.Module)
# ──────────────────────────────────────────────────────────────────────────────

class CoherenceLayer(nn.Module):
    """
    Wraps all four negative-e regularizers into a single differentiable module.

    Sits above the GNN stack and receives:
        - h_layers:   list of per-GNN-layer node representations
        - A_log:      SSM log-A matrix (for Lyapunov term)
        - dt:         SSM time-step tensor (for Lyapunov term)
        - edge_index: graph topology (for Laplacian term)
        - edge_weight: per-edge weights

    Returns scalar coherence energy E_coh and a dict of per-term values
    for logging/scheduling.
    """

    def __init__(
        self,
        alpha: float = 0.10,
        beta: float  = 0.05,
        gamma: float = 0.08,
        delta: float = 0.03,
        epsilon: float = 0.04,
        lyapunov_margin: float = 0.99,
        layer_temperature: float = 1.0,
        euler_chi_target: float = 1.0,
    ) -> None:
        super().__init__()
        self.lyapunov_margin = lyapunov_margin
        self.layer_temperature = layer_temperature
        self.euler_chi_target = euler_chi_target
        self.register_buffer("alpha",   torch.tensor(alpha))
        self.register_buffer("beta",    torch.tensor(beta))
        self.register_buffer("gamma",   torch.tensor(gamma))
        self.register_buffer("delta",   torch.tensor(delta))
        self.register_buffer("epsilon", torch.tensor(epsilon))

    def set_weights(self, weights: Dict[str, float]) -> None:
        """Called each step by CoherenceWeightSchedule."""
        self.alpha.fill_(weights["alpha"])
        self.beta.fill_(weights["beta"])
        self.gamma.fill_(weights["gamma"])
        self.delta.fill_(weights["delta"])
        self.epsilon.fill_(weights.get("epsilon", 0.04))

    def forward(
        self,
        h_layers: List[torch.Tensor],
        A_log: torch.Tensor,
        dt: torch.Tensor,
        edge_index: torch.LongTensor,
        edge_weight: Optional[torch.Tensor] = None,
        topo_invariant=None,   # Optional[TopologicalInvariant] from topology.primitives
    ) -> Tuple[torch.Tensor, Dict[str, float]]:
        """
        Compute total coherence energy.

        Topology binding:
            When `topo_invariant` (a topology.primitives.TopologicalInvariant) is
            supplied, the Euler-characteristic term uses the full χ = V − E + T
            from the primitive layer and the live chi overrides euler_chi_target.
            The CoherenceDaemon passes this each cycle via SambaOrchestrator.topo.

        Returns:
            E_coh:    scalar tensor — add to task loss before backward()
            terms:    dict of per-term float values for logging
        """
        h_final = h_layers[-1]
        N = h_final.size(0)

        # Determine the χ target: live graph geometry if available, else stored default
        chi_target = (
            float(topo_invariant.chi)
            if topo_invariant is not None
            else self.euler_chi_target
        )

        # ── Term 1: Negentropy (−J) ────────────────────────────────────────
        neg_e = negentropy_loss(h_final)

        # ── Term 2: Laplacian smoothness (h^T L h) ─────────────────────────
        lap_e = laplacian_smoothness_loss(h_final, edge_index, edge_weight)

        # ── Term 3: Euler SSM Lyapunov stability ───────────────────────────
        lyap_e = ssm_lyapunov_loss(A_log, dt, self.lyapunov_margin)

        # ── Term 4: Layer coherence (cross-layer KL) ───────────────────────
        layer_e = layer_coherence_loss(h_layers, self.layer_temperature)

        # ── Term 5: Euler characteristic — bound to TopologicalInvariant ───
        # If topo_invariant is present, χ = V − E + T (full); else V − E fallback.
        euler_e = euler_characteristic_loss(
            edge_index, N,
            target_chi=chi_target,
            topo_invariant=topo_invariant,
        )

        E_coh = (
            self.alpha   * neg_e
          + self.beta    * lap_e
          + self.gamma   * lyap_e
          + self.delta   * layer_e
          + self.epsilon * euler_e
        )

        terms = {
            "coh/negentropy":    neg_e.item(),
            "coh/laplacian":     lap_e.item(),
            "coh/lyapunov":      lyap_e.item(),
            "coh/layer_kl":      layer_e.item(),
            "coh/euler_chi":     euler_e.item() if isinstance(euler_e, torch.Tensor) else float(euler_e),
            "coh/chi_target":    chi_target,
            "coh/total":         E_coh.item(),
            "coh/alpha":         self.alpha.item(),
            "coh/beta":          self.beta.item(),
            "coh/gamma":         self.gamma.item(),
            "coh/delta":         self.delta.item(),
            "coh/epsilon":       self.epsilon.item(),
        }
        return E_coh, terms

# Related: _luma, SambaGNN.euler_eigenvalue_report, OctopusAttentionHead,
#          hub_scores, micro_step, GraftArm, random_walk_sequence,
#          ResurfaceArm, CairnBridge._coherence, CAIRRNPipeline, run_ana_chi_flow
