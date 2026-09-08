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

Enforcement
───────────
  By default EdgeScorer runs in strict mode: if a required formula is not
  ready in the registry it raises workers.formula_registry.FormulaNotReady
  immediately rather than silently falling back to ad-hoc Python math.

  The fallback path is available only when strict=False is passed explicitly,
  which should never happen in production.  Tests that want to exercise the
  fallback must opt in.

  At module import, validate_edge_formulas() is called so import itself
  fails fast if the formula YAML is misconfigured — the graph pipeline cannot
  start in a degraded math state.

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
  • strict=True (default) raises FormulaNotReady when formulas are absent.
    strict=False falls back to direct Python math (test/debug only).
"""
from __future__ import annotations

import math
import sys
from dataclasses import dataclass, field
from typing import Any

import numpy as np


# ---------------------------------------------------------------------------
# Required formula IDs — these are the edge activation math, not decorations
# ---------------------------------------------------------------------------

EDGE_FORMULA_IDS: tuple[str, ...] = (
    "F_COSINE_SIMILARITY",
    "F_JACCARD_AFFINITY",
    "F_EDGE_WEIGHT",
    "F_RAG_PRIORITY",
    "F_PATH_COST",
    "F_LOCAL_COHERENCE",
)


# ---------------------------------------------------------------------------
# FormulaRegistry — accessed by all scorer methods
# ---------------------------------------------------------------------------

def _registry():
    """Return the live FormulaRegistry or None (only in non-strict fallback)."""
    try:
        from workers.formula_registry import REGISTRY
        return REGISTRY
    except Exception as exc:  # noqa: BLE001
        print(f"[edge_scorer] registry unavailable: {exc}", file=sys.stderr)
        return None


def validate_edge_formulas() -> dict[str, str]:
    """
    Check that every EDGE_FORMULA_ID is present and ready in the registry.

    Returns a dict mapping formula_id → "ready" | "missing" | "unimplemented".
    Raises workers.formula_registry.FormulaNotReady when any required formula
    is not callable — the system cannot score edges without its math.

    Called at module import so problems surface immediately, not silently at
    first score call.
    """
    from workers.formula_registry import REGISTRY, FormulaNotReady

    report: dict[str, str] = {}
    missing: list[str] = []

    for fid in EDGE_FORMULA_IDS:
        if fid not in REGISTRY:
            report[fid] = "missing"
            missing.append(fid)
            continue
        spec = REGISTRY.inspect(fid)
        status = spec.get("status", "unknown")
        report[fid] = status
        if status != "ready":
            missing.append(fid)

    if missing:
        raise FormulaNotReady(
            f"EdgeScorer cannot start — {len(missing)} required formula(s) are not ready: "
            + ", ".join(missing)
            + ". Run sync_notion or fix config/formulas/formula_dictionary.yaml."
        )

    return report


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
    fallback_used:    bool = False   # True only in strict=False mode

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
# Pure-Python fallback math — only used when strict=False
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

    All scoring operations delegate to FormulaRegistry.call() using the
    formula IDs declared in EDGE_FORMULA_IDS.  This is not a soft dependency:
    in strict mode (default) any missing or unimplemented formula raises
    FormulaNotReady immediately.

    Parameters
    ----------
    strict      Enforce formula availability (default True). Set False only
                in tests that explicitly exercise the fallback path.
    rag_O_N     System complexity denominator for F_RAG_PRIORITY (default 1.0).
    rag_P_risk  Perplexity risk denominator for F_RAG_PRIORITY (default 1.0).
    edge_hop    Default hop count for F_PATH_COST (default 1).
    """

    def __init__(
        self,
        strict:     bool  = True,
        rag_O_N:    float = 1.0,
        rag_P_risk: float = 1.0,
        edge_hop:   int   = 1,
    ) -> None:
        self._strict     = strict
        self._rag_O_N    = rag_O_N
        self._rag_P_risk = rag_P_risk
        self._edge_hop   = edge_hop

        if strict:
            # Fail immediately if formulas are missing — do not defer to
            # first scoring call where errors are harder to diagnose.
            validate_edge_formulas()

    # ── internal helper ──────────────────────────────────────────────────

    def _call(self, formula_id: str, **kwargs) -> float:
        """
        Call a formula through the registry.

        In strict mode: raises FormulaNotReady / FormulaNotFound on failure.
        In non-strict mode: falls back to the _fallback_* functions and logs
        a warning.  Non-strict is for tests and offline tooling only.
        """
        from workers.formula_registry import REGISTRY, FormulaNotReady, FormulaNotFound

        try:
            return float(REGISTRY.call(formula_id, **kwargs))
        except (FormulaNotReady, FormulaNotFound):
            if self._strict:
                raise
            # Non-strict: warn and return sentinel so caller can use fallback
            print(
                f"[edge_scorer] non-strict: formula {formula_id} not ready, using fallback",
                file=sys.stderr,
            )
            raise  # let the caller decide which fallback to use

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

        try:
            return self._call("F_COSINE_SIMILARITY", A=la, B=lb), False
        except Exception:
            if self._strict:
                raise
            return _fallback_cosine(la, lb), True

    def jaccard_affinity(
        self,
        tags_a: list[str],
        tags_b: list[str],
    ) -> tuple[float, bool]:
        """Tag set overlap via F_JACCARD_AFFINITY."""
        try:
            return self._call("F_JACCARD_AFFINITY", A=tags_a, B=tags_b), False
        except Exception:
            if self._strict:
                raise
            return _fallback_jaccard(tags_a, tags_b), True

    def edge_weight(
        self,
        sim_scores:    list[float],
        reinforcement: list[float],
    ) -> tuple[float, bool]:
        """
        Reinforcement-weighted edge activation via F_EDGE_WEIGHT.

        sim_scores      List of per-facet cosine similarities.
        reinforcement   Parallel list of reinforcement multipliers.
        """
        try:
            return self._call(
                "F_EDGE_WEIGHT",
                sim_list=sim_scores,
                reinforcement_list=reinforcement,
            ), False
        except Exception:
            if self._strict:
                raise
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
        O_N_    = O_N    if O_N    is not None else self._rag_O_N
        P_risk_ = P_risk if P_risk is not None else self._rag_P_risk

        try:
            return self._call(
                "F_RAG_PRIORITY",
                X_norm=X_norm,
                O_N=max(O_N_, 1e-9),
                T_pos=T_pos,
                P_risk=max(P_risk_, 1e-9),
            ), False
        except Exception:
            if self._strict:
                raise
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
        try:
            return self._call("F_PATH_COST", Hop_Count=hops, sim=sim), False
        except Exception:
            if self._strict:
                raise
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
        try:
            return self._call(
                "F_LOCAL_COHERENCE",
                w_list=w_list,
                sim_list=sim_list,
                dist_list=dist_list,
            ), False
        except Exception:
            if self._strict:
                raise
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

        All five formula calls go through the registry.  In strict mode any
        missing formula surfaces as FormulaNotReady here, not as a silent
        wrong answer.

        Parameters
        ----------
        stem_a / stem_b   Node stems (used as labels only).
        vec_a / vec_b     Embedding vectors (L2-normalised preferred).
        tags_a / tags_b   Tag lists for Jaccard affinity.
        hop_count         Graph distance for path cost.
        """
        trace:    dict[str, Any] = {}
        fallback: bool           = False

        # Lazy-import the gate so score_pair works even when mcp_server is
        # not on the path (e.g. graph-only scripts).  Failures are silent
        # — gate recording is best-effort; it must never block a score.
        try:
            from mcp_server.formula_gate import GATE as _gate
        except Exception:  # noqa: BLE001
            _gate = None

        def _record(formula_id: str, result: float) -> None:
            if _gate is not None:
                try:
                    _gate.record(formula_id, result)
                except Exception:  # noqa: BLE001
                    pass

        cos, fb = self.cosine_sim(vec_a, vec_b)
        trace["F_COSINE_SIMILARITY"] = round(cos, 6)
        fallback = fallback or fb
        _record("F_COSINE_SIMILARITY", cos)

        jac, fb = self.jaccard_affinity(list(tags_a), list(tags_b))
        trace["F_JACCARD_AFFINITY"] = round(jac, 6)
        fallback = fallback or fb
        _record("F_JACCARD_AFFINITY", jac)

        ew, fb = self.edge_weight([cos], [jac + 1.0])
        trace["F_EDGE_WEIGHT"] = round(ew, 6)
        fallback = fallback or fb
        _record("F_EDGE_WEIGHT", float(ew))

        rp, fb = self.rag_priority(X_norm=cos, T_pos=1.0 - jac)
        trace["F_RAG_PRIORITY"] = round(rp, 6)
        fallback = fallback or fb
        _record("F_RAG_PRIORITY", float(rp))

        pc, fb = self.path_cost(sim=cos, hop_count=hop_count)
        trace["F_PATH_COST"] = round(pc, 6)
        fallback = fallback or fb
        _record("F_PATH_COST", float(pc))

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

        Returns sorted (rag_priority, stem, EdgeScore), highest first.
        """
        exclude = exclude or set()

        try:
            from mcp_server.formula_gate import GATE as _gate
        except Exception:  # noqa: BLE001
            _gate = None

        def _record(formula_id: str, result: float) -> None:
            if _gate is not None:
                try:
                    _gate.record(formula_id, result)
                except Exception:  # noqa: BLE001
                    pass

        target_norm = target_vec / (np.linalg.norm(target_vec) + 1e-12)
        corp_norms  = corpus_vecs / (
            np.linalg.norm(corpus_vecs, axis=1, keepdims=True) + 1e-12
        )
        raw_sims: np.ndarray = corp_norms @ target_norm

        results: list[tuple[float, str, EdgeScore]] = []
        for i, (stem, tags, cos_raw) in enumerate(
            zip(corpus_stems, corpus_tags, raw_sims)
        ):
            if stem == target_stem or stem in exclude:
                continue
            cos = float(np.clip(cos_raw, 0.0, 1.0))
            if cos < threshold:
                continue

            _record("F_COSINE_SIMILARITY", cos)
            jac, _ = self.jaccard_affinity(target_tags, tags)
            _record("F_JACCARD_AFFINITY", float(jac))
            ew,  _ = self.edge_weight([cos], [jac + 1.0])
            _record("F_EDGE_WEIGHT", float(ew))
            rp,  _ = self.rag_priority(X_norm=cos, T_pos=1.0 - jac)
            _record("F_RAG_PRIORITY", float(rp))
            pc,  _ = self.path_cost(sim=cos)
            _record("F_PATH_COST", float(pc))

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
# Module singleton — strict=True: import fails if formulas are misconfigured
# ---------------------------------------------------------------------------

SCORER = EdgeScorer(strict=True)
