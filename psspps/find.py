"""
/find — Pericles-scored exact-retrieval pipeline.

Funnel:  all vault docs → top-5 by combined score
                        → Pericles re-scoring
                        → top-3 shown to operator
                        → top-1 as the final answer

The Pericles formula
--------------------
    per = tc_A * (1 + Adp_At) * k / x

where:
    tc_A     — total positional term count: Σ_t Σ_pos 1/(pos+1) for each
                query-token hit in the document body; earlier hits count more.
                Zero tc_A → per = 0, regardless of harmonic state.
    Adp_At   — adaptive harmonic temporal score: perspective_score multiplied by
                exp(−λ · harmonic_step) so fresher index states weigh more.
                Acts as a multiplicative amplifier on top of tc_A, not a
                substitute for it.
    k        — combined TF-IDF + harmonic relevance score (the k-score),
                produced by sem_gated_blend so zero-semantic docs are suppressed.
    x        — confidence denominator: max(|k · N_j|, D, dawn_x)  [∨ = max]
    N_j      — normalised Jules score (entropy, normalised to 0.00 target):
                Shannon entropy of the doc's TF-IDF row, shifted batch-wide
                so the most-focused document scores exactly 0.00.
    D        — drift / iwave score: sin(π · β / 2) where β = k / max_k.
                A positive half-sine iwave — β = 0 → D = 0, β = 1 → D = 1.

Pericles (495–429 BC) — Athenian autocratic statesman.
If Pericles had a scoring formula, it would be this one: precise, positional,
and temporally weighted, with a confidence floor that prevents noise from
inflating weak candidates.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from psspps.retriever import VaultDoc, load_vault_docs
from psspps.scorer import (
    build_tfidf,
    coherence_scores,
    harmonic_affinity,
    perspective_scores,
    query_vector,
    sem_gated_blend,
    semantic_scores,
    tokenize,
)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

FIND_MODES: frozenset[str] = frozenset({"pericles", "semantic", "harmonic", "quick"})


@dataclass
class PericlesScore:
    """All intermediate values for the Pericles formula, fully auditable."""

    tc_A: float      # total positional term count
    Adp_At: float    # adaptive harmonic temporal score
    k: float         # combined relevance score
    N_j: float       # normalised Jules entropy (0.00 = most focused)
    D: float         # drift / iwave score
    x: float         # confidence denominator
    per: float       # final Pericles score  ↑ higher = better


@dataclass
class FindCandidate:
    title: str
    path: str
    coherence_score: float
    perspective_score: float
    combined_score: float
    pericles: PericlesScore
    headings: list[str] = field(default_factory=list)
    wikilinks: list[str] = field(default_factory=list)
    snippet: str = ""
    affinity: list[float] = field(default_factory=list)
    """8-dim L1-normalised harmonic affinity vector — carried for shard feedback."""


@dataclass
class FindResult:
    query: str
    n_docs_searched: int
    candidates_5: list[FindCandidate]   # raw top-5 by combined score (pre-Pericles)
    operator_3: list[FindCandidate]     # Pericles-ranked top-3 shown to operator
    answer: FindCandidate | None        # single best — the final answer


# ---------------------------------------------------------------------------
# tc_A — total positional term count
# ---------------------------------------------------------------------------


def _positional_term_count(query: str, doc_text: str) -> float:
    """
    For every occurrence of a query token in the document body,
    contribute 1/(position+1) — earlier hits score higher.

    Returns the sum across all query tokens and all their occurrences.
    A document with no query-token hits returns 0.0.
    """
    query_tokens: frozenset[str] = frozenset(tokenize(query))
    if not query_tokens:
        return 0.0
    doc_tokens = tokenize(doc_text)
    total = 0.0
    for pos, token in enumerate(doc_tokens):
        if token in query_tokens:
            total += 1.0 / (pos + 1.0)
    return total


# ---------------------------------------------------------------------------
# Adp_At — adaptive harmonic temporal score
# ---------------------------------------------------------------------------


def _adaptive_temporal(
    perspective_score: float,
    harmonic_step: int,
    lambda_decay: float = 0.05,
) -> float:
    """
    Adaptive score of the Active node, temporally weighted.

    Decays the perspective score by exp(−λ · step) so fresher harmonic
    states (lower step count) contribute more heavily.
    """
    weight = float(np.exp(-lambda_decay * max(harmonic_step, 0)))
    return perspective_score * weight


# ---------------------------------------------------------------------------
# N_j — normalised Jules score (entropy → 0.00 target)
# ---------------------------------------------------------------------------


def _jules_entropy_raw(tf_row: np.ndarray) -> float:
    """
    Raw normalised entropy for one document's TF-IDF row.

    Re-L1-normalises the row and computes Shannon entropy H.
    Returns H / log(n_terms) so the result is in [0, 1].
    High entropy → noisy/broad document.  Low entropy → focused document.
    """
    p = np.abs(tf_row)
    total = p.sum()
    if total < 1e-12:
        return 1.0        # no signal → treat as maximum entropy
    p = p / total
    mask = p > 0
    H = float(-np.sum(p[mask] * np.log(p[mask])))
    n = len(tf_row)
    H_max = float(np.log(n)) if n > 1 else 1.0
    return H / H_max if H_max > 0 else 0.0


def _normalise_jules_batch(raw: list[float]) -> list[float]:
    """
    Shift the Jules scores so the minimum maps to 0.00 (the target).

    The most focused document (lowest entropy) scores exactly 0.00.
    All others are non-negative offsets from that baseline.
    """
    arr = np.array(raw, dtype=float)
    shifted = arr - arr.min()
    return shifted.tolist()


# ---------------------------------------------------------------------------
# D — drift / iwave score
# ---------------------------------------------------------------------------


def _drift_iwave(k: float, max_k: float) -> float:
    """
    Drift score, modulated by the positive half-sine iwave.

    β = k / max_k  ∈ [0, 1]   (normalised relevance)
    D = sin(π · β / 2)         (positive half-sine; 0 ≤ D ≤ 1)

    D = 0 when the candidate has zero relevance.
    D = 1 when the candidate sits at peak relevance.
    The sine shape gives a smooth, non-linear boost near the top.
    """
    if max_k < 1e-12:
        return 0.0
    beta = float(np.clip(k / max_k, 0.0, 1.0))
    return float(np.sin(np.pi * beta / 2.0))


# ---------------------------------------------------------------------------
# Pericles formula
# ---------------------------------------------------------------------------


def _pericles(
    tc_A: float,
    Adp_At: float,
    k: float,
    N_j: float,
    D: float,
    dawn_x: float = 0.0,
) -> PericlesScore:
    """
    Compute the Pericles score.

        per = tc_A * (1 + Adp_At) * k / x
        x   = max(|k · N_j|, D, dawn_x)     [∨ = max / logical-OR over magnitudes]

    tc_A is the positional term-count: zero means no query tokens appeared in
    the document, so per = 0 regardless of harmonic pressure.  This prevents
    high-perspective, semantically-irrelevant documents from winning.

    Adp_At is used as a multiplicative amplifier: it can boost a document
    that genuinely matches the query AND is harmonically aligned, but it
    cannot substitute for a missing lexical match.

    x acts as a confidence floor — when N_j is small (focused doc) and D is
    high (strong iwave pull), x is moderate and per is bounded.
    dawn_x is the session-level DAWN confidence (F_DAWN_CONFIDENCE output).
    When the session K is high, dawn_x raises the floor across all candidates
    so only sharply-relevant results pass.
    Division-by-zero is prevented by the 1e-12 floor on x.
    """
    x = max(abs(k * N_j), D, dawn_x, 1e-12)
    per = tc_A * (1.0 + Adp_At) * k / x
    return PericlesScore(
        tc_A=round(tc_A, 6),
        Adp_At=round(Adp_At, 6),
        k=round(k, 6),
        N_j=round(N_j, 6),
        D=round(D, 6),
        x=round(x, 6),
        per=round(per, 6),
    )


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------


def run_find(
    query: str,
    index_activations: np.ndarray,
    harmonic_step: int = 0,
    mode: str = "pericles",
    perspective_alpha: float | None = None,
    dawn_x: float = 0.0,
) -> FindResult:
    """
    /find — Pericles-scored exact vault retrieval.

    Stages
    ------
    1. Load all vault docs.
    2. Score every doc with TF-IDF semantic + harmonic perspective → k-scores.
    3. Take the top-5 candidates by k-score.
    4. Compute Pericles scores for all five.
    5. Re-rank by Pericles score → operator_3 (top-3) and answer (top-1).

    Parameters
    ----------
    query              : keyword / natural-language search string
    index_activations  : 8-dim harmonic shard activation vector
    harmonic_step      : current harmonic index step counter (for Adp_At decay)
    mode               : pericles | semantic | harmonic | quick
    perspective_alpha  : override blend for pericles/quick. None = mode default
                         (MCP passes the live index-modulated alpha here).
    dawn_x             : session DAWN confidence floor (F_DAWN_CONFIDENCE output).
                         Passed through to _pericles so K-weighted session quality
                         raises the Pericles denominator across all candidates.
                         0.0 = no effect (default, backward-compatible).
    """
    if mode not in FIND_MODES:
        mode = "pericles"

    docs: list[VaultDoc] = load_vault_docs()
    if not docs:
        return FindResult(
            query=query,
            n_docs_searched=0,
            candidates_5=[],
            operator_3=[],
            answer=None,
        )

    alpha = {"semantic": 0.0, "harmonic": 1.0, "quick": 0.5, "pericles": 0.5}[mode]
    if mode in ("pericles", "quick") and perspective_alpha is not None:
        alpha = float(np.clip(perspective_alpha, 0.0, 1.0))

    # ---- Semantic + perspective scoring (semantic-gated) -----------------
    tfidf_matrix, vocab = build_tfidf([d["clean_text"] for d in docs])
    q_vec = query_vector(query, vocab)
    sem = semantic_scores(q_vec, tfidf_matrix)
    affinities = [harmonic_affinity(d["numbers"]) for d in docs]
    persp = perspective_scores(affinities, index_activations)
    coh = coherence_scores(affinities, index_activations)
    # Use sem_gated_blend so that zero-semantic docs cannot win on harmonic
    # pressure alone.  mode=semantic forces alpha=0 (pure TF-IDF), which is
    # equivalent to combined_scores with no gate applied.
    k_scores = sem_gated_blend(sem, persp, alpha=alpha)

    # Coherence tiebreaker: structured × aligned docs get a small lift before
    # the top-5 cut so they don't lose their slot to equivalent-score noise.
    max_sem_pre = float(np.max(sem)) if len(sem) > 0 else 0.0
    k_scores = np.clip(k_scores + 0.05 * coh * max_sem_pre, 0.0, 1.0)

    # ---- Top-5 by combined score ------------------------------------------
    n_candidates = min(5, len(docs))
    top5_idx = np.argsort(k_scores)[::-1][:n_candidates]
    max_k = float(k_scores[top5_idx[0]]) if len(top5_idx) > 0 else 1.0

    # ---- Jules entropy for the top-5 batch --------------------------------
    raw_jules = [_jules_entropy_raw(tfidf_matrix[i]) for i in top5_idx]
    norm_jules = _normalise_jules_batch(raw_jules)

    # ---- Build Pericles-scored candidates ---------------------------------
    candidates: list[FindCandidate] = []
    for idx, n_j in zip(top5_idx, norm_jules):
        doc = docs[idx]
        k = float(k_scores[idx])
        p = float(persp[idx])

        tc_A = _positional_term_count(query, doc["clean_text"])
        Adp_At = _adaptive_temporal(p, harmonic_step)
        D = _drift_iwave(k, max_k)
        psc = _pericles(tc_A, Adp_At, k, n_j, D, dawn_x=dawn_x)

        src = doc["clean_text"]
        snippet = (src[:220] + "…") if len(src) > 220 else src

        candidates.append(FindCandidate(
            title=doc["title"],
            path=doc["path"],
            coherence_score=round(float(coh[idx]), 4),
            perspective_score=round(p, 4),
            combined_score=round(k, 4),
            pericles=psc,
            headings=doc["headings"][:5],
            wikilinks=doc["wikilinks"][:8],
            snippet=snippet,
            # Affinity carried for shard feedback injection.
            affinity=[round(float(v), 6) for v in affinities[idx]],
        ))

    # ---- Re-rank → operator_3 → answer -------------------------------------
    if mode == "semantic":
        candidates.sort(key=lambda c: c.combined_score, reverse=True)
    elif mode == "quick":
        candidates.sort(key=lambda c: c.combined_score, reverse=True)
    else:
        candidates.sort(key=lambda c: c.pericles.per, reverse=True)
    operator_3 = candidates[:3]
    answer = candidates[0] if candidates else None

    return FindResult(
        query=query,
        n_docs_searched=len(docs),
        candidates_5=candidates,
        operator_3=operator_3,
        answer=answer,
    )
