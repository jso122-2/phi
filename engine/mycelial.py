"""
MycelialNetwork — CAIRRN-aware soft edge activation for the Obsidian graph.

Biological model (from "Rationale: Mycelial Intelligence in DAWN"):
  - Notes are nodes (root tips / fungal junction points)
  - Samba GNN semantic scores are resting edge conductances
  - CAIRRN hub pipeline modulates activation along hyphae
  - harmonic_propagate diffuses activation N steps across the ring
  - Edges below threshold are dormant; above are lit (anastomosed)
  - C-layer: each hub's memory_decay applies every tick → hyphal dormancy

CAIRRN integration constants (from CAIRRN SKILL):
  κ = 0.15   harmonic coupling ≡ mycelial conductance constant
  α = 1.96   double-well attractor locations
  τ = 30     coherence half-life (steps)
  x* = −W(1) ≈ −0.5671   coherence fixed point

Pipeline layers:
  Layer 1 (Ana-Chi):  modulated = metric × gravity × (decay if rattling)
  Layer 2 (neg_exp):  shard = floor(e^χ × 8 / 14.44) clamped [0, 7]
  Layer 3 (coherence): coherence = exp(−steps / τ); < 0.50 → re-route HOME
"""
from __future__ import annotations

import json
import logging
import math
import os
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# CAIRRN hub table (from CAIRRN SKILL spec)
# ──────────────────────────────────────────────────────────────────────────────

CAIRRN_HUBS: Dict[str, Dict[str, Any]] = {
    "HOME":          {"basin": "true_center", "chi": 1.5414, "gravity": 3.00, "rattling": False, "decay": 0.98},
    "MATH":          {"basin": "white_peak",  "chi": 1.9600, "gravity": 2.00, "rattling": True,  "decay": 0.95},
    "CODE":          {"basin": "mirror",      "chi": 0.9900, "gravity": 1.50, "rattling": True,  "decay": 0.93},
    "COMMANDS":      {"basin": "escape",      "chi": 2.6700, "gravity": 1.00, "rattling": True,  "decay": 0.90},
    "agent-context": {"basin": "boundary",    "chi": 0.0300, "gravity": 0.50, "rattling": False, "decay": 0.90},
}

CAIRRN_KAPPA      = 0.15    # conductance constant κ — shared with mycelial g_ij
CAIRRN_COHERENCE_TAU = 30   # coherence half-life τ (steps)
CAIRRN_COHERENCE_THRESHOLD = 0.50
SOFT_EDGE_FLOOR   = 0.30    # resting score below which an edge is dormant


# ──────────────────────────────────────────────────────────────────────────────
# Data structures
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class HyphalEdge:
    """A single soft edge between two notes with live activation tracking."""
    source: str
    target: str
    resting_score: float        # Samba GNN semantic similarity [0, 1]
    activation: float           # current modulated activation strength
    hub: str                    # CAIRRN hub that last activated this edge
    shard: int                  # neg_exp shard routed to
    coherence: float            # last coherence score
    step: int                   # global tick when last activated
    decay_rate: float           # memory_decay from activating hub

    @property
    def conductance(self) -> float:
        """g_ij = sigmoid(κ * w_ij) — mycelial conductance from Samba score."""
        return 1.0 / (1.0 + math.exp(-CAIRRN_KAPPA * self.resting_score * 20))

    @property
    def is_active(self) -> bool:
        return self.activation >= SOFT_EDGE_FLOOR

    def to_dict(self) -> Dict:
        return {
            "source": self.source,
            "target": self.target,
            "resting_score": round(self.resting_score, 4),
            "activation": round(self.activation, 4),
            "conductance": round(self.conductance, 4),
            "hub": self.hub,
            "shard": self.shard,
            "coherence": round(self.coherence, 4),
            "step": self.step,
            "decay_rate": self.decay_rate,
            "is_active": self.is_active,
        }


@dataclass
class CAIRRNRun:
    """Record of one CAIRRN pipeline pass."""
    hub: str
    metric: float
    modulated: float
    shard: int
    coherence: float
    coherent: bool
    rerouted_to_home: bool

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class SporeResult:
    """Result of a mycelial_spore injection."""
    query: str
    hub: str
    colonization_points: List[Dict]         # top notes from samba_route_query
    activated_edges: List[Dict]             # HyphalEdge dicts that were lit
    anastomoses: List[Dict]                 # latent links surfaced
    cairrn_run: Dict

    def to_dict(self) -> Dict:
        return {
            "query": self.query,
            "hub": self.hub,
            "colonization_points": self.colonization_points,
            "activated_edges": self.activated_edges,
            "anastomoses": self.anastomoses,
            "cairrn_run": self.cairrn_run,
        }


# ──────────────────────────────────────────────────────────────────────────────
# CAIRRN pipeline (local implementation — mirrors SKILL spec exactly)
# ──────────────────────────────────────────────────────────────────────────────

class CAIRRNPipeline:
    """
    Three-layer CAIRRN modulation pipeline.

    Layer 1  Ana-Chi modulation   metric × gravity × (decay if rattling)
    Layer 2  neg_exp sharding     shard = floor(e^χ × 8 / 14.44) clamped [0,7]
    Layer 3  coherence enforce    exp(−steps / τ); < 0.50 → HOME re-route
    """

    def __init__(self) -> None:
        self._global_step: int = 0

    def tick(self) -> None:
        self._global_step += 1

    @property
    def step(self) -> int:
        return self._global_step

    def set_step(self, step: int) -> None:
        self._global_step = step

    def run(self, hub_name: str, metric: float) -> CAIRRNRun:
        hub = CAIRRN_HUBS.get(hub_name)
        if hub is None:
            raise ValueError(f"Unknown CAIRRN hub '{hub_name}'. Valid: {list(CAIRRN_HUBS)}")

        # Layer 1 — Ana-Chi basin modulation
        modulated = metric * hub["gravity"]
        if hub["rattling"]:
            modulated *= hub["decay"]

        # Layer 2 — neg_exp sharding  f(χ) = floor(e^χ × 8 / 14.44) clamped [0,7]
        raw_shard = math.exp(hub["chi"]) * 8.0 / 14.44
        shard = int(min(7, max(0, math.floor(raw_shard))))

        # Layer 3 — coherence enforcement
        coherence = math.exp(-self._global_step / CAIRRN_COHERENCE_TAU)
        coherent = coherence >= CAIRRN_COHERENCE_THRESHOLD
        rerouted = False

        if not coherent:
            # Re-route to HOME — run Layer 1 again with HOME params
            home = CAIRRN_HUBS["HOME"]
            modulated = metric * home["gravity"]
            shard = int(min(7, max(0, math.floor(math.exp(home["chi"]) * 8.0 / 14.44))))
            hub_name = "HOME"
            rerouted = True
            logger.warning(f"Coherence {coherence:.3f} < {CAIRRN_COHERENCE_THRESHOLD} — re-routed to HOME")

        self._global_step += 1

        return CAIRRNRun(
            hub=hub_name,
            metric=metric,
            modulated=modulated,
            shard=shard,
            coherence=coherence,
            coherent=coherent,
            rerouted_to_home=rerouted,
        )


# ──────────────────────────────────────────────────────────────────────────────
# MycelialNetwork
# ──────────────────────────────────────────────────────────────────────────────

class MycelialNetwork:
    """
    CAIRRN-aware mycelial activation layer over the Obsidian knowledge graph.

    The network maintains a live activation map of soft edges (hyphae) between
    notes. Edges are not binary — they have a resting conductance derived from
    Samba GNN semantic scores, and are dynamically activated by routing concept
    queries (spores) through the CAIRRN three-layer pipeline.

    Persistent state lives in `state_path` (JSON) so hyphal activation survives
    across sessions. Each tick, edges decay by their hub's memory_decay factor.

    Usage:
        net = MycelialNetwork(orchestrator)
        result = net.spore("mycelial intelligence", hub="HOME")
        edges  = net.trace_hyphae("Rationale: Mycelial Intelligence in DAWN")
        links  = net.surface_anastomoses("CAIRRN")
        net.decay_all()   # advance one dormancy tick (C-layer)
    """

    STATE_FILENAME = "mycelial_state.json"

    def __init__(
        self,
        orchestrator,
        state_dir: Optional[str] = None,
        top_k_colonize: int = 8,
        top_k_hyphae: int = 10,
        top_k_anastomoses: int = 5,
        activation_floor: float = SOFT_EDGE_FLOOR,
    ) -> None:
        self.orch = orchestrator
        self.top_k_colonize  = top_k_colonize
        self.top_k_hyphae    = top_k_hyphae
        self.top_k_anastomoses = top_k_anastomoses
        self.activation_floor  = activation_floor

        # Resolve state path
        if state_dir is None:
            state_dir = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), "engine", "state"
            )
        os.makedirs(state_dir, exist_ok=True)
        self.state_path = os.path.join(state_dir, self.STATE_FILENAME)

        self.pipeline = CAIRRNPipeline()
        self._edges: Dict[Tuple[str, str], HyphalEdge] = {}
        self._load_state()

    # ──────────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────────

    def spore(
        self,
        query: str,
        hub: str = "HOME",
        threshold: Optional[float] = None,
    ) -> SporeResult:
        """
        Inject a concept spore into the mycelial network.

        1. Route query through Samba → colonization points (entry notes)
        2. Trace local hyphae from each colonization point
        3. Take top Samba score as CAIRRN metric, run full pipeline
        4. Activate edges above threshold with modulated strength
        5. Surface anastomoses (latent links) from the hottest colonization point

        Args:
            query:     Free-text concept to inject (the spore)
            hub:       CAIRRN hub to route through (default HOME)
            threshold: Activation floor override (default SOFT_EDGE_FLOOR)

        Returns:
            SporeResult with colonization points, activated edges, anastomoses
        """
        threshold = threshold if threshold is not None else self.activation_floor

        if hub not in CAIRRN_HUBS:
            raise ValueError(f"Unknown hub '{hub}'. Valid: {list(CAIRRN_HUBS)}")

        # Step 1 — colonize: find entry notes for the query
        colonization_points = self.orch.route_query(query, top_k=self.top_k_colonize)
        if not colonization_points:
            return SporeResult(
                query=query, hub=hub,
                colonization_points=[], activated_edges=[],
                anastomoses=[], cairrn_run={},
            )

        # Step 2 — CAIRRN pipeline: metric = top Samba similarity score
        top_score = colonization_points[0]["score"]
        run = self.pipeline.run(hub, metric=top_score)

        # Step 3 — trace hyphae and activate
        activated = []
        for cp in colonization_points:
            note_title = cp["title"]
            related = self.orch.find_related(note_title, top_k=self.top_k_hyphae)
            for rel in related:
                key = (note_title, rel["title"])
                resting = rel["score"]

                # Edge activation = CAIRRN modulated value × resting conductance
                edge_activation = run.modulated * (1.0 / (1.0 + math.exp(-CAIRRN_KAPPA * resting * 20)))
                edge_activation = min(1.0, edge_activation)   # clamp to [0,1]

                edge = HyphalEdge(
                    source=note_title,
                    target=rel["title"],
                    resting_score=resting,
                    activation=edge_activation,
                    hub=run.hub,
                    shard=run.shard,
                    coherence=run.coherence,
                    step=self.pipeline.step,
                    decay_rate=CAIRRN_HUBS[run.hub]["decay"],
                )
                self._edges[key] = edge
                if edge.is_active:
                    activated.append(edge.to_dict())

        # Step 4 — anastomoses from hottest colonization point
        anastomoses = []
        if colonization_points:
            try:
                raw = self.orch.suggest_links(
                    colonization_points[0]["title"],
                    top_k=self.top_k_anastomoses,
                )
                # Only surface anastomoses whose latent score exceeds the hub-modulated floor
                for s in raw:
                    s["anastomosis_strength"] = round(run.modulated * s["score"], 4)
                anastomoses = [s for s in raw if s["anastomosis_strength"] >= threshold]
            except Exception as e:
                logger.warning(f"anastomosis surface failed: {e}")

        self._save_state()

        result = SporeResult(
            query=query,
            hub=hub,
            colonization_points=colonization_points,
            activated_edges=activated,
            anastomoses=anastomoses,
            cairrn_run=run.to_dict(),
        )

        # Permanent vault record — append to activations log and refresh state snapshot
        self._append_event_log(self._fmt_spore_log(query, hub, result))
        self._write_state_snapshot()

        return result

    def trace_hyphae(
        self,
        note_title: str,
        threshold: Optional[float] = None,
    ) -> List[Dict]:
        """
        Trace all currently activated soft edges involving a given note.

        Returns edges where activation >= threshold, sorted by activation strength.
        Includes both outgoing (source) and incoming (target) hyphae.

        Args:
            note_title:  Note to trace from (exact title)
            threshold:   Activation floor (default SOFT_EDGE_FLOOR)

        Returns:
            List of HyphalEdge dicts sorted by activation descending
        """
        threshold = threshold if threshold is not None else self.activation_floor
        title_lower = note_title.lower()

        results = []
        for (src, tgt), edge in self._edges.items():
            if src.lower() == title_lower or tgt.lower() == title_lower:
                if edge.activation >= threshold:
                    results.append(edge.to_dict())

        results.sort(key=lambda e: -e["activation"])
        return results

    def surface_anastomoses(
        self,
        note_title: str,
        hub: str = "HOME",
        threshold: Optional[float] = None,
    ) -> List[Dict]:
        """
        Surface latent anastomoses — hyphae that could become explicit wiki-links.

        Runs samba_suggest_links to find semantically close, unlinked notes, then
        filters by activation potential (hub-modulated Samba score ≥ threshold).

        Args:
            note_title:  Note to surface anastomoses for
            hub:         CAIRRN hub to apply for modulation estimate
            threshold:   Minimum anastomosis_strength to include

        Returns:
            List of suggestion dicts with anastomosis_strength field
        """
        threshold = threshold if threshold is not None else self.activation_floor
        hub_cfg = CAIRRN_HUBS.get(hub, CAIRRN_HUBS["HOME"])

        try:
            raw = self.orch.suggest_links(note_title, top_k=self.top_k_anastomoses * 2)
        except Exception as e:
            logger.warning(f"suggest_links failed for '{note_title}': {e}")
            return []

        results = []
        for s in raw:
            # Estimate what CAIRRN would return for this score through this hub
            modulated = s["score"] * hub_cfg["gravity"]
            if hub_cfg["rattling"]:
                modulated *= hub_cfg["decay"]
            strength = modulated * (1.0 / (1.0 + math.exp(-CAIRRN_KAPPA * s["score"] * 20)))
            s["anastomosis_strength"] = round(min(1.0, strength), 4)
            if s["anastomosis_strength"] >= threshold:
                results.append(s)

        results.sort(key=lambda s: -s["anastomosis_strength"])
        return results[:self.top_k_anastomoses]

    def propagate(self, steps: int = 3) -> Dict:
        """
        Passive diffusion — spread activation N steps through the edge graph.

        Implements the passive flow formula from the mycelial rationale:
            F_passive_ij = g_ij × (activation_i − activation_j)

        Each step, each active edge donates a fraction of its activation surplus
        to adjacent edges (sharing the same source or target note).

        Args:
            steps:  Number of diffusion ticks

        Returns:
            Dict with before/after activation summary
        """
        before_active = sum(1 for e in self._edges.values() if e.is_active)

        for _ in range(steps):
            self._diffuse_step()

        after_active = sum(1 for e in self._edges.values() if e.is_active)
        self._save_state()

        return {
            "steps": steps,
            "edges_before_active": before_active,
            "edges_after_active": after_active,
            "total_edges": len(self._edges),
            "newly_activated": max(0, after_active - before_active),
            "went_dormant": max(0, before_active - after_active),
        }

    def decay_all(self) -> Dict:
        """
        C-layer: apply one dormancy tick to all edges.

        Each edge's activation decays by its hub's memory_decay factor:
            activation_t+1 = activation_t × decay_rate

        Edges that fall below SOFT_EDGE_FLOOR go dormant (but are not deleted —
        a future spore can reactivate them, just as dormant mycelia revive).

        Returns:
            Summary of decay applied across the network
        """
        went_dormant = 0
        for edge in self._edges.values():
            was_active = edge.is_active
            edge.activation *= edge.decay_rate
            if was_active and not edge.is_active:
                went_dormant += 1

        active_count = sum(1 for e in self._edges.values() if e.is_active)
        self._save_state()

        result = {
            "total_edges": len(self._edges),
            "active_after_decay": active_count,
            "went_dormant": went_dormant,
            "pipeline_step": self.pipeline.step,
        }

        self._append_event_log(self._fmt_decay_log(result))
        self._write_state_snapshot()

        return result

    def activation_map(self, active_only: bool = True) -> List[Dict]:
        """
        Return the full current activation map, sorted by activation strength.

        Args:
            active_only:  If True, only include edges above threshold

        Returns:
            List of HyphalEdge dicts
        """
        edges = list(self._edges.values())
        if active_only:
            edges = [e for e in edges if e.is_active]
        edges.sort(key=lambda e: -e.activation)
        return [e.to_dict() for e in edges]

    def network_stats(self) -> Dict:
        """Summarise the current hyphal network state."""
        active = [e for e in self._edges.values() if e.is_active]
        dormant = [e for e in self._edges.values() if not e.is_active]

        hub_counts: Dict[str, int] = {}
        for e in active:
            hub_counts[e.hub] = hub_counts.get(e.hub, 0) + 1

        return {
            "total_hyphae": len(self._edges),
            "active_hyphae": len(active),
            "dormant_hyphae": len(dormant),
            "mean_activation": (
                round(sum(e.activation for e in active) / len(active), 4)
                if active else 0.0
            ),
            "hub_activation_counts": hub_counts,
            "pipeline_step": self.pipeline.step,
            "coherence_now": round(
                math.exp(-self.pipeline.step / CAIRRN_COHERENCE_TAU), 4
            ),
        }

    def apply_anastomoses(
        self,
        note_title: str,
        write_threshold: float = 0.60,
        hub: str = "HOME",
        dry_run: bool = True,
    ) -> Dict:
        """
        Write hot anastomoses for one note into the vault as wiki-links.

        Surfaces latent connections above `write_threshold` via
        `surface_anastomoses()` and calls `VaultWriter.append_links()` to
        write them. Uses dry_run=True by default — set False to actually
        modify the vault file.

        Args:
            note_title:      Source note to grow links from.
            write_threshold: Minimum anastomosis_strength to write (default 0.60).
            hub:             CAIRRN hub for modulation estimate (default HOME).
            dry_run:         If True, report without writing (default True).

        Returns:
            Dict with note, suggestions, links_written, dry_run flag.
        """
        from engine.vault_writer import VaultWriter

        candidates = self.surface_anastomoses(
            note_title=note_title,
            hub=hub,
            threshold=write_threshold,
        )
        if not candidates:
            return {"note": note_title, "suggestions": [], "links_written": 0, "dry_run": dry_run}

        # Resolve vault path for the source note
        note_path: Optional[str] = None
        for n in self.orch.graph.notes.values():
            if n.title.lower() == note_title.lower():
                note_path = n.path
                break

        if note_path is None:
            logger.warning("apply_anastomoses: note '%s' not found in graph", note_title)
            return {
                "note": note_title,
                "error": "note not found in graph",
                "suggestions": candidates,
                "links_written": 0,
                "dry_run": dry_run,
            }

        writer = VaultWriter(dry_run=dry_run)
        links_written = writer.append_links(note_path, candidates)

        result = {
            "note": note_title,
            "path": note_path,
            "suggestions": candidates,
            "links_written": links_written,
            "dry_run": dry_run,
        }

        self._append_event_log(
            self._fmt_growth_log(note_title, links_written, dry_run, candidates)
        )

        return result

    def apply_all_anastomoses(
        self,
        write_threshold: float = 0.60,
        hub: str = "HOME",
        dry_run: bool = True,
        top_n_notes: int = 5,
    ) -> Dict:
        """
        Apply anastomoses for the top-N most active source notes in the network.

        Identifies the unique source notes with the highest mean edge activation,
        then calls `apply_anastomoses()` for each. Designed for daemon use — runs
        on the same pulse as decay so growth and dormancy fire together.

        Args:
            write_threshold: Minimum anastomosis_strength to write (default 0.60).
            hub:             CAIRRN hub for modulation (default HOME).
            dry_run:         If True, report without writing (default True).
            top_n_notes:     How many source notes to process (default 5).

        Returns:
            Dict with per-note results and aggregate totals.
        """
        # Rank source notes by mean activation of their outgoing edges
        source_scores: Dict[str, list] = {}
        for edge in self._edges.values():
            if edge.is_active:
                source_scores.setdefault(edge.source, []).append(edge.activation)

        ranked = sorted(
            source_scores.items(),
            key=lambda kv: -sum(kv[1]) / len(kv[1]),
        )[:top_n_notes]

        results = []
        total_written = 0
        for source_title, _ in ranked:
            r = self.apply_anastomoses(
                note_title=source_title,
                write_threshold=write_threshold,
                hub=hub,
                dry_run=dry_run,
            )
            results.append(r)
            total_written += r.get("links_written", 0)

        return {
            "notes_checked": len(ranked),
            "total_links_written": total_written,
            "dry_run": dry_run,
            "per_note": results,
        }

    # ──────────────────────────────────────────────────────────────────────────
    # Internal diffusion
    # ──────────────────────────────────────────────────────────────────────────

    def _diffuse_step(self) -> None:
        """One passive diffusion tick — activation equalises along conductance-weighted edges."""
        # Build adjacency: note → list of connected edges
        adjacency: Dict[str, List[HyphalEdge]] = {}
        for edge in self._edges.values():
            adjacency.setdefault(edge.source, []).append(edge)
            adjacency.setdefault(edge.target, []).append(edge)

        # Compute deltas without in-place mutation during iteration
        deltas: Dict[Tuple[str, str], float] = {}
        for (src, tgt), edge in self._edges.items():
            src_activation = edge.activation
            # Average activation of edges that share this edge's target
            peers = [e for e in adjacency.get(tgt, []) if (e.source, e.target) != (src, tgt)]
            if not peers:
                continue
            mean_peer = sum(e.activation for e in peers) / len(peers)
            flow = edge.conductance * (src_activation - mean_peer)
            deltas[(src, tgt)] = deltas.get((src, tgt), 0.0) - flow * 0.1   # damp factor

        for key, delta in deltas.items():
            if key in self._edges:
                self._edges[key].activation = max(0.0, min(1.0, self._edges[key].activation + delta))

    # ──────────────────────────────────────────────────────────────────────────
    # Vault visibility — permanent .txt event log and state snapshot
    # ──────────────────────────────────────────────────────────────────────────

    def _vault_log_dir(self) -> Optional[str]:
        """Return the agent-log/ directory inside the vault, creating it if needed."""
        try:
            from engine.vault_writer import _load_vault_path
            vault_root = _load_vault_path()
            log_dir = vault_root / "agent-log"
            log_dir.mkdir(parents=True, exist_ok=True)
            return str(log_dir)
        except Exception as e:
            logger.warning("Could not resolve vault log dir: %s", e)
            return None

    def _append_event_log(self, event_text: str) -> None:
        """
        Append a timestamped event block to agent-log/mycelial-activations.txt.

        This file is the permanent, vault-visible record of all mycelial activity.
        It is plain text so it remains readable without any tooling, and lives
        inside the vault so Samba's crawler indexes it as a graph node.
        """
        log_dir = self._vault_log_dir()
        if log_dir is None:
            return
        log_path = os.path.join(log_dir, "mycelial-activations.txt")
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(event_text)
                f.flush()
        except Exception as e:
            logger.warning("Failed to write mycelial event log: %s", e)

    def _write_state_snapshot(self) -> None:
        """
        Overwrite agent-log/mycelial-state.txt with the current network state.

        This is the live snapshot — always reflects the most recent activation
        map. Unlike the event log it is not append-only: it is rewritten on
        every significant network change so it shows the present, not history.
        """
        log_dir = self._vault_log_dir()
        if log_dir is None:
            return

        ts = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())
        active = [e for e in self._edges.values() if e.is_active]
        dormant_count = len(self._edges) - len(active)
        mean_act = (sum(e.activation for e in active) / len(active)) if active else 0.0
        coherence = math.exp(-self.pipeline.step / CAIRRN_COHERENCE_TAU)

        lines = [
            "MYCELIAL NETWORK STATE",
            f"updated: {ts}",
            f"pipeline_step={self.pipeline.step}  coherence={coherence:.4f}",
            f"total_hyphae={len(self._edges)}  active={len(active)}"
            f"  dormant={dormant_count}  mean_activation={mean_act:.4f}",
            "",
        ]

        if active:
            lines.append("ACTIVE HYPHAE  (sorted by activation strength)")
            lines.append("─" * 72)
            for e in sorted(active, key=lambda x: -x.activation):
                src_short = e.source[:36]
                tgt_short = e.target[:36]
                lines.append(
                    f"  {e.activation:.4f}  [{e.hub:<13}  shard={e.shard}]"
                    f"  {src_short} → {tgt_short}"
                )
        else:
            lines.append("(no active hyphae)")

        lines.append("")

        snapshot_path = os.path.join(log_dir, "mycelial-state.txt")
        tmp = snapshot_path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            os.replace(tmp, snapshot_path)
        except Exception as e:
            logger.warning("Failed to write mycelial state snapshot: %s", e)

    def _fmt_spore_log(self, query: str, hub: str, result: "SporeResult") -> str:
        """Format a SPORE event block for the activations log."""
        ts = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())
        run = result.cairrn_run
        sep = "═" * 64

        lines = [
            "",
            sep,
            f"SPORE  {ts}  hub={hub}  step={run.get('metric','')}",
            f"query: \"{query}\"",
            f"cairrn: modulated={run.get('modulated',0):.4f}"
            f"  shard={run.get('shard',0)}"
            f"  coherence={run.get('coherence',0):.4f}"
            f"  [{'COHERENT' if run.get('coherent') else 'REROUTED→HOME'}]",
        ]

        if result.colonization_points:
            lines.append(f"colonised ({len(result.colonization_points)}):")
            for cp in result.colonization_points[:5]:
                lines.append(f"  {cp['score']:.4f}  {cp['title'][:60]}")

        if result.activated_edges:
            lines.append(f"activated edges ({len(result.activated_edges)}):")
            for e in result.activated_edges[:8]:
                lines.append(
                    f"  {e['activation']:.4f}  [LIT]"
                    f"  {e['source'][:30]} → {e['target'][:30]}"
                )

        if result.anastomoses:
            lines.append(f"anastomoses surfaced ({len(result.anastomoses)}):")
            for a in result.anastomoses:
                lines.append(f"  {a['anastomosis_strength']:.4f}  → [[{a['title'][:50]}]]")

        lines.append(sep)
        lines.append("")
        return "\n".join(lines)

    def _fmt_decay_log(self, result: Dict) -> str:
        """Format a DECAY event block for the activations log."""
        ts = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())
        return (
            f"\nDECAY  {ts}  step={result.get('pipeline_step',0)}"
            f"  active={result.get('active_after_decay',0)}"
            f"  went_dormant={result.get('went_dormant',0)}\n"
        )

    def _fmt_growth_log(self, note: str, links_written: int, dry_run: bool, suggestions: list) -> str:
        """Format a GROWTH event block for the activations log."""
        ts = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())
        tag = "[dry-run]" if dry_run else "[WRITTEN]"
        lines = [f"\nGROWTH  {ts}  {tag}  note={note[:50]}  links={links_written}"]
        for s in suggestions[:5]:
            lines.append(f"  → [[{s['title'][:50]}]]  strength={s.get('anastomosis_strength',0):.4f}")
        lines.append("")
        return "\n".join(lines)

    # ──────────────────────────────────────────────────────────────────────────
    # State persistence
    # ──────────────────────────────────────────────────────────────────────────

    def _save_state(self) -> None:
        state = {
            "schema_version": 1,
            "pipeline_step": self.pipeline.step,
            "saved_at": time.time(),
            "edges": {
                f"{src}|||{tgt}": edge.to_dict()
                for (src, tgt), edge in self._edges.items()
            },
        }
        tmp = self.state_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
        os.replace(tmp, self.state_path)

    def _load_state(self) -> None:
        if not os.path.exists(self.state_path):
            logger.info("No mycelial state found — starting fresh network")
            return
        try:
            with open(self.state_path, encoding="utf-8") as f:
                state = json.load(f)

            self.pipeline.set_step(state.get("pipeline_step", 0))

            for key_str, d in state.get("edges", {}).items():
                parts = key_str.split("|||", 1)
                if len(parts) != 2:
                    continue
                src, tgt = parts
                self._edges[(src, tgt)] = HyphalEdge(
                    source=d["source"],
                    target=d["target"],
                    resting_score=d["resting_score"],
                    activation=d["activation"],
                    hub=d["hub"],
                    shard=d["shard"],
                    coherence=d["coherence"],
                    step=d["step"],
                    decay_rate=d["decay_rate"],
                )
            logger.info(f"Loaded mycelial state: {len(self._edges)} edges, step={self.pipeline.step}")
        except Exception as e:
            logger.warning(f"Failed to load mycelial state: {e} — starting fresh")
            self._edges = {}

# Related: OctopusTracer, ResurfaceArm, TopologicalGraph.semantic_simplex_complex,
#          SambaOrchestrator.topology_summary, SproutArm
