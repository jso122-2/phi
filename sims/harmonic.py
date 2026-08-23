"""
Harmonically sharded index with local propagation.

Architecture
------------
The index is a ring of N shards.  Each shard i is centred on the i-th
harmonic of the fundamental attractor α = 1.96:

    basin_centre(i) = (i + 1) · α

Shards hold a scalar *activation*.  Local propagation uses a
discrete-wave / diffusion update:

    a_i(t+1) = a_i(t) + κ · [ a_{i-1}(t) + a_{i+1}(t) − 2·a_i(t) ]

where κ ∈ (0, 0.5) is the coupling constant (stability condition: κ < 0.5).

Trajectories from sims.attractors are injected by mapping their final
position to the nearest basin centre, accumulating activation in the
corresponding shard.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Sequence

import numpy as np

from sims.attractors import ALPHA


# ---------------------------------------------------------------------------
# Station-hub → shard mapping
#
# Each Obsidian hub node owns a contiguous slice of the harmonic ring.
# Activation injected via a hub is distributed evenly across its shards,
# then propagates outward through the normal local/resonance update cycle.
#
#   HOME         shard 0          fundamental attractor (1·α)
#   MATH         shards 1–2       mathematical depth (2·α, 3·α)
#   CODE         shards 3–4       implementation range (4·α, 5·α)
#   COMMANDS     shard 5          command layer (6·α)
#   agent-context shards 6–7     workflow / meta layer (7·α, 8·α)
# ---------------------------------------------------------------------------

HUB_SHARD_MAP: dict[str, tuple[int, ...]] = {
    "HOME":          (0,),
    "MATH":          (1, 2),
    "CODE":          (3, 4),
    "COMMANDS":      (5,),
    "agent-context": (6, 7),
}

HUB_NAMES: tuple[str, ...] = tuple(HUB_SHARD_MAP.keys())

# MCP boot floor — peaked HOME prior so PSSPPS never sees a dead ring.
# Uniform seed would be structural_order = 0 (pure semantic); HOME + 1
# propagate step is peaked with neighbour bleed.
WARM_HUB: str = "HOME"
WARM_VALUE: float = 1.0
WARM_PROPAGATE_STEPS: int = 1
COLD_EPS: float = 1e-12


# ---------------------------------------------------------------------------
# Shard
# ---------------------------------------------------------------------------


@dataclass
class HarmonicShard:
    """One unit of the harmonically-indexed ring."""

    index: int
    harmonic: int           # harmonic number (1-based)
    activation: float = 0.0
    coherence: float = 1.0  # M3 coherence quality ∈ [0, 1]; 1.0 = coherent silence

    @property
    def basin_centre(self) -> float:
        """Basin centre = harmonic × α."""
        return self.harmonic * ALPHA


# ---------------------------------------------------------------------------
# Propagator
# ---------------------------------------------------------------------------


class LocalPropagator:
    """
    Nearest-neighbour diffusion propagator on a ring of shards.

    Parameters
    ----------
    coupling : float
        Coupling constant κ.  Must satisfy 0 < κ < 0.5 for stability.
    """

    def __init__(self, coupling: float = 0.15) -> None:
        if not 0.0 < coupling < 0.5:
            raise ValueError(f"coupling must be in (0, 0.5); got {coupling}")
        self.coupling = coupling

    def step(self, shards: list[HarmonicShard]) -> None:
        """In-place wave-diffusion update over a ring."""
        n = len(shards)
        activations = np.array([s.activation for s in shards], dtype=float)
        left = np.roll(activations, 1)
        right = np.roll(activations, -1)
        new_activations = activations + self.coupling * (left + right - 2.0 * activations)
        for shard, val in zip(shards, new_activations):
            shard.activation = float(val)


# ---------------------------------------------------------------------------
# Resonance propagator
# ---------------------------------------------------------------------------


class ResonancePropagator:
    """
    Exponential cosine resonance-sharing propagator on a ring of shards.

    Derived from the composition of three regimes:

      Option 3 — gate (dominance ratio):
        r    = a_p / A                          a_p = peak activation, A = total
        gate = −cos(π · r)                      ∈ [−1, +1]

      Option 1 — spatial kernel (ring distance from hotspot p to shard i):
        d_i  = min(|i−p|, N−|i−p|) / (N/2)    ∈ [0, 1]  (ring-wrapped)
        s_i  = −cos(π · d_i)                   ∈ [−1, +1]

      Option 2 — exponential kernel (emerges from the product):
        w_i  = exp(gate · s_i)
             = exp(cos(π·r) · cos(π·d_i))

    Conservation: the hotspot *donates* κ · a_p; that amount is redistributed
    to all other shards weighted by normalised w.  Total activation is conserved.

    The sign on the hotspot is −κ (it loses); the sign on receivers is +κ (gain).

    Parameters
    ----------
    coupling : float
        Fraction of peak activation donated per step.  No upper stability bound
        beyond coupling < 1.0 (unlike the local diffusion κ < 0.5).
    """

    def __init__(self, coupling: float = 0.15) -> None:
        if not 0.0 < coupling < 1.0:
            raise ValueError(f"coupling must be in (0, 1); got {coupling}")
        self.coupling = coupling

    def step(self, shards: list["HarmonicShard"]) -> None:
        """In-place resonance-sharing update over the ring."""
        n = len(shards)
        if n < 2:
            return

        acts = np.array([s.activation for s in shards], dtype=float)
        total = acts.sum()
        if total < 1e-12:
            return

        p = int(np.argmax(acts))
        a_p = float(acts[p])
        r = a_p / total

        # Gate — how dominant is the hotspot?
        gate = -np.cos(np.pi * r)

        # Ring distances from hotspot (topology-aware)
        linear = np.abs(np.arange(n) - p)
        ring_d = np.minimum(linear, n - linear)
        d = ring_d / (n / 2)                   # normalise to [0, 1]

        # Spatial kernel
        shape = -np.cos(np.pi * d)

        # Exponential resonance weights
        raw_w = np.exp(gate * shape)
        raw_w[p] = 0.0                          # hotspot does not receive its own donation
        w_sum = raw_w.sum()
        if w_sum < 1e-12:
            return

        norm_w = raw_w / w_sum                  # receivers' shares sum to 1

        # Conservation: hotspot donates −κ·a_p, receivers gain proportionally
        donated = self.coupling * a_p
        acts[p] -= donated                      # −κ on the source
        acts += norm_w * donated                # +κ·w_norm_i on each receiver

        for shard, val in zip(shards, acts):
            shard.activation = float(val)


# ---------------------------------------------------------------------------
# Index
# ---------------------------------------------------------------------------


class HarmonicIndex:
    """
    Harmonically sharded index.

    Parameters
    ----------
    n_harmonics : int
        Number of shards.  Shard i is centred on harmonic (i+1)·α.
    coupling    : float
        Propagation coupling κ ∈ (0, 0.5).
    """

    def __init__(self, n_harmonics: int = 8, coupling: float = 0.15) -> None:
        self.shards: list[HarmonicShard] = [
            HarmonicShard(index=i, harmonic=i + 1)
            for i in range(n_harmonics)
        ]
        self._propagator = LocalPropagator(coupling)
        self._resonance_propagator = ResonancePropagator(coupling)
        self._isometric_propagator = IsometricCosinePropagator(coupling)
        self._base_coupling: float = coupling
        self._coupling: float = coupling
        self._step_count: int = 0
        # Last vault-topology fusion (None until graph_topo_hubs applies).
        self.last_t_b_norm: float | None = None
        self.last_chi: float | None = None
        # RLock so methods can safely call each other without deadlocking
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # Injection
    # ------------------------------------------------------------------

    def inject(self, shard_index: int, value: float = 1.0) -> None:
        """Directly inject activation into shard at position shard_index."""
        with self._lock:
            self.shards[shard_index % len(self.shards)].activation += value

    @property
    def coupling(self) -> float:
        """Effective κ currently on the local propagator."""
        return self._coupling

    def set_coupling(self, kappa: float) -> float:
        """
        Set ring coupling on all three propagators.

        Local diffusion stays in (0, 0.5) for stability. Resonance and
        isometric accept up to 0.99. Returns the local κ actually applied.
        """
        local_k = min(max(float(kappa), 1e-6), 0.499)
        wide_k = min(max(float(kappa), 1e-6), 0.99)
        with self._lock:
            self._propagator.coupling = local_k
            self._resonance_propagator.coupling = wide_k
            self._isometric_propagator.coupling = wide_k
            self._coupling = local_k
        return local_k

    def inject_from_hub(self, hub_name: str, value: float = 1.0) -> tuple[int, ...]:
        """
        Inject activation distributed evenly across the shards owned by hub_name.

        Parameters
        ----------
        hub_name : one of HUB_NAMES — "HOME", "MATH", "CODE", "COMMANDS", "agent-context"
        value    : total activation to inject (split evenly across the hub's shards)

        Returns the tuple of shard indices that received activation.
        """
        shard_indices = HUB_SHARD_MAP.get(hub_name)
        if shard_indices is None:
            raise ValueError(
                f"Unknown hub {hub_name!r}. "
                f"Valid hubs: {', '.join(HUB_NAMES)}"
            )
        per_shard = value / len(shard_indices)
        with self._lock:
            for idx in shard_indices:
                self.shards[idx].activation += per_shard
        return shard_indices

    def hub_activations(self) -> dict[str, float]:
        """
        Return total activation per station hub.

        Each hub's activation is the sum of its owned shards' activations.
        """
        with self._lock:
            return {
                hub: round(sum(self.shards[i].activation for i in indices), 8)
                for hub, indices in HUB_SHARD_MAP.items()
            }

    def hub_state(self) -> dict:
        """Serialisable snapshot including the per-hub activation breakdown."""
        with self._lock:
            base = self.state()
            base["hubs"] = [
                {
                    "hub": hub,
                    "shard_indices": list(indices),
                    "basin_centres": [round(self.shards[i].basin_centre, 4) for i in indices],
                    "activation": round(sum(self.shards[i].activation for i in indices), 8),
                }
                for hub, indices in HUB_SHARD_MAP.items()
            ]
            return base

    def inject_from_trajectory_final(self, final_x: float, value: float = 1.0) -> HarmonicShard:
        """
        Map a trajectory's final position to the nearest harmonic basin and
        inject activation there.

        Uses |final_x| so both ±α map to the same shard.
        """
        with self._lock:
            target = abs(final_x)
            nearest = min(self.shards, key=lambda s: abs(s.basin_centre - target))
            nearest.activation += value
            return nearest

    def activation_vector(self) -> np.ndarray:
        """Return current shard activations as a numpy array (thread-safe snapshot)."""
        with self._lock:
            return np.array([s.activation for s in self.shards], dtype=float)

    # ------------------------------------------------------------------
    # Propagation
    # ------------------------------------------------------------------

    def propagate(self, steps: int = 1, mode: str = "local") -> None:
        """
        Advance the propagator by `steps` cycles.

        Parameters
        ----------
        steps : int
            Number of propagation cycles.
        mode : str
            "local"      — nearest-neighbour diffusion (LocalPropagator, κ < 0.5)
            "resonance"  — exponential cosine resonance sharing (ResonancePropagator)
            "isometric"  — true isometric cosine-modulated decay (IsometricCosinePropagator);
                           full bipolar cosine kernel, dissipative (total activation decays),
                           all-to-all coupling in ONE hop expands path space to N^k
        """
        if mode == "resonance":
            propagator = self._resonance_propagator
        elif mode == "local":
            propagator = self._propagator
        elif mode == "isometric":
            propagator = self._isometric_propagator
        else:
            raise ValueError(
                f"Unknown propagation mode {mode!r}; "
                "expected 'local', 'resonance', or 'isometric'"
            )

        with self._lock:
            for _ in range(steps):
                propagator.step(self.shards)
                self._step_count += 1

    # ------------------------------------------------------------------
    # Inspection
    # ------------------------------------------------------------------

    def total_activation(self) -> float:
        with self._lock:
            return sum(s.activation for s in self.shards)

    def is_cold(self) -> bool:
        """True when total |activation| is below COLD_EPS (PSSPPS dead-ring)."""
        return abs(self.total_activation()) < COLD_EPS

    def ensure_warm(
        self,
        hub: str = WARM_HUB,
        value: float = WARM_VALUE,
        steps: int = WARM_PROPAGATE_STEPS,
    ) -> bool:
        """
        Seed a peaked prior if the ring is cold. No-op when already warm.

        Returns True if it injected. Uniform seeding is avoided so
        structural_order stays high (local / harmonic PSSPPS alpha).
        """
        if not self.is_cold():
            return False
        self.inject_from_hub(hub, value)
        if steps > 0:
            self.propagate(steps, mode="local")
        return True

    def peak_shard(self) -> HarmonicShard:
        with self._lock:
            return max(self.shards, key=lambda s: s.activation)

    # ------------------------------------------------------------------
    # Coherence indexing (M3 gate feedback)
    # ------------------------------------------------------------------

    def update_coherence_from_m3(
        self,
        m3: float,
        threshold: float = 1.0,
        decay_rate: float = 0.1,
        heal_rate: float = 0.05,
    ) -> None:
        """
        Update per-shard coherence quality from an M3 gate evaluation.

        M3 = |CSS| · N · |PFS − SHI| — the prefeed quality composite.

        When M3 > threshold the ring is misaligned.  Each shard's coherence
        decays in proportion to how far its activation deviates from SHI
        (the all-shard mean).  Shards that drive the incoherence take the
        largest hit; dark shards are unaffected when all activations are equal.

        When M3 ≤ threshold (accepted) all shards heal toward 1.0 at heal_rate.

        Special case: when all activations are equal (dev_sum ≈ 0) there is no
        identifiable source of incoherence — all shards heal regardless of M3.

        Parameters
        ----------
        m3         : M3 gate value (output of f_m3)
        threshold  : acceptance threshold (default 1.0 = M3_THRESHOLD)
        decay_rate : maximum coherence loss fraction when a shard holds all
                     incoherence and m3 is 2× threshold (default 0.1)
        heal_rate  : exponential healing rate toward 1.0 per call (default 0.05)
        """
        with self._lock:
            activations = np.array([s.activation for s in self.shards], dtype=float)
            shi = float(activations.mean())  # SHI proxy = mean shard activation
            deviation = np.abs(activations - shi)
            dev_sum = float(deviation.sum())

            if m3 > threshold and dev_sum > 1e-12:
                # Clamp excess to [0, 1] so a single huge M3 can't zero coherence
                excess = min((m3 / threshold) - 1.0, 1.0)
                weights = deviation / dev_sum  # shard's share of total incoherence, sums to 1
                for shard, w in zip(self.shards, weights):
                    shard.coherence = max(
                        0.0,
                        shard.coherence * (1.0 - decay_rate * excess * float(w)),
                    )
            else:
                # Accepted (or uniform activations) — heal all toward 1.0
                for shard in self.shards:
                    shard.coherence = min(
                        1.0,
                        shard.coherence + heal_rate * (1.0 - shard.coherence),
                    )

    def heal_coherence(self, heal_rate: float = 0.01) -> None:
        """
        Passively heal all shard coherence toward 1.0.

        Call once per propagation step to simulate coherence recovery in dark
        shards.  Shards that are not receiving disruptive injections recover
        exponentially: c_i(t+1) = c_i(t) + heal_rate · (1 − c_i(t)).

        Parameters
        ----------
        heal_rate : exponential approach rate toward 1.0 (default 0.01)
        """
        with self._lock:
            for shard in self.shards:
                shard.coherence = min(
                    1.0,
                    shard.coherence + heal_rate * (1.0 - shard.coherence),
                )

    def coherence_vector(self) -> np.ndarray:
        """Return current shard coherence values as a numpy array (thread-safe snapshot)."""
        with self._lock:
            return np.array([s.coherence for s in self.shards], dtype=float)

    def mean_coherence(self) -> float:
        """Return mean coherence across all shards ∈ [0, 1]."""
        with self._lock:
            return float(np.mean([s.coherence for s in self.shards]))

    def state(self) -> dict:
        """Serialisable snapshot of the full index."""
        with self._lock:
            mean_coh = sum(s.coherence for s in self.shards) / len(self.shards)
            return {
                "step": self._step_count,
                "alpha": ALPHA,
                "coupling": round(self._coupling, 6),
                "n_harmonics": len(self.shards),
                "total_activation": round(sum(s.activation for s in self.shards), 8),
                "mean_coherence": round(mean_coh, 6),
                "last_t_b_norm": (
                    None if self.last_t_b_norm is None
                    else round(float(self.last_t_b_norm), 6)
                ),
                "last_chi": (
                    None if self.last_chi is None else round(float(self.last_chi), 6)
                ),
                "shards": [
                    {
                        "index": s.index,
                        "harmonic": s.harmonic,
                        "basin_centre": round(s.basin_centre, 4),
                        "activation": round(s.activation, 8),
                        "coherence": round(s.coherence, 6),
                    }
                    for s in self.shards
                ],
            }

    def reset(self) -> None:
        with self._lock:
            for s in self.shards:
                s.activation = 0.0
                s.coherence = 1.0
            self._step_count = 0
            self.last_t_b_norm = None
            self.last_chi = None
        self.set_coupling(self._base_coupling)

    # ------------------------------------------------------------------
    # Snapshot persistence (survive server restarts)
    # ------------------------------------------------------------------

    def dump_snapshot(self) -> dict:
        """Return a JSON-serialisable dict of the full index state."""
        with self._lock:
            return {
                "step": self._step_count,
                "coupling": self._coupling,
                "last_t_b_norm": self.last_t_b_norm,
                "last_chi": self.last_chi,
                "shards": [
                    {
                        "index":      s.index,
                        "activation": s.activation,
                        "coherence":  s.coherence,
                    }
                    for s in self.shards
                ],
            }

    def load_snapshot(self, snap: dict) -> None:
        """Restore activations and coherence from a dump_snapshot() dict."""
        with self._lock:
            self._step_count = int(snap.get("step", 0))
            if "coupling" in snap:
                self.set_coupling(float(snap["coupling"]))
            t_b = snap.get("last_t_b_norm")
            self.last_t_b_norm = None if t_b is None else float(t_b)
            chi = snap.get("last_chi")
            self.last_chi = None if chi is None else float(chi)
            for entry in snap.get("shards", []):
                idx = int(entry["index"])
                if 0 <= idx < len(self.shards):
                    self.shards[idx].activation = float(entry["activation"])
                    self.shards[idx].coherence  = float(entry.get("coherence", 1.0))


# ---------------------------------------------------------------------------
# Isometric cosine propagator
# ---------------------------------------------------------------------------


class IsometricCosinePropagator:
    """
    True isometric cosine-modulated propagator.

    Replaces the exp(gate · shape) resonance kernel with the DIRECT cosine
    kernel evaluated at equal arc-length (isometric) steps on the ring:

        c(d) = cos(π · d)     d ∈ [0, 1] normalised ring distance

    For N = 8 shards, from any shard p the weights are:
        d = 0/4  →  c =  1.000  (self — excluded)
        d = 1/4  →  c =  0.707  (nearest neighbours    — excitatory)
        d = 2/4  →  c =  0.000  (quarter-ring           — neutral)
        d = 3/4  →  c = −0.707  (three-quarter ring     — inhibitory)
        d = 4/4  →  c = −1.000  (antipodal shard        — maximal inhibition)

    Unlike the ResonancePropagator, there is NO exponential wrapping.
    The kernel is bipolar: near shards receive, far shards are inhibited.

    Conservation property
    ---------------------
    The cosine row-sum (excluding the self-term) equals −1 for N = 8, so the
    total activation leaks by κ·total per step.  This DISSIPATION is
    intentional — it is the "decay" in "cosine modulated decay".  The system
    relaxes toward zero without an external driving term.

    Path-space expansion
    --------------------
    Under nearest-neighbour (local) propagation the wave reaches only the
    k-hop neighbourhood after k steps: diameter 4, maximum 6 hub-hops.
    Under IsometricCosine, every shard is coupled to every other shard
    in ONE step (positive or negative), so after k steps the number of
    distinct active routing paths is N^k (not 2^k).  For N = 8 and k = 10
    that is 8^10 ≈ 1.07 × 10^9; with the hub graph × cosine weighting the
    effective path space reaches the ~6.5 × 10^9 range.

    Parameters
    ----------
    coupling : float
        κ ∈ (0, 1) — fraction of each shard's cosine flux donated per step.
    """

    def __init__(self, coupling: float = 0.15) -> None:
        if not 0.0 < coupling < 1.0:
            raise ValueError(f"coupling must be in (0, 1); got {coupling}")
        self.coupling = coupling
        self._kernel: np.ndarray | None = None

    # Build the N×N cosine coupling matrix (lazy, cached per ring size)
    def _build_kernel(self, n: int) -> np.ndarray:
        K = np.zeros((n, n), dtype=float)
        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                ring_d = min(abs(i - j), n - abs(i - j))
                d = ring_d / (n / 2)          # normalise to [0, 1]
                K[i, j] = np.cos(np.pi * d)
        return K

    def step(self, shards: list["HarmonicShard"]) -> None:
        """
        In-place isometric cosine update.

        For each shard i the update is:
            Δa_i = κ · Σ_{j≠i} cos(π·d(i,j)) · a_j

        Positive terms (near shards) add activation;
        negative terms (far shards) subtract activation.
        Total activation decays by κ per step (dissipative by design).
        """
        n = len(shards)
        if n < 2:
            return

        if self._kernel is None or self._kernel.shape[0] != n:
            self._kernel = self._build_kernel(n)

        acts = np.array([s.activation for s in shards], dtype=float)

        # Δa = κ · K · a  (bipolar cosine convolution)
        delta = self.coupling * (self._kernel @ acts)
        acts = acts + delta

        for shard, val in zip(shards, acts):
            shard.activation = float(val)


# ---------------------------------------------------------------------------
# Ticket clipper — station-hub passage recorder
# ---------------------------------------------------------------------------


@dataclass
class TicketRecord:
    """One passage event recorded as a propagation wave crosses a hub."""

    step: int
    hub: str
    shard_indices: tuple[int, ...]
    hub_activation: float
    total_activation: float
    timestamp: float = field(default_factory=time.time)

    @property
    def dominance_ratio(self) -> float:
        """Fraction of total activation held by this hub at the clipping moment."""
        if self.total_activation < 1e-12:
            return 0.0
        return self.hub_activation / self.total_activation


class TicketClipper:
    """
    Station-hub passage recorder.

    Wraps a HarmonicIndex propagation call and records a TicketRecord for
    every hub whose activation crosses `threshold` on a given step.  This
    is the 'ticket clipping' mechanic: the hub stamps the journey log of
    any activation wave that passes through it above the significance floor.

    Parameters
    ----------
    index     : the HarmonicIndex whose hubs are monitored
    threshold : minimum hub activation to trigger a clip (default 0.01)
    """

    def __init__(self, index: "HarmonicIndex", threshold: float = 0.01) -> None:
        self.index = index
        self.threshold = threshold
        self._log: list[TicketRecord] = []
        self._lock = threading.Lock()

    def clip_step(self, step: int) -> list[TicketRecord]:
        """
        Sample the current hub activations and record clips above threshold.

        Call AFTER each propagation step.
        Returns the TicketRecords created for this step (may be empty).
        """
        hub_acts = self.index.hub_activations()
        total = self.index.total_activation()
        new_clips: list[TicketRecord] = []

        for hub, shard_indices in HUB_SHARD_MAP.items():
            act = hub_acts.get(hub, 0.0)
            if act >= self.threshold:
                record = TicketRecord(
                    step=step,
                    hub=hub,
                    shard_indices=shard_indices,
                    hub_activation=act,
                    total_activation=total,
                )
                new_clips.append(record)

        with self._lock:
            self._log.extend(new_clips)

        return new_clips

    def propagate_and_clip(
        self,
        steps: int = 1,
        mode: str = "isometric",
    ) -> list[TicketRecord]:
        """
        Propagate the index for `steps` cycles, clipping a ticket at each step.

        Parameters
        ----------
        steps : propagation cycles
        mode  : passed directly to HarmonicIndex.propagate()

        Returns
        -------
        All TicketRecords clipped during this call.
        """
        clipped: list[TicketRecord] = []
        current_step = self.index._step_count
        for k in range(steps):
            self.index.propagate(1, mode=mode)
            new_clips = self.clip_step(current_step + k + 1)
            clipped.extend(new_clips)
        return clipped

    @property
    def log(self) -> list[TicketRecord]:
        """Full history of all clipped tickets, oldest first."""
        with self._lock:
            return list(self._log)

    def clear(self) -> None:
        with self._lock:
            self._log.clear()

    def journey_summary(self) -> dict:
        """
        Compact summary of the clipped journey: which hubs were activated,
        in order, with peak dominance ratios.
        """
        with self._lock:
            log = list(self._log)

        if not log:
            return {"hubs_clipped": [], "total_clips": 0}

        hub_order: list[str] = []
        seen: set[str] = set()
        peak_dominance: dict[str, float] = {}

        for record in log:
            if record.hub not in seen:
                hub_order.append(record.hub)
                seen.add(record.hub)
            dr = record.dominance_ratio
            if dr > peak_dominance.get(record.hub, 0.0):
                peak_dominance[record.hub] = dr

        return {
            "hubs_clipped": hub_order,
            "total_clips": len(log),
            "peak_dominance": {h: round(v, 6) for h, v in peak_dominance.items()},
            "n_hubs_visited": len(hub_order),
        }


# ---------------------------------------------------------------------------
# Path-space expansion helper
# ---------------------------------------------------------------------------


def cosine_path_count(n_shards: int, k_steps: int) -> int:
    """
    Number of distinct k-step routing paths on an n-shard ring under the
    isometric cosine kernel (all-to-all coupling, no self-loops).

    With nearest-neighbour propagation: 2^k paths per source.
    With isometric cosine (every shard coupled to every other):
        (n - 1)^k paths per source × n sources = n · (n-1)^k total.

    The cosine kernel makes ALL n−1 destinations reachable from any shard
    in ONE hop (positive or negative weight), so the path space is n · (n-1)^k.
    """
    return n_shards * (n_shards - 1) ** k_steps
