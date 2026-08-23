"""
TF-IDF semantic scoring + harmonic perspective scoring for PSSPPS.

Semantic score  — cosine similarity between query and document TF-IDF vectors.
Perspective score — dot product of the document's harmonic affinity vector with
                    the current harmonic index activations.

The affinity vector encodes which attractor basins a document "lives in" by
soft-assigning each numeric value found in its text to the nearest basin centre
via a Gaussian kernel.  Documents that discuss maths near the active harmonics
float to the top automatically.
"""
from __future__ import annotations

import math
import re

import numpy as np

from sims.ana_chi import ANA_CHI_CONSTANT
from sims.attractors import ALPHA

BASIN_CENTRES: np.ndarray = np.array([(i + 1) * ALPHA for i in range(8)])
_GAUSSIAN_SIGMA = 0.5 * ALPHA

_STOPWORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "is", "are", "was", "were", "be", "been", "this", "that",
    "it", "as", "by", "from", "not", "do", "if", "so", "no", "can", "all",
    "its", "into", "each", "has", "have", "will", "would", "which", "there",
    "their", "they", "also", "more", "than", "any", "how", "when", "where",
})


# ---------------------------------------------------------------------------
# Tokenisation
# ---------------------------------------------------------------------------


def tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return [t for t in tokens if t not in _STOPWORDS and len(t) > 1]


# ---------------------------------------------------------------------------
# TF-IDF
# ---------------------------------------------------------------------------


def build_tfidf(corpus: list[str]) -> tuple[np.ndarray, list[str]]:
    """
    Build a TF-IDF matrix for a list of plain-text documents.

    Returns
    -------
    tfidf : (n_docs, n_terms) float array, L2-normalised row-wise
    vocab : list of terms in column order
    """
    tokenized = [tokenize(doc) for doc in corpus]

    vocab_set: set[str] = set()
    for tokens in tokenized:
        vocab_set.update(tokens)
    vocab = sorted(vocab_set)
    v_idx = {term: i for i, term in enumerate(vocab)}

    n_docs = len(corpus)
    n_terms = len(vocab)

    tf = np.zeros((n_docs, n_terms), dtype=float)
    for di, tokens in enumerate(tokenized):
        if not tokens:
            continue
        for token in tokens:
            if token in v_idx:
                tf[di, v_idx[token]] += 1.0
        tf[di] /= len(tokens)

    df = (tf > 0).sum(axis=0).astype(float)
    idf = np.log((n_docs + 1.0) / (df + 1.0)) + 1.0

    tfidf = np.nan_to_num(tf * idf, nan=0.0, posinf=0.0, neginf=0.0)
    norms = np.linalg.norm(tfidf, axis=1, keepdims=True)
    norms[norms < 1e-12] = 1.0
    return tfidf / norms, vocab


def query_vector(query: str, vocab: list[str]) -> np.ndarray:
    """Convert a query string to an L2-normalised TF-IDF vector."""
    v_idx = {term: i for i, term in enumerate(vocab)}
    tokens = tokenize(query)
    vec = np.zeros(len(vocab), dtype=float)
    for token in tokens:
        if token in v_idx:
            vec[v_idx[token]] += 1.0
    norm = np.linalg.norm(vec)
    if norm > 1e-12:
        vec /= norm
    return vec


def semantic_scores(query_vec: np.ndarray, tfidf_matrix: np.ndarray) -> np.ndarray:
    """Cosine similarity between query vector and every document row."""
    # np.errstate suppresses a spurious BLAS FP-flag divide warning that
    # some OpenBLAS builds emit even on clean float64 inputs.  Results are correct.
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        scores = tfidf_matrix @ query_vec
    return np.nan_to_num(scores, nan=0.0, posinf=1.0, neginf=0.0)


# ---------------------------------------------------------------------------
# Harmonic perspective
# ---------------------------------------------------------------------------


def harmonic_affinity(numbers: list[float]) -> np.ndarray:
    """
    Map a document's numeric content to an 8-dim basin affinity vector.

    Each number is soft-assigned to every basin via a Gaussian with
    σ = 0.5·α centred on |number|.  The result is L1-normalised so it
    represents a probability distribution over basins.

    Documents with no numbers in the attractor range get a uniform prior.
    """
    affinity = np.zeros(8, dtype=float)
    for num in numbers:
        dists = np.abs(BASIN_CENTRES - abs(num))
        affinity += np.exp(-0.5 * (dists / _GAUSSIAN_SIGMA) ** 2)

    total = affinity.sum()
    if total > 1e-12:
        return affinity / total
    return np.ones(8, dtype=float) / 8.0


def perspective_scores(
    doc_affinities: list[np.ndarray],
    index_activations: np.ndarray,
) -> np.ndarray:
    """
    Dot product of each document's basin affinity with the harmonic index state.

    When the index is cold (all zeros), falls back to a uniform prior so every
    document is weighted equally.
    """
    total = index_activations.sum()
    norm_acts = (index_activations / total) if total > 1e-12 else np.ones(8) / 8.0
    return np.array([float(np.dot(aff, norm_acts)) for aff in doc_affinities])


# ---------------------------------------------------------------------------
# Combined score
# ---------------------------------------------------------------------------


def combined_scores(
    sem: np.ndarray,
    persp: np.ndarray,
    alpha: float = 0.5,
) -> np.ndarray:
    """
    Blend semantic and perspective scores.

    alpha = 0.0 → pure semantic similarity
    alpha = 1.0 → pure harmonic perspective
    """
    return (1.0 - alpha) * sem + alpha * persp


# ---------------------------------------------------------------------------
# Semantic-gated blend
# ---------------------------------------------------------------------------

# Documents below this semantic score get their perspective/Partridge
# contributions linearly suppressed to zero.  This prevents music hub notes
# that print basin numbers in YAML frontmatter (after stripping) or body text
# from winning queries where they have no actual lexical relevance.
_SEM_GATE_FLOOR: float = 0.03


def sem_gated_blend(
    sem: np.ndarray,
    persp: np.ndarray,
    alpha: float = 0.5,
    part: np.ndarray | None = None,
    beta: float = 0.0,
) -> np.ndarray:
    """
    Semantic-gated blend of semantic, perspective, and Partridge scores.

    The gate linearly ramps perspective/Partridge contributions from 0 at
    sem=0 up to full weight at sem >= _SEM_GATE_FLOOR.  The semantic term
    itself is never gated — a pure-semantic result is never suppressed.

    Formula:
        gate       = clip(sem / SEM_GATE_FLOOR, 0, 1)
        sem_w      = max(0, 1 − α − β)
        result     = sem_w · sem  +  (α · persp + β · part) · gate

    When α=0 and β=0 this reduces exactly to sem (backward-compatible).
    When sem=0 the perspective and Partridge terms contribute nothing,
    so zero-semantic-relevance documents cannot win on harmonic pressure alone.
    """
    sem_w = float(np.clip(1.0 - alpha - beta, 0.0, 1.0))
    gate = np.clip(sem / _SEM_GATE_FLOOR, 0.0, 1.0)
    extra = alpha * persp
    if part is not None:
        extra = extra + beta * part
    return sem_w * sem + extra * gate


# ---------------------------------------------------------------------------
# Coherence + search modulation
# ---------------------------------------------------------------------------


def _structural_order(p: np.ndarray) -> float:
    """
    Structural order of a probability distribution over basins.

    1 - H/H_max.  One-hot → 1.0 (max order).  Uniform → 0.0 (max entropy).
    """
    p = np.asarray(p, dtype=float)
    total = float(p.sum())
    if total < 1e-12:
        return 0.0
    p = p / total
    mask = p > 0
    H = float(-np.sum(p[mask] * np.log(p[mask])))
    n = len(p)
    h_max = float(np.log(n)) if n > 1 else 1.0
    if h_max < 1e-12:
        return 0.0
    return float(np.clip(1.0 - H / h_max, 0.0, 1.0))


def coherence_scores(
    doc_affinities: list[np.ndarray],
    index_activations: np.ndarray,
) -> np.ndarray:
    """
    Coherence score per document: structural_order × harmonic_alignment.

    A focused document aligned with the hot shard scores highest.
    A flat (uniform) affinity always scores zero — no structure to lock onto.
    """
    alignment = perspective_scores(doc_affinities, index_activations)
    orders = np.array([
        0.0 if float(np.asarray(aff, dtype=float).sum()) < 1e-12
        else _structural_order(aff)
        for aff in doc_affinities
    ], dtype=float)
    return orders * alignment


def ana_chi_weight(n_wikilinks: int) -> float:
    """
    Topology correction weight derived from the Ana-Chi coherence formula.

    Peaks when log1p(n) ≈ 𝒜_χ = 1.5414 (around 4 wikilinks).
    Orphans and overlinked notes are discounted.  Always in (0, 1].
    """
    n = max(int(n_wikilinks), 0)
    return float(math.exp(-abs(math.log1p(n) - ANA_CHI_CONSTANT) / 0.40))


def modulate_search_alpha(index_activations: np.ndarray) -> float:
    """
    Derive PSSPPS perspective_alpha from the live harmonic index.

    This is the MCP search modulator — the index analogue of phi's
    ``_t_b_to_alpha`` (basin sequestration → retrieval locality).

        cold index  (Σ act ≈ 0)  → 0.5  neutral blend
        peaked index (order → 1) → 1.0  local / harmonic retrieval
        diffuse index (order → 0) → 0.0  global / semantic retrieval
    """
    acts = np.asarray(index_activations, dtype=float).ravel()
    if acts.size == 0:
        return 0.5
    total = float(np.abs(acts).sum())
    if total < 1e-12:
        return 0.5
    return float(_structural_order(np.abs(acts) / total))


# ---------------------------------------------------------------------------
# Partridge bubble-sort scoring
# ---------------------------------------------------------------------------

_PARTRIDGE_RECENCY_HOURS = 48.0   # half-life for recency decay


def partridge_scores(
    doc_paths: list[str],
    ledger: "dict[str, dict]",
    now_utc: "datetime | None" = None,
) -> np.ndarray:
    """
    Partridge cache-eviction sort, converted to a continuous promotion score.

    The sort is defined in the handwritten note as:
      Primary key   : ``used`` count descending  (most frequently retrieved → top)
      Secondary key : ``last_used`` timestamp descending  (most recent → top on ties)
      Tertiary key  : ``accessed`` count descending

    The continuous weight is derived from the Partridge formula:

        T = recency weight in [0, 1]:  exp(-hours_since_last_used / τ)
        p = position weight:  used_norm (normalised frequency)  ∈ [0, 1]
        x = combined recency × frequency:  T * p

        partridge_weight = x * T * p
                         = T² * p         (x = T*p substituted)

    This is equivalent to `|x - T·p| * (|x+1| - 1/p)` evaluated at x = T·p = 0
    for unseen docs and x → 1 for hot docs, giving a smooth promotion signal.

    Docs with no ledger entry score 0.  Scores are L∞-normalised to [0, 1].

    Parameters
    ----------
    doc_paths   : vault-relative paths, same order as the PSSPPS doc list
    ledger      : the .graph-usage.json dict loaded by graph.tracker
    now_utc     : reference datetime (defaults to UTC now); injectable for tests
    """
    from datetime import datetime as _dt, timezone as _tz

    _now = now_utc or _dt.now(_tz.utc)

    def _parse_ts(ts: str | None) -> float:
        """Hours since the given ISO timestamp, or large value if missing."""
        if not ts:
            return _PARTRIDGE_RECENCY_HOURS * 10.0
        try:
            t = _dt.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=_tz.utc)
            return max(0.0, (_now - t).total_seconds() / 3600.0)
        except Exception:
            return _PARTRIDGE_RECENCY_HOURS * 10.0

    n = len(doc_paths)
    if n == 0:
        return np.zeros(0, dtype=float)

    raw = np.zeros(n, dtype=float)
    for i, path in enumerate(doc_paths):
        key = path.replace("\\", "/").lstrip("/")
        if not key.endswith(".md"):
            key = f"{key}.md"
        row = ledger.get(key)
        if not row:
            continue
        used_count = int(row.get("used", 0))
        if used_count == 0:
            continue
        hours = _parse_ts(row.get("last_used"))
        T = float(np.exp(-hours / _PARTRIDGE_RECENCY_HOURS))  # recency ∈ (0, 1]
        raw[i] = float(used_count) * T * T  # freq × recency²

    peak = float(raw.max())
    if peak < 1e-12:
        return raw
    return raw / peak


def modulate_partridge_beta(partridge: np.ndarray) -> float:
    """
    Auto-derive the Partridge blend weight from how much history is present.

    If no doc has ledger data, beta = 0 (fall back to semantic+perspective).
    Otherwise beta scales with the density of nonzero scores, capped at 0.12.

    The 0.12 ceiling is derived empirically: the beta sweep on the live vault
    shows nDCG@3 peaks around 0.10–0.12 and degrades above 0.16 because a
    high-frequency-but-semantically-cold doc (dominant peak) overwhelms the
    semantic component.  Keeping beta ≤ 0.12 gives a safe improvement margin.
    """
    nonzero = float(np.count_nonzero(partridge))
    if nonzero < 1.0:
        return 0.0
    n = max(len(partridge), 1)
    # Scale by fraction of docs with history, capped at 0.12
    density = nonzero / n
    return float(np.clip(density * 0.40, 0.0, 0.12))


# ---------------------------------------------------------------------------
# Corpus-size cache — graph_status refreshes this so scorers see live n_docs
# ---------------------------------------------------------------------------

_on_cache: int | None = None


def refresh_on_cache(n_docs: int) -> None:
    """Record the current vault size. Called by graph_status after each scan."""
    global _on_cache
    _on_cache = n_docs


def _get_o_n(n_docs_fallback: int) -> float:
    """
    Observation scale O(N) = 1 + N/1000.

    Uses the cached vault size when graph_status has run; otherwise the
    caller-supplied fallback count.
    """
    n = _on_cache if _on_cache is not None else n_docs_fallback
    return 1.0 + n / 1000.0
