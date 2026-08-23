"""
CairnBridge — local CAIRRN state machine for OctopusTracer autonomy.

Implements the full CAIRRN three-layer modulation pipeline locally, without
any external MCP calls. The bridge:

    1. Maintains hub activation state across cycles
    2. Runs each vault metric through Ana-Chi → neg_exp sharding → coherence
    3. Exposes per-hub coherence scores to the TracerDaemon as spawn signals
    4. Propagates activation through the harmonic ring on each tick

Hub geometry (from CAIRRN SKILL.md):
    HOME          χ=1.5414  gravity=3.00  rattling=no   decay=0.98
    MATH          χ=1.9600  gravity=2.00  rattling=yes  decay=0.95
    CODE          χ=0.9900  gravity=1.50  rattling=yes  decay=0.93
    COMMANDS      χ=2.6700  gravity=1.00  rattling=yes  decay=0.90
    agent-context χ=0.0300  gravity=0.50  rattling=no   decay=0.90

Shard mapping (neg_exp):
    shard = floor(e^χ × 8 / 14.44)  clamped to [0, 7]

Coherence (Layer 3):
    coherence = exp(−steps / τ_hub)  — per-hub time constant
    τ_hub derived from memory_decay: τ = -1 / log(decay)
        HOME          τ ≈ 49.5   (slow — graph topology is stable)
        MATH          τ ≈ 19.5   (medium)
        CODE          τ ≈ 13.8   (medium-fast)
        COMMANDS      τ ≈  9.5   (fast — actionable signals)
        agent-context τ ≈  9.5   (fast — agent write activity)
    fixed point x* = −W(1) ≈ −0.5671432904097838
    if coherence < 0.50 → hub flagged incoherent → route to HOME

Harmonic propagation:
    κ = 0.15  (coupling constant)
    α = 1.96  (double-well attractor locations)
    Each propagation step: index[i] += κ × (index[i-1] + index[i+1]) − α × index[i]

Usage from TracerDaemon:
    bridge = CairnBridge()
    bridge.step("CODE", metric=0.85)          # run CODE hub pipeline
    signals = bridge.spawn_signals(threshold=0.50)  # {hub: coherence} for spawning
    bridge.propagate(steps=1)                 # diffuse activation through ring
    bridge.decay_all()                        # apply memory decay to all hubs
"""
import math
import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("cairrn_bridge")


# ── Welford sliding-window z-score tracker ─────────────────────────────────────

class WelfordWindow:
    """
    Online mean / variance over a fixed-size sliding window.

    Uses the compensated-sum trick for O(1) amortised updates:
        on eviction of the oldest value, subtract its contribution from
        _sum and _sum_sq before appending the new one.

    Numerically stable for the value ranges CAIRRN produces
    (activations in [0, ~10], z-scores in [−5, +5]).

    z_score(x) returns the z-score of x against the current window,
    or 0.0 when fewer than 2 samples exist (undefined variance).
    """

    def __init__(self, window: int = 32) -> None:
        self._buf: deque = deque(maxlen=window)
        self._sum:    float = 0.0
        self._sum_sq: float = 0.0

    def push(self, x: float) -> None:
        if len(self._buf) == self._buf.maxlen:
            old = self._buf[0]          # will be evicted by deque
            self._sum    -= old
            self._sum_sq -= old * old
        self._buf.append(x)
        self._sum    += x
        self._sum_sq += x * x

    @property
    def n(self) -> int:
        return len(self._buf)

    @property
    def mean(self) -> float:
        return self._sum / self.n if self.n > 0 else 0.0

    @property
    def variance(self) -> float:
        if self.n < 2:
            return 0.0
        # Sample variance: (Σx² − (Σx)²/n) / (n − 1)
        return max(0.0, (self._sum_sq - self._sum ** 2 / self.n) / (self.n - 1))

    @property
    def std(self) -> float:
        return math.sqrt(self.variance)

    def z_score(self, x: float) -> float:
        """z-score of x relative to the current window. Returns 0.0 if std ≈ 0."""
        s = self.std
        if s < 1e-8:
            return 0.0
        return (x - self.mean) / s

# ── Fixed point of −eˣ (Lambert W(1)) ─────────────────────────────────────────
_FIXED_POINT: float = -0.5671432904097838

# ── Hub definitions ────────────────────────────────────────────────────────────
_HUB_PARAMS: Dict[str, dict] = {
    # tau = -1 / log(decay)  — so coherence(t) ≈ decay^t, matching Ana-Chi memory decay.
    # Per-hub taus make the five hubs evolve at different rates rather than in lockstep.
    "HOME":          {"chi": 1.5414, "gravity": 3.00, "rattling": False, "decay": 0.98, "tau": 49.5},
    "MATH":          {"chi": 1.9600, "gravity": 2.00, "rattling": True,  "decay": 0.95, "tau": 19.5},
    "CODE":          {"chi": 0.9900, "gravity": 1.50, "rattling": True,  "decay": 0.93, "tau": 13.8},
    "COMMANDS":      {"chi": 2.6700, "gravity": 1.00, "rattling": True,  "decay": 0.90, "tau":  9.5},
    "agent-context": {"chi": 0.0300, "gravity": 0.50, "rattling": False, "decay": 0.90, "tau":  9.5},
}

_HARMONIC_SHARDS: int = 8
_KAPPA:           float = 0.15    # harmonic coupling constant
_ALPHA:           float = 1.96    # double-well attractor


@dataclass
class HubState:
    """Live state of one CAIRRN hub."""
    name:            str
    chi:             float         # Ana-Chi basin value
    gravity:         float
    rattling:        bool
    memory_decay:    float         # per-cycle decay factor
    tau:             float         # coherence time constant (hub-specific)
    activation:      float = 0.0  # current modulated activation
    shard:           int   = 0    # natural shard assignment
    steps:           int   = 0    # steps since last coherence reset
    coherence:       float = 1.0  # exp(−steps / τ_hub)
    last_metric:     float = 0.0
    z_awareness:     float = 0.0  # z-score of activation vs rolling window history


@dataclass
class PipelineResult:
    """Result of running one metric through the three-layer CAIRRN pipeline."""
    hub:          str
    metric:       float
    modulated:    float   # after Ana-Chi (Layer 1)
    shard:        int     # after neg_exp sharding (Layer 2)
    coherence:    float   # after coherence enforcement (Layer 3)
    coherent:     bool    # True if coherence ≥ 0.50
    rerouted:     bool    # True if rerouted to HOME due to incoherence
    z_awareness:  float = 0.0  # z-score of this step's activation


# ──────────────────────────────────────────────────────────────────────────────
# CairnBridge
# ──────────────────────────────────────────────────────────────────────────────

class CairnBridge:
    """
    Local CAIRRN pipeline — drives OctopusTracer spawn conditions without
    any external MCP calls.

    Args:
        tau:               coherence time constant (default 30 steps)
        coherence_floor:   hub coherence below this signals a spawn trigger
        harmonic_shards:   number of shards in the harmonic ring (default 8)
    """

    def __init__(
        self,
        tau: float = 30.0,
        coherence_floor: float = 0.50,
        harmonic_shards: int = _HARMONIC_SHARDS,
        z_window: int = 32,
        z_spawn_threshold: float = 2.5,
    ) -> None:
        self.tau = tau
        self.coherence_floor = coherence_floor
        self.harmonic_shards = harmonic_shards
        self.z_window = z_window
        self.z_spawn_threshold = z_spawn_threshold

        # Initialise hub states.
        # Each hub uses its own tau from _HUB_PARAMS so the five hubs evolve at
        # different rates.  Pass override_tau= to force a uniform tau (ablations).
        self._hubs: Dict[str, HubState] = {}
        for name, p in _HUB_PARAMS.items():
            shard = self._chi_to_shard(p["chi"])
            self._hubs[name] = HubState(
                name=name,
                chi=p["chi"],
                gravity=p["gravity"],
                rattling=p["rattling"],
                memory_decay=p["decay"],
                tau=p["tau"],
                shard=shard,
            )

        # Per-hub sliding-window stats for z-awareness computation.
        self._z_stats: Dict[str, WelfordWindow] = {
            name: WelfordWindow(window=z_window) for name in _HUB_PARAMS
        }

        # Harmonic index — 8-shard ring (maps to hub shards)
        self._index: List[float] = [0.0] * harmonic_shards
        self._global_step: int = 0

        # Incoherence events captured during the last ingest cycle.
        # Populated BEFORE the step-reset so spawn_signals() can read them.
        # Cleared at the start of each ingest_vault_snapshot() call.
        self._incoherence_events: Dict[str, float] = {}   # hub_name → pre-reset coherence

        # Z-awareness events — hubs whose |z| crossed z_spawn_threshold this cycle.
        # Cleared alongside _incoherence_events at the start of each ingest.
        self._z_events: Dict[str, float] = {}             # hub_name → z_score

    # ──────────────────────────────────────────────────────────────────────────
    # Layer 1 — Ana-Chi modulation
    # ──────────────────────────────────────────────────────────────────────────

    def _ana_chi_modulate(self, hub: HubState, metric: float) -> float:
        """
        modulated = metric × gravity × (memory_decay^steps  if rattling else 1)
        """
        if hub.rattling:
            mem = hub.memory_decay ** max(hub.steps, 1)
            return metric * hub.gravity * mem
        return metric * hub.gravity

    # ──────────────────────────────────────────────────────────────────────────
    # Layer 2 — neg_exp sharding
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _chi_to_shard(chi: float) -> int:
        """
        shard = floor(e^χ × 8 / 14.44)  clamped to [0, 7]
        Derived from the neg_exp map f(x) = −eˣ.
        """
        return min(7, int(math.exp(chi) * 8 / 14.44))

    # ──────────────────────────────────────────────────────────────────────────
    # Layer 3 — coherence enforcement
    # ──────────────────────────────────────────────────────────────────────────

    def _coherence(self, steps: int, tau: float) -> float:
        """exp(−steps / τ_hub)  — matches CAIRRN Layer 3 with per-hub time constant."""
        return math.exp(-steps / tau)

    # ──────────────────────────────────────────────────────────────────────────
    # Main pipeline
    # ──────────────────────────────────────────────────────────────────────────

    def step(self, hub_name: str, metric: float) -> PipelineResult:
        """
        Run one metric through the full three-layer CAIRRN pipeline for a hub.

        Layer 1: Ana-Chi modulation
        Layer 2: neg_exp sharding → target shard
        Layer 3: coherence enforcement → flag incoherent, reroute if needed

        Injects the modulated value into the harmonic index at the target shard.
        If incoherent, re-routes to HOME hub instead.

        Args:
            hub_name: one of HOME, MATH, CODE, COMMANDS, agent-context
            metric:   raw scalar metric to feed through pipeline

        Returns:
            PipelineResult with all intermediate values
        """
        if hub_name not in self._hubs:
            raise ValueError(f"Unknown CAIRRN hub: {hub_name}. Valid: {list(self._hubs)}")

        hub = self._hubs[hub_name]
        hub.steps += 1
        hub.last_metric = metric
        self._global_step += 1

        # Layer 1
        modulated = self._ana_chi_modulate(hub, metric)
        hub.activation = modulated

        # Layer 2
        shard = self._chi_to_shard(hub.chi)

        # Layer 3 — use hub's own tau so each hub decays at its characteristic rate
        coherence = self._coherence(hub.steps, hub.tau)
        hub.coherence = coherence
        coherent  = coherence >= self.coherence_floor
        rerouted  = False

        if not coherent:
            logger.debug(
                "Hub %s incoherent (coherence=%.3f) — rerouting to HOME", hub_name, coherence
            )
            # Record the event BEFORE resetting so spawn_signals() can see it.
            # The reset zeroes hub.coherence back to 1.0, which would otherwise
            # make spawn_signals() miss the trigger entirely (Bug: dead-on-arrival).
            self._incoherence_events[hub_name] = coherence

            # Reroute: inject into HOME shard instead, reset hub steps
            hub.steps = 0
            hub.coherence = 1.0
            shard = self._hubs["HOME"].shard
            rerouted = True

        # Inject into harmonic index
        self._index[shard] = modulated

        # ── z-awareness — push modulated into this hub's rolling window, then score ──
        stats = self._z_stats[hub_name]
        stats.push(modulated)
        z = stats.z_score(modulated)
        hub.z_awareness = z

        if abs(z) >= self.z_spawn_threshold:
            # Record before any reset so signals survive the ingest boundary.
            self._z_events[hub_name] = z
            logger.debug(
                "Hub %s z-awareness spike  z=%.3f  (threshold=%.1f)",
                hub_name, z, self.z_spawn_threshold,
            )

        result = PipelineResult(
            hub=hub_name,
            metric=metric,
            modulated=modulated,
            shard=shard,
            coherence=coherence,
            coherent=coherent,
            rerouted=rerouted,
            z_awareness=z,
        )

        logger.debug(
            "CAIRRN %s  metric=%.3f  modulated=%.3f  shard=%d  coherence=%.3f  z=%.3f  %s",
            hub_name, metric, modulated, shard, coherence, z,
            "REROUTED→HOME" if rerouted else "✓",
        )
        return result

    # ──────────────────────────────────────────────────────────────────────────
    # Harmonic propagation
    # ──────────────────────────────────────────────────────────────────────────

    def propagate(self, steps: int = 1) -> List[float]:
        """
        Diffuse activation through the harmonic ring for N steps.

        Each step:
            index[i] += κ × (index[i-1] + index[i+1]) − α × index[i]
        Ring is circular (periodic boundary).

        Returns final index state.
        """
        n = self.harmonic_shards
        for _ in range(steps):
            new_index = list(self._index)
            for i in range(n):
                left  = self._index[(i - 1) % n]
                right = self._index[(i + 1) % n]
                new_index[i] = (
                    self._index[i]
                    + _KAPPA * (left + right)
                    - _ALPHA * self._index[i]
                )
            self._index = new_index
        return list(self._index)

    # ──────────────────────────────────────────────────────────────────────────
    # Decay
    # ──────────────────────────────────────────────────────────────────────────

    def decay_all(self) -> None:
        """Apply memory decay to all hub activations (one cycle tick)."""
        for hub in self._hubs.values():
            hub.activation *= hub.memory_decay

    # ──────────────────────────────────────────────────────────────────────────
    # Spawn signals for TracerDaemon
    # ──────────────────────────────────────────────────────────────────────────

    def spawn_signals(
        self,
        threshold: Optional[float] = None,
        include_z: bool = False,
    ) -> Dict[str, float]:
        """
        Return {hub_name: coherence} for hubs that crossed the incoherence floor
        during the most recent ingest_vault_snapshot() call.

        The values are the pre-reset coherence scores (i.e. how far below the
        floor the hub dropped before being re-routed to HOME).  Hubs that are
        still below floor without having been reset are also included.

        Args:
            threshold:  override the coherence floor (default: self.coherence_floor)
            include_z:  if True, also merge z-awareness spike events into the
                        returned dict.  Z-triggered keys use the raw z-score as
                        value (which will be ≥ z_spawn_threshold in absolute terms).
                        Key collisions are won by the coherence signal.

        TracerDaemon reads this after each ingest+propagate cycle to decide
        which hubs warrant a new tracer spawn.
        """
        floor = threshold if threshold is not None else self.coherence_floor

        # Start with events captured during the last ingest (pre-reset values)
        signals = dict(self._incoherence_events)

        # Also include any hubs currently below floor (in case they drifted
        # without triggering a hard reset — e.g. partial metric ingestion)
        for name, hub in self._hubs.items():
            if hub.coherence < floor and name not in signals:
                signals[name] = hub.coherence

        if include_z:
            for name, z in self._z_events.items():
                if name not in signals:          # coherence signal takes precedence
                    signals[name] = z

        return signals

    def z_awareness_signals(
        self,
        threshold: Optional[float] = None,
    ) -> Dict[str, float]:
        """
        Return {hub_name: z_score} for hubs whose |z_awareness| exceeded the
        z-spawn threshold during the most recent ingest_vault_snapshot() call.

        Positive z → hub activation is unusually HIGH (burst of activity).
        Negative z → hub activation is unusually LOW  (sudden quiet / collapse).

        Use this alongside spawn_signals() for a richer picture of system state:
            coherence signals  → the hub has been running too long without reset
            z-awareness signals → the hub is in a statistically anomalous state NOW

        Args:
            threshold: override z_spawn_threshold (default: self.z_spawn_threshold)
        """
        floor = threshold if threshold is not None else self.z_spawn_threshold

        # Events from the last ingest cycle
        events = {k: v for k, v in self._z_events.items() if abs(v) >= floor}

        # Also catch hubs whose current z is anomalous but didn't fire an event
        # (e.g. they spiked mid-cycle before _z_events was populated)
        for name, hub in self._hubs.items():
            if abs(hub.z_awareness) >= floor and name not in events:
                events[name] = hub.z_awareness

        return events

    def all_coherent(self) -> bool:
        """True when all hubs are above the coherence floor."""
        return all(hub.coherence >= self.coherence_floor for hub in self._hubs.values())

    def global_coherence(self) -> float:
        """Mean coherence across all hubs."""
        scores = [hub.coherence for hub in self._hubs.values()]
        return sum(scores) / len(scores)

    def global_z_awareness(self) -> float:
        """
        System-level z-awareness: mean |z_awareness| across all hubs, weighted
        by each hub's gravity so high-gravity hubs (HOME, MATH) contribute more.

        Returns 0.0 when no hub has seen enough samples to compute a z-score
        (i.e. window still filling up). Increases as the system deviates from
        its own statistical baseline — a useful single-number "how surprised is
        CAIRRN right now?" signal.

        Interpretation:
            0.0 – 1.0   normal operating range
            1.0 – 2.5   mildly anomalous — monitor
            ≥ 2.5       z-hot: at least one hub is statistically unusual
        """
        total_weight = 0.0
        weighted_z   = 0.0
        for name, hub in self._hubs.items():
            w = hub.gravity
            weighted_z   += abs(hub.z_awareness) * w
            total_weight += w
        return weighted_z / total_weight if total_weight > 0 else 0.0

    # ──────────────────────────────────────────────────────────────────────────
    # Metrics injection — vault-derived metrics enter through these helpers
    # ──────────────────────────────────────────────────────────────────────────

    def ingest_arm_scores(self, arm_scores: Dict[str, float]) -> None:
        """
        Route OctopusTracer arm score means through the harmonic sharding system.

        Unlike ingest_vault_snapshot(), this does NOT step hub coherence clocks,
        does NOT clear incoherence events, and does NOT generate new events.
        It only blends modulated arm values into the harmonic index shards,
        so tracer feedback influences ring propagation without inflating spawn
        pressure beyond what the vault topology drives.

        Arm → hub routing (mirrors CAIRRN semantic intent):

            prune  + sprout  → COMMANDS     (actionable structural interventions)
            graft  + rank    → HOME         (graph topology / link centrality)
            cluster + tag    → MATH         (conceptual / mathematical structure)
            merge            → CODE         (content density / deduplication)
            resurface        → agent-context (agent discovery backlog)

        Harmonic blending (exponential moving average, α=0.5):
            index[shard] = 0.5 × old + 0.5 × modulated

        Args:
            arm_scores: dict with float values for any/all of:
                prune, graft, cluster, rank, resurface, sprout, tag, merge
                Missing keys default to 0.0.
        """
        def _clip(key: str) -> float:
            return min(1.0, max(0.0, float(arm_scores.get(key, 0.0))))

        routing = {
            "COMMANDS":      0.5 * (_clip("prune")   + _clip("sprout")),
            "HOME":          0.5 * (_clip("graft")   + _clip("rank")),
            "MATH":          0.5 * (_clip("cluster") + _clip("tag")),
            "CODE":          _clip("merge"),
            "agent-context": _clip("resurface"),
        }

        for hub_name, metric in routing.items():
            hub = self._hubs[hub_name]
            # Layer 1: Ana-Chi modulation using current hub state (gravity + rattling decay)
            # Steps are NOT incremented — we're reading state, not advancing the clock.
            modulated = self._ana_chi_modulate(hub, metric)
            shard = hub.shard
            # Exponential moving average blend — preserves vault signal, adds arm pressure
            self._index[shard] = 0.5 * self._index[shard] + 0.5 * modulated

        logger.debug(
            "CAIRRN arm routing → HOME=%.3f MATH=%.3f CODE=%.3f COMMANDS=%.3f ctx=%.3f",
            routing["HOME"], routing["MATH"], routing["CODE"],
            routing["COMMANDS"], routing["agent-context"],
        )

    def ingest_vault_snapshot(self, snapshot: dict) -> None:
        """
        Feed vault topology snapshot into CAIRRN hubs automatically.

        Accepts both key formats:
          Full topology (topo.snapshot):  "chi", "beta_1", "V", "orphan_count", "links_written"
          Lightweight (graph_snapshot):   "euler_chi", "nodes", "edges", "density", "components"

        Routing:
            chi / euler_chi             → HOME          (graph shape)
            beta_1 / edges              → MATH          (structural complexity)
            V / nodes                   → CODE          (symbol density proxy)
            orphan_count / components   → COMMANDS      (actionable isolation signals)
            links_written / density     → agent-context (write activity)
        """
        # Clear events from the previous cycle so signals only reflect THIS ingest.
        self._incoherence_events.clear()
        self._z_events.clear()

        # Normalise keys — prefer full topology keys, fall back to lightweight keys.
        inv_chi  = float(snapshot.get("chi",          snapshot.get("euler_chi",   0.0)))
        beta_1   = float(snapshot.get("beta_1",       snapshot.get("edges",       0)))
        V        = float(snapshot.get("V",             snapshot.get("nodes",       1)))
        orphans  = float(snapshot.get("orphan_count",  snapshot.get("components",  0)))
        links_out = float(snapshot.get("links_written", snapshot.get("density",    0.0)))

        V = max(V, 1)   # guard against empty graph

        # Normalise to [0, 1] for safe pipeline input
        self.step("HOME",          min(1.0, abs(inv_chi) / 10.0))
        self.step("MATH",          min(1.0, beta_1 / V))
        self.step("CODE",          min(1.0, V / 5000.0))
        self.step("COMMANDS",      min(1.0, orphans / V))
        self.step("agent-context", min(1.0, links_out))

    # ──────────────────────────────────────────────────────────────────────────
    # State inspection
    # ──────────────────────────────────────────────────────────────────────────

    def hub_state(self) -> Dict[str, dict]:
        """Full hub state snapshot, suitable for logging."""
        return {
            name: {
                "activation":  round(hub.activation, 4),
                "shard":       hub.shard,
                "tau":         round(hub.tau, 1),
                "coherence":   round(hub.coherence, 4),
                "steps":       hub.steps,
                "coherent":    hub.coherence >= self.coherence_floor,
                "z_awareness": round(hub.z_awareness, 4),
                "z_window_n":  self._z_stats[name].n,
            }
            for name, hub in self._hubs.items()
        }

    def index_state(self) -> List[float]:
        """Current harmonic index (8-shard ring)."""
        return [round(v, 4) for v in self._index]

    def report(self) -> str:
        """Human-readable one-line summary including z-awareness."""
        coh = self.global_coherence()
        incoherent = [n for n, h in self._hubs.items() if h.coherence < self.coherence_floor]
        z_hot = [
            f"{n}({h.z_awareness:+.2f})"
            for n, h in self._hubs.items()
            if abs(h.z_awareness) >= self.z_spawn_threshold
        ]
        coh_flag = f"  ⚠ incoherent: {incoherent}" if incoherent else "  ✓ all coherent"
        z_flag   = f"  ⚡ z-hot: {z_hot}" if z_hot else ""
        gz = self.global_z_awareness()
        return (
            f"CAIRRN step={self._global_step}  "
            f"global_coh={coh:.3f}  global_z={gz:.3f}"
            f"{coh_flag}{z_flag}"
        )
