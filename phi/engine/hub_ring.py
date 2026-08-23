# -*- coding: utf-8 -*-
"""phi.engine.hub_ring — Music-domain harmonic hub/spoke ring for phi.

A dedicated 8-shard HarmonicIndex whose shards map to music-semantic domains,
separate from both the MCP station-hub ring and the CAIRRN operational ring.

Hub layout (shard → basin centre = k·α, α=1.96):
    shard 0   1.96   PLAYBACK   live track state, queue position
    shard 1   3.92   ENERGY     tempo, loudness, valence energy blend
    shard 2   5.88   MOOD       emotional arc, danceability
    shard 3   7.84   GENRE      style, speechiness, acousticness
    shard 4   9.80   ARTIST     artist / album context in vault
    shard 5  11.76   TOPOLOGY   graph health χ, β₁ from TopologicalInvariant
    shard 6  13.72   VAULT      Obsidian PSSPPS retrieval signal
    shard 7  15.68   MEMORY     long-term session history depth

β₁ coupling modulation
-----------------------
The vault's first Betti number β₁ (independent cycles in the Obsidian graph)
tunes the ring coupling κ at each topology update:

    κ_eff = min(κ_base × (1 + β₁ / V), KAPPA_MAX)

Rich cross-links (high β₁) → stronger inter-hub propagation and broader
context spreading.  Sparse vault → localised activations.

Spoke retrieval
---------------
active_spoke_queries() returns {hub: query_str} for every hub whose
activation is above the threshold — ready to feed directly into PSSPPS.

Injection protocol
------------------
On each track load the caller should:

    ring.inject_track_features(spotify_features)   # audio → ENERGY/MOOD/GENRE/ARTIST
    ring.inject("PLAYBACK", 1.0)                   # mark track start
    ring.modulate_kappa(topo_invariant)            # β₁ tunes coupling
    ring.inject_topology(topo_invariant)           # χ/β₁ → TOPOLOGY hub
    ring.propagate(steps=2, mode="resonance")      # diffuse
    queries = ring.active_spoke_queries()          # pull vault context
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from sims.harmonic import HarmonicIndex

# TopologicalInvariant pulled in for type hints only — avoids the heavy
# data/__init__.py import if topology is used standalone.
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from phi.topology.primitives import TopologicalInvariant

_log = logging.getLogger("phi.engine.hub_ring")

# ── Physics ────────────────────────────────────────────────────────────────────

BASE_KAPPA: float = 0.15   # default coupling constant
KAPPA_MAX:  float = 0.45   # hard ceiling — LocalPropagator requires κ < 0.5
DEFAULT_THRESHOLD: float = 0.30

# ── Hub → shard map ────────────────────────────────────────────────────────────

PHI_MUSIC_HUBS: Dict[str, int] = {
    "PLAYBACK":  0,  # 1·α  = 1.96
    "ENERGY":    1,  # 2·α  = 3.92
    "MOOD":      2,  # 3·α  = 5.88
    "GENRE":     3,  # 4·α  = 7.84
    "ARTIST":    4,  # 5·α  = 9.80
    "TOPOLOGY":  5,  # 6·α  = 11.76
    "VAULT":     6,  # 7·α  = 13.72
    "MEMORY":    7,  # 8·α  = 15.68
}

SHARD_HUB: Dict[int, str] = {v: k for k, v in PHI_MUSIC_HUBS.items()}

# ── Vault spoke paths (relative to VAULT_ROOT) ────────────────────────────────

PHI_SPOKE_PATHS: Dict[str, str] = {
    "PLAYBACK":  "music/PLAYBACK.md",
    "ENERGY":    "music/ENERGY.md",
    "MOOD":      "music/MOOD.md",
    "GENRE":     "music/GENRE.md",
    "ARTIST":    "music/ARTIST.md",
    "TOPOLOGY":  "music/TOPOLOGY.md",
    "VAULT":     "music/VAULT.md",
    "MEMORY":    "music/MEMORY.md",
}

# Default PSSPPS retrieval queries per hub
PHI_SPOKE_QUERIES: Dict[str, str] = {
    "PLAYBACK":  "track playback queue session state",
    "ENERGY":    "energy tempo bpm loudness intensity drive",
    "MOOD":      "mood valence emotion feel danceability atmosphere",
    "GENRE":     "genre style classification acoustic instrumental texture",
    "ARTIST":    "artist album release credits production",
    "TOPOLOGY":  "topology graph euler beta chi connectivity",
    "VAULT":     "retrieval obsidian vault notes context discovery",
    "MEMORY":    "session history memory listen long-term pattern",
}

# ── Audio feature → hub injection map ────────────────────────────────────────
# Each entry: feature_name → (hub, scale)
# scale is applied before clamping to [0, 1].
# loudness is [-60, 0] dB; all others are already [0, 1].

_FEATURE_ROUTES: Dict[str, tuple[str, float]] = {
    "energy":           ("ENERGY",  1.0),
    "tempo":            ("ENERGY",  1 / 200.0),   # ~200 BPM max
    "loudness":         ("ENERGY",  1 / 60.0),    # loudness + 60, then scale
    "valence":          ("MOOD",    1.0),
    "danceability":     ("MOOD",    1.0),
    "speechiness":      ("GENRE",   1.0),
    "acousticness":     ("GENRE",   1.0),
    "instrumentalness": ("GENRE",   1.0),
    "liveness":         ("ARTIST",  1.0),
}


@dataclass
class HubInjectionRecord:
    """Snapshot of a single hub injection event (for debugging and logging)."""
    hub:    str
    shard:  int
    value:  float
    source: str = "direct"


# ── PhiHubRing ────────────────────────────────────────────────────────────────


class PhiHubRing:
    """
    Music-domain hub/spoke ring for phi.

    Wraps a dedicated HarmonicIndex (8 shards) with the PHI_MUSIC_HUBS mapping,
    β₁-modulated coupling, and spoke retrieval query generation.

    This ring is entirely independent of the MCP station-hub ring and the
    CAIRRN operational ring.  Do not share the underlying HarmonicIndex with
    either of those systems.

    Parameters
    ----------
    base_kappa  : float
        Starting coupling constant.  Modulated by inject_topology().
    threshold   : float
        Activation floor used by active_hubs() and active_spoke_queries().
    """

    def __init__(
        self,
        base_kappa: float = BASE_KAPPA,
        threshold:  float = DEFAULT_THRESHOLD,
    ) -> None:
        if not (0.0 < base_kappa < 0.5):
            raise ValueError(f"base_kappa must be in (0, 0.5); got {base_kappa}")
        self._base_kappa = base_kappa
        self.threshold   = threshold
        self._ring       = HarmonicIndex(n_harmonics=8, coupling=base_kappa)
        self._last_injection_log: list[HubInjectionRecord] = []
        self._last_inv: Optional["TopologicalInvariant"] = None

    # ── Direct injection ──────────────────────────────────────────────────────

    def inject(self, hub: str, value: float) -> None:
        """
        Inject activation directly into a named hub.

        Parameters
        ----------
        hub   : one of PHI_MUSIC_HUBS — "PLAYBACK", "ENERGY", …
        value : activation magnitude (any float; typically [0, 1])
        """
        shard = PHI_MUSIC_HUBS.get(hub)
        if shard is None:
            raise ValueError(
                f"Unknown hub {hub!r}. Valid hubs: {list(PHI_MUSIC_HUBS)}"
            )
        self._ring.inject(shard, value)
        self._last_injection_log.append(
            HubInjectionRecord(hub=hub, shard=shard, value=value)
        )
        _log.debug("inject %s (shard %d) += %.4f", hub, shard, value)

    # ── Audio feature injection ───────────────────────────────────────────────

    def inject_track_features(self, features: Dict[str, float]) -> List[HubInjectionRecord]:
        """
        Map Spotify audio features to hub injections and apply them.

        Recognised keys: energy, tempo, loudness, valence, danceability,
        speechiness, acousticness, instrumentalness, liveness.
        Unknown keys are silently skipped.

        Multi-feature hubs (ENERGY receives energy + tempo + loudness;
        GENRE receives speechiness + acousticness + instrumentalness) take the
        mean of all contributing values so that every injection is normalised
        to [0, 1] regardless of how many features arrive.

        Parameters
        ----------
        features : dict of Spotify audio feature name → float value

        Returns
        -------
        List of HubInjectionRecord for every hub that was injected.
        """
        # Accumulate per-hub contributions
        hub_values: Dict[str, list[float]] = {h: [] for h in PHI_MUSIC_HUBS}

        for feat, raw in features.items():
            route = _FEATURE_ROUTES.get(feat)
            if route is None:
                continue
            hub, scale = route
            if feat == "loudness":
                # loudness ∈ [-60, 0] dB — shift then scale
                val = max(0.0, min(1.0, (raw + 60.0) * scale))
            else:
                val = max(0.0, min(1.0, raw * scale))
            hub_values[hub].append(val)

        records: list[HubInjectionRecord] = []
        for hub, vals in hub_values.items():
            if not vals:
                continue
            blended = sum(vals) / len(vals)
            shard   = PHI_MUSIC_HUBS[hub]
            self._ring.inject(shard, blended)
            rec = HubInjectionRecord(
                hub=hub, shard=shard, value=blended, source="audio_features"
            )
            records.append(rec)
            _log.debug(
                "inject_track_features %s (shard %d) = %.4f  (n=%d features)",
                hub, shard, blended, len(vals),
            )

        self._last_injection_log.extend(records)
        return records

    # ── Topology injection & κ modulation ────────────────────────────────────

    def modulate_kappa(self, invariant: "TopologicalInvariant") -> float:
        """
        Adjust ring coupling based on vault topology.

            κ_eff = min(κ_base × (1 + β₁ / V), KAPPA_MAX)

        Higher β₁ (more independent cycles in the vault) → broader propagation.
        Updates all three propagators on the underlying ring.
        Also caches the invariant so last_t_b() can surface T_B to vault_context.

        Parameters
        ----------
        invariant : TopologicalInvariant from TopologicalGraph.build()

        Returns
        -------
        The new effective κ.
        """
        self._last_inv = invariant

        V      = max(invariant.V, 1)
        kappa  = self._base_kappa * (1.0 + invariant.beta_1 / V)
        kappa  = min(kappa, KAPPA_MAX)

        # Update propagators directly — no need to rebuild the ring
        self._ring._propagator.coupling             = kappa
        self._ring._resonance_propagator.coupling   = min(kappa, 0.99)
        self._ring._isometric_propagator.coupling   = min(kappa, 0.99)

        _log.debug(
            "modulate_kappa  β₁=%d  V=%d  κ_eff=%.4f  T_B=%.3f  (base=%.4f)",
            invariant.beta_1, V, kappa, invariant.t_b, self._base_kappa,
        )
        return kappa

    def last_t_b(self) -> float:
        """
        Return raw T_B from the most recently seen TopologicalInvariant.

        Returns 0.0 if no invariant has been received yet.
        """
        return self._last_inv.t_b if self._last_inv is not None else 0.0

    def last_t_b_norm(self) -> float:
        """
        Return T_B_norm ∈ (−1, 1) from the most recently seen TopologicalInvariant.

        T_B_norm > 0 → deep basin → high perspective_alpha (local retrieval)
        T_B_norm ≈ 0 → neutral    → alpha ≈ 0.5
        T_B_norm < 0 → open basin → low perspective_alpha  (global retrieval)

        Returns 0.0 if no invariant has been received yet (alpha stays at 0.5).
        """
        return self._last_inv.t_b_norm if self._last_inv is not None else 0.0

    def inject_topology(self, invariant: "TopologicalInvariant") -> None:
        """
        Feed graph health metrics into the TOPOLOGY hub.

        Normalised signal = |χ| / (V + 1), clamped to [0, 1].  A more
        topologically complex vault (larger absolute χ) produces a stronger
        TOPOLOGY hub signal, attracting more vault-traversal context.

        Parameters
        ----------
        invariant : TopologicalInvariant from TopologicalGraph.build()
        """
        V      = max(invariant.V, 1)
        signal = min(1.0, abs(invariant.chi) / (V + 1))
        self.inject("TOPOLOGY", signal)

    # ── Propagation ───────────────────────────────────────────────────────────

    def propagate(self, steps: int = 2, mode: str = "resonance") -> None:
        """
        Advance the ring for `steps` propagation cycles.

        Parameters
        ----------
        steps : int   number of propagation cycles (default 2)
        mode  : str   "local" | "resonance" | "isometric"
                      Passed directly to HarmonicIndex.propagate().
        """
        self._ring.propagate(steps=steps, mode=mode)

    # ── Hub inspection ────────────────────────────────────────────────────────

    def activations(self) -> Dict[str, float]:
        """Return {hub: activation} for all 8 hubs."""
        acts = self._ring.activation_vector()
        return {SHARD_HUB[i]: round(float(acts[i]), 6) for i in range(8)}

    def active_hubs(self, threshold: Optional[float] = None) -> List[str]:
        """
        Return hub names whose activation is at or above `threshold`.

        Parameters
        ----------
        threshold : float | None  override self.threshold if provided

        Returns
        -------
        List of hub names sorted by activation descending.
        """
        floor = threshold if threshold is not None else self.threshold
        acts  = self.activations()
        above = [(hub, v) for hub, v in acts.items() if v >= floor]
        above.sort(key=lambda x: x[1], reverse=True)
        return [hub for hub, _ in above]

    def active_spoke_queries(
        self,
        threshold: Optional[float] = None,
    ) -> Dict[str, str]:
        """
        Return {hub: query_str} for every hub currently above threshold.

        Feed these strings directly into PSSPPS / vault_context.query().
        """
        return {
            hub: PHI_SPOKE_QUERIES[hub]
            for hub in self.active_hubs(threshold)
        }

    # ── Full cycle helper ─────────────────────────────────────────────────────

    def on_track_load(
        self,
        features:  Dict[str, float],
        invariant: Optional["TopologicalInvariant"] = None,
        vault_signal:   float = 0.0,
        memory_signal:  float = 0.0,
        propagate_steps: int  = 2,
        propagate_mode:  str  = "resonance",
    ) -> Dict[str, str]:
        """
        Full injection → propagation cycle on track load.

        Sequence:
            1. inject_track_features(features)
            2. inject("PLAYBACK", 1.0)
            3. modulate_kappa(invariant) + inject_topology(invariant)  [if given]
            4. inject("VAULT",  vault_signal)   [if > 0]
            5. inject("MEMORY", memory_signal)  [if > 0]
            6. propagate(steps, mode)
            7. return active_spoke_queries()

        Parameters
        ----------
        features        : Spotify audio feature dict
        invariant       : TopologicalInvariant (optional — topology hubs skipped if None)
        vault_signal    : PSSPPS retrieval confidence [0, 1] for this track
        memory_signal   : session history weight [0, 1]
        propagate_steps : propagation cycles
        propagate_mode  : propagation mode

        Returns
        -------
        dict hub → PSSPPS query string for all active hubs
        """
        self._last_injection_log.clear()

        self.inject_track_features(features)
        self.inject("PLAYBACK", 1.0)

        if invariant is not None:
            self.modulate_kappa(invariant)
            self.inject_topology(invariant)

        if vault_signal > 0.0:
            self.inject("VAULT", vault_signal)

        if memory_signal > 0.0:
            self.inject("MEMORY", memory_signal)

        self.propagate(steps=propagate_steps, mode=propagate_mode)

        queries = self.active_spoke_queries()
        _log.info(
            "on_track_load  active=%s  κ_base=%.3f",
            list(queries.keys()), self._base_kappa,
        )
        return queries

    # ── State / reset ─────────────────────────────────────────────────────────

    def state(self) -> dict:
        """Serialisable snapshot of the full ring state."""
        ring_state = self._ring.state()
        t_b      = self.last_t_b()
        t_b_norm = self.last_t_b_norm()
        # Import locally to avoid circular at module level
        from phi.engine.vault_context import _t_b_to_alpha
        psspps_alpha = _t_b_to_alpha(t_b_norm)
        return {
            **ring_state,
            "threshold":    self.threshold,
            "base_kappa":   self._base_kappa,
            # basin sequestration — drives PSSPPS perspective_alpha
            "t_b":          round(t_b, 4),
            "t_b_norm":     round(t_b_norm, 4),
            "psspps_alpha": round(psspps_alpha, 4),
            "hubs": [
                {
                    "hub":          SHARD_HUB[s["index"]],
                    "shard":        s["index"],
                    "basin_centre": s["basin_centre"],
                    "activation":   s["activation"],
                    "active":       s["activation"] >= self.threshold,
                    "spoke_path":   PHI_SPOKE_PATHS[SHARD_HUB[s["index"]]],
                }
                for s in ring_state["shards"]
            ],
        }

    def reset(self) -> None:
        """Zero all shard activations and step counter."""
        self._ring.reset()
        self._last_injection_log.clear()

    @property
    def injection_log(self) -> list[HubInjectionRecord]:
        """Records from the most recent on_track_load() call."""
        return list(self._last_injection_log)
