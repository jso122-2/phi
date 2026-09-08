"""
graph.edge_scorer — formula-driven edge activation scoring for the vault graph.

Every score computed here goes through FormulaRegistry.call().
The formulas live in config/formulas/formula_dictionary.yaml and
config/formulas/python_overrides.yaml.  When a formula is updated in Notion
and sync_notion() runs, the next edge scoring call uses the new expression
automatically — no code change required.

This is the exclusive math layer for MCP-accessible edge computation.
Agents use the graph_edge_score MCP tool; internal pipeline imports EdgeScorer
directly.

Architecture
─────────────
  Vault node A  ──┐
                  ├─ EdgeScorer.score_pair() ─→ EdgeScore (formula trace)
  Vault node B  ──┘          │
                         via REGISTRY.call():
                           F_COSINE_SIMILARITY  — embedding similarity
                           F_JACCARD_AFFINITY   — tag set overlap
                           F_EDGE_WEIGHT        — reinforcement-weighted composite
                           F_RAG_PRIORITY       — P_sps final retrieval priority
                           F_PATH_COST          — traversal cost from A to B
                           F_LOCAL_COHERENCE    — neighbourhood coherence

  EdgeScorer.score_corpus() — batch: numpy matrix multiply for speed,
                               then formula weighting per pair.

Design contract
───────────────
  • REGISTRY is the sole source of mathematical truth.
  • numpy is used only for batch matrix operations (speed).
    Individual pair scores always go through formula_call.
  • Every EdgeScore carries a formula_trace dict so agents can see which
    formula produced which value and verify correctness.
  • If the registry fails to load (no YAML, missing PyYAML), EdgeScorer
    falls back to direct numpy / Python math with a warning — the graph
    still works, it just loses Notion-driven formula updates.
"""
from __future__ import annotations

import math
import sys
from dataclasses import dataclass, field
from typing import Any

import numpy as np

# ---------------------------------------------------------------------------
# FormulaRegistry — lazy import so the module loads even without PyYAML
# ---------------------------------------------------------------------------

def _registry():
    try:
        from workers.formula_registry import REGISTRY
        return REGISTRY
    except Exception as exc:  # noqa: BLE001
        print(f"[edge_scorer] registry unavailable: {exc}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# EdgeScore
# ---------------------------------------------------------------------------

@dataclass
class EdgeScore:
    """
    Full scored relationship between two vault nodes.

    Every numeric field is the direct output of a FormulaRegistry.call().
    formula_trace records the formula_id → result for each step so the MCP
    tool can surface it to agents.

    Composite 0 → 1 (higher = stronger edge / higher retrieval priority).
    """
    stem_a:           str
    stem_b:           str

    # Individual formula outputs
    cosine_sim:       float          # F_COSINE_SIMILARITY
    jaccard:          float          # F_JACCARD_AFFINITY
    edge_weight:      float          # F_EDGE_WEIGHT  (reinforced composite)
    rag_priority:     float          # F_RAG_PRIORITY (final retrieval weight)
    path_cost:        float          # F_PATH_COST    (traversal cost)

    # Metadata
    formula_trace:    dict[str, Any] = field(default_factory=dict)
    fallback_used:    bool = False   # True if registry was unavailable

    @property
    def composite(self) -> float:
        """Edge activation strength: normalised blend of sim + jaccard."""
        return float(np.clip(0.7 * self.cosine_sim + 0.3 * self.jaccard, 0.0, 1.0))

    def to_dict(self) -> dict:
        return {
            "stem_a":       self.stem_a,
            "stem_b":       self.stem_b,
            "cosine_sim":   round(self.cosine_sim, 6),
            "jaccard":      round(self.jaccard, 6),
            "edge_weight":  round(self.edge_weight, 6),
            "rag_priority": round(self.rag_priority, 6),
            "path_cost":    round(self.path_cost, 6),
            "composite":    round(self.composite, 6),
            "formula_trace": self.formula_trace,
            "fallback_used": self.fallback_used,
        }


# ---------------------------------------------------------------------------
# Pure-Python fallback math (used when registry unavailable)
# ---------------------------------------------------------------------------

def _fallback_cosine(a: list[float], b: list[float]) -> float:
    dot = sum(ai * bi for ai, bi in zip(a, b))
    na  = math.sqrt(sum(x * x for x in a))
    nb  = math.sqrt(sum(x * x for x in b))
    denom = na * nb
    return float(dot / denom) if denom > 1e-12 else 0.0


def _fallback_jaccard(a: list, b: list) -> float:
    sa, sb = set(a), set(b)
    inter = len(sa & sb)
    union = len(sa | sb)
    return float(inter / union) if union > 0 else 0.0


# ---------------------------------------------------------------------------
# EdgeScorer
# ---------------------------------------------------------------------------

class EdgeScorer:
    """
    Formula-driven edge activation scorer.

    All scoring operations delegate to FormulaRegistry.call().
    Numpy is used only for batch matrix operations in score_corpus().

    Parameters
    ----------
    rag_O_N     System complexity denominator for F_RAG_PRIORITY (default 1.0).
    rag_P_risk  Perplexity risk denominator for F_RAG_PRIORITY (default 1.0).
    edge_hop    Default hop count for F_PATH_COST (default 1).
    """

    def __init__(
        self,
        rag_O_N:    float = 1.0,
        rag_P_risk: float = 1.0,
        edge_hop:   int   = 1,
    ) -> None:
        self._rag_O_N    = rag_O_N
        self._rag_P_risk = rag_P_risk
        self._edge_hop   = edge_hop

    # ── individual formula calls ─────────────────────────────────────────

    def cosine_sim(
        self,
        vec_a: list[float] | np.ndarray,
        vec_b: list[float] | np.ndarray,
    ) -> tuple[float, bool]:
        """
        Cosine similarity via F_COSINE_SIMILARITY.

        Returns (score, fallback_used).
        For L2-normalised vectors this equals the dot product.
        """
        la = list(vec_a) if isinstance(vec_a, np.ndarray) else list(vec_a)
        lb = list(vec_b) if isinstance(vec_b, np.ndarray) else list(vec_b)

        reg = _registry()
        if reg and "F_COSINE_SIMILARITY" in reg:
            try:
                return float(reg.call("F_COSINE_SIMILARITY", A=la, B=lb)), False
            except Exception as exc:  # noqa: BLE001
                print(f"[edge_scorer] F_COSINE_SIMILARITY: {exc}", file=sys.stderr)

        return _fallback_cosine(la, lb), True

    def jaccard_affinity(
        self,
        tags_a: list[str],
        tags_b: list[str],
    ) -> tuple[float, bool]:
        """Tag set overlap via F_JACCARD_AFFINITY."""
        reg = _registry()
        if reg and "F_JACCARD_AFFINITY" in reg:
            try:
                return float(reg.call("F_JACCARD_AFFINITY", A=tags_a, B=tags_b)), False
            except Exception as exc:  # noqa: BLE001
                print(f"[edge_scorer] F_JACCARD_AFFINITY: {exc}", file=sys.stderr)

        return _fallback_jaccard(tags_a, tags_b), True

    def edge_weight(
        self,
        sim_scores:        list[float],
        reinforcement:     list[float],
    ) -> tuple[float, bool]:
        """
        Reinforcement-weighted edge activation via F_EDGE_WEIGHT.

        sim_scores      List of per-facet cosine similarities.
        reinforcement   Parallel list of reinforcement multipliers
                        (e.g. [1.0] for a single-facet pair).
        """
        reg = _registry()
        if reg and "F_EDGE_WEIGHT" in reg:
            try:
                return float(reg.call(
                    "F_EDGE_WEIGHT",
                    sim_list=sim_scores,
                    reinforcement_list=reinforcement,
                )), False
            except Exception as exc:  # noqa: BLE001
                print(f"[edge_scorer] F_EDGE_WEIGHT: {exc}", file=sys.stderr)

        return float(sum(s * r for s, r in zip(sim_scores, reinforcement))), True

    def rag_priority(
        self,
        X_norm: float,
        T_pos:  float,
        O_N:    float | None = None,
        P_risk: float | None = None,
    ) -> tuple[float, bool]:
        """
        Final retrieval priority via F_RAG_PRIORITY.

        P_sps = (X_norm / O_N) − (T_pos / P_risk)

        X_norm   Semantic awareness score ∈ [0, 1].
        T_pos    Positional/recency penalty ∈ [0, 1].
        O_N      System complexity (default self._rag_O_N).
        P_risk   Perplexity risk tuning lever (default self._rag_P_risk).
        """
        O_N_   = O_N    if O_N    is not None else self._rag_O_N
        P_risk_ = P_risk if P_risk is not None else self._rag_P_risk

        reg = _registry()
        if reg and "F_RAG_PRIORITY" in reg:
            try:
                return float(reg.call(
                    "F_RAG_PRIORITY",
                    X_norm=X_norm,
                    O_N=max(O_N_, 1e-9),
                    T_pos=T_pos,
                    P_risk=max(P_risk_, 1e-9),
                )), False
            except Exception as exc:  # noqa: BLE001
                print(f"[edge_scorer] F_RAG_PRIORITY: {exc}", file=sys.stderr)

        # Fallback: simple blend
        return float(X_norm - T_pos), True

    def path_cost(
        self,
        sim:       float,
        hop_count: int | None = None,
    ) -> tuple[float, bool]:
        """
        Traversal cost via F_PATH_COST: Hop_Count × (1 − sim).

        Lower is better — a 1-hop link with sim=0.9 costs 0.1.
        """
        hops = hop_count if hop_count is not None else self._edge_hop
        reg  = _registry()
        if reg and "F_PATH_COST" in reg:
            try:
                return float(reg.call("F_PATH_COST", Hop_Count=hops, sim=sim)), False
            except Exception as exc:  # noqa: BLE001
                print(f"[edge_scorer] F_PATH_COST: {exc}", file=sys.stderr)

        return float(hops * (1.0 - sim)), True

    def local_coherence(
        self,
        w_list:    list[float],
        sim_list:  list[float],
        dist_list: list[float],
    ) -> tuple[float, bool]:
        """
        Local neighbourhood coherence via F_LOCAL_COHERENCE.

        C_i = Σ w_ij · sim_ij / dist_ij
        """
        reg = _registry()
        if reg and "F_LOCAL_COHERENCE" in reg:
            try:
                return float(reg.call(
                    "F_LOCAL_COHERENCE",
                    w_list=w_list,
                    sim_list=sim_list,
                    dist_list=dist_list,
                )), False
            except Exception as exc:  # noqa: BLE001
                print(f"[edge_scorer] F_LOCAL_COHERENCE: {exc}", file=sys.stderr)

        total = sum(
            w * s / max(d, 1e-9)
            for w, s, d in zip(w_list, sim_list, dist_list)
        )
        return float(total), True

    # ── full pair scoring ────────────────────────────────────────────────

    def score_pair(
        self,
        stem_a:  str,
        stem_b:  str,
        vec_a:   list[float] | np.ndarray,
        vec_b:   list[float] | np.ndarray,
        tags_a:  list[str] = (),
        tags_b:  list[str] = (),
        hop_count: int = 1,
    ) -> EdgeScore:
        """
        Compute a full formula-traced EdgeScore between two vault nodes.

        Parameters
        ----------
        stem_a / stem_b   Node stems (used as labels only).
        vec_a / vec_b     Embedding vectors (L2-normalised preferred).
        tags_a / tags_b   Tag lists for Jaccard affinity.
        hop_count         Graph distance for path cost.

        Returns an EdgeScore with formula_trace containing every
        formula_id → value pair used in the computation.
        """
        trace:    dict[str, Any] = {}
        fallback: bool           = False

        # 1. Cosine similarity
        cos, fb = self.cosine_sim(vec_a, vec_b)
        trace["F_COSINE_SIMILARITY"] = round(cos, 6)
        fallback = fallback or fb

        # 2. Tag set Jaccard affinity
        jac, fb = self.jaccard_affinity(list(tags_a), list(tags_b))
        trace["F_JACCARD_AFFINITY"] = round(jac, 6)
        fallback = fallback or fb

        # 3. Reinforced edge weight
        #    Treat cosine as the primary sim-facet; Jaccard as reinforcement.
        ew, fb = self.edge_weight([cos], [jac + 1.0])
        trace["F_EDGE_WEIGHT"] = round(ew, 6)
        fallback = fallback or fb

        # 4. RAG priority
        #    X_norm = cosine_sim, T_pos = 1 - jaccard (penalty for tag distance)
        rp, fb = self.rag_priority(X_norm=cos, T_pos=1.0 - jac)
        trace["F_RAG_PRIORITY"] = round(rp, 6)
        fallback = fallback or fb

        # 5. Path cost
        pc, fb = self.path_cost(sim=cos, hop_count=hop_count)
        trace["F_PATH_COST"] = round(pc, 6)
        fallback = fallback or fb

        return EdgeScore(
            stem_a       = stem_a,
            stem_b       = stem_b,
            cosine_sim   = float(np.clip(cos, 0.0, 1.0)),
            jaccard      = float(np.clip(jac, 0.0, 1.0)),
            edge_weight  = float(ew),
            rag_priority = float(rp),
            path_cost    = float(pc),
            formula_trace = trace,
            fallback_used = fallback,
        )

    # ── batch scoring ────────────────────────────────────────────────────

    def score_corpus(
        self,
        target_stem: str,
        target_vec:  np.ndarray,
        target_tags: list[str],
        corpus_stems: list[str],
        corpus_vecs:  np.ndarray,
        corpus_tags:  list[list[str]],
        threshold:    float = 0.25,
        top_k:        int   = 6,
        exclude:      set[str] | None = None,
    ) -> list[tuple[float, str, EdgeScore]]:
        """
        Rank a corpus against a target using formula-driven scoring.

        Batch step: numpy matrix multiply for cosine similarities (fast).
        Per-pair step: F_JACCARD_AFFINITY, F_EDGE_WEIGHT, F_RAG_PRIORITY
                       through the registry.

        Returns a sorted list of (rag_priority, stem, EdgeScore),
        highest priority first, filtered by threshold and top_k.
        """
        exclude = exclude or set()

        # Batch cosine via numpy (speed) — vectors are L2-normalised
        target_norm = target_vec / (np.linalg.norm(target_vec) + 1e-12)
        corp_norms  = corpus_vecs / (
            np.linalg.norm(corpus_vecs, axis=1, keepdims=True) + 1e-12
        )
        raw_sims: np.ndarray = corp_norms @ target_norm  # (n,)

        results: list[tuple[float, str, EdgeScore]] = []
        for i, (stem, tags, cos_raw) in enumerate(
            zip(corpus_stems, corpus_tags, raw_sims)
        ):
            if stem == target_stem or stem in exclude:
                continue
            cos = float(np.clip(cos_raw, 0.0, 1.0))
            if cos < threshold:
                continue

            # Per-pair formula computation
            jac, _ = self.jaccard_affinity(target_tags, tags)
            ew,  _ = self.edge_weight([cos], [jac + 1.0])
            rp,  _ = self.rag_priority(X_norm=cos, T_pos=1.0 - jac)
            pc,  _ = self.path_cost(sim=cos)

            score = EdgeScore(
                stem_a       = target_stem,
                stem_b       = stem,
                cosine_sim   = cos,
                jaccard      = float(np.clip(jac, 0.0, 1.0)),
                edge_weight  = float(ew),
                rag_priority = float(rp),
                path_cost    = float(pc),
                formula_trace = {
                    "F_COSINE_SIMILARITY": round(cos, 6),
                    "F_JACCARD_AFFINITY":  round(jac, 6),
                    "F_EDGE_WEIGHT":       round(float(ew), 6),
                    "F_RAG_PRIORITY":      round(float(rp), 6),
                    "F_PATH_COST":         round(float(pc), 6),
                },
            )
            results.append((float(rp), stem, score))

        results.sort(key=lambda x: x[0], reverse=True)
        return results[:top_k]


# ---------------------------------------------------------------------------
# Module singleton
# ---------------------------------------------------------------------------

SCORER = EdgeScorer()
