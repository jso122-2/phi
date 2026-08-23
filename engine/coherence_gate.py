"""
AutonomousGate — decides whether a newly discovered SymbolNode is worth
admitting to the UnifiedGraph.

Three outcomes for every symbol:
    ADMIT   Add to graph immediately
    DEFER   Re-evaluate next crawl cycle (stored in a SQLite pending queue)
    SKIP    Discard permanently (path/content excluded)

Decision rules (first match wins):
    1. Hard skip — excluded path pattern or binary/tiny content
    2. Connectivity — symbol imports ≥ N names already in the graph name index
    3. Novelty — embedding cosine distance to nearest node > threshold
    4. Quality — has a docstring ≥ min_docstring_len chars
    5. Default → DEFER

Every decision is persisted to logs/gate.db for inspection.
"""
import enum
import logging
import os
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set

import numpy as np

from phi.data.symbol_node import SymbolNode

logger = logging.getLogger(__name__)

# ── Excluded path fragments (always hard-skip regardless of other rules) ──────
_SKIP_PATH_FRAGMENTS: Set[str] = {
    "/test/", "/tests/", "/__tests__/", "/spec/", "/specs/",
    "/fixtures/", "/mocks/", "/mock/", "/stubs/",
    "/node_modules/", "/.git/", "/__pycache__/",
    "/build/", "/dist/", "/.venv/", "/venv/",
    "/site-packages/",
}


class GateAction(enum.Enum):
    ADMIT = "admit"
    DEFER = "defer"
    SKIP  = "skip"


@dataclass
class GateDecision:
    action: GateAction
    reason: str
    score: float = 0.0


class AutonomousGate:
    """
    Rule-based + embedding-based admission gate for the unified graph.

    Args:
        cfg:         gate config dict (from config.yaml["gate"])
        name_index:  Dict mapping symbol name → node_id from the existing graph.
                     Pass {} for a cold-start (no existing graph).
        log_path:    Path to SQLite gate log. Created automatically.
    """

    def __init__(
        self,
        cfg: Optional[dict] = None,
        name_index: Optional[Dict[str, int]] = None,
        log_path: Optional[str] = None,
    ) -> None:
        cfg = cfg or {}
        self.min_tokens: int           = cfg.get("min_tokens", 10)
        self.max_tokens: int           = cfg.get("max_tokens", 2000)
        self.novelty_threshold: float  = cfg.get("novelty_threshold", 0.40)
        self.min_import_hits: int      = cfg.get("min_import_hits", 2)
        self.min_docstring_len: int    = cfg.get("min_docstring_len", 30)

        self.name_index: Dict[str, int] = name_index or {}

        self._log_path = log_path or cfg.get("log_path", "logs/gate.db")
        self._pending: List[SymbolNode] = []   # DEFER queue
        self._db: Optional[sqlite3.Connection] = None
        self._init_db()

    # ──────────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────────

    def evaluate(
        self,
        sym: SymbolNode,
        embedding: Optional[np.ndarray] = None,
        nearest_sim: Optional[float] = None,
    ) -> GateDecision:
        """
        Evaluate a single SymbolNode and return a GateDecision.

        Args:
            sym:         The symbol to evaluate.
            embedding:   Pre-computed embedding for novelty scoring (optional).
            nearest_sim: Pre-computed nearest-neighbour similarity (optional).
                         If both embedding and nearest_sim are given, nearest_sim wins.
        """
        decision = self._run_rules(sym, embedding, nearest_sim)
        sym.admitted = (decision.action == GateAction.ADMIT)
        sym.gate_score = decision.score
        self._log(sym, decision)

        if decision.action == GateAction.DEFER:
            self._pending.append(sym)

        return decision

    def evaluate_batch(
        self,
        symbols: List[SymbolNode],
        embeddings: Optional[np.ndarray] = None,
        existing_embs: Optional[np.ndarray] = None,
    ) -> List[GateDecision]:
        """
        Evaluate a batch of SymbolNodes, optionally with pre-computed embeddings.

        Nearest-similarity is computed once against existing_embs for efficiency.
        """
        nearest_sims: List[Optional[float]] = [None] * len(symbols)

        if embeddings is not None and existing_embs is not None and len(existing_embs) > 0:
            # Batch cosine similarity: (N_new, D) × (D, N_existing) → (N_new, N_existing)
            nq = embeddings / (np.linalg.norm(embeddings, axis=1, keepdims=True) + 1e-8)
            ne = existing_embs / (np.linalg.norm(existing_embs, axis=1, keepdims=True) + 1e-8)
            sims = nq @ ne.T  # (N_new, N_existing)
            nearest_sims = sims.max(axis=1).tolist()

        decisions = []
        for i, sym in enumerate(symbols):
            emb = embeddings[i] if embeddings is not None else None
            nsim = nearest_sims[i]
            decisions.append(self.evaluate(sym, embedding=emb, nearest_sim=nsim))

        return decisions

    def flush_pending(
        self,
        embeddings: Optional[np.ndarray] = None,
        existing_embs: Optional[np.ndarray] = None,
    ) -> List[SymbolNode]:
        """
        Re-evaluate deferred symbols. Returns those that are now admitted.
        Called at the start of each crawl cycle so new graph context can
        unlock previously deferred symbols.
        """
        if not self._pending:
            return []

        pending = self._pending[:]
        self._pending.clear()

        decisions = self.evaluate_batch(pending, embeddings=embeddings, existing_embs=existing_embs)
        admitted = [s for s, d in zip(pending, decisions) if d.action == GateAction.ADMIT]
        logger.info(
            "Pending flush: %d deferred → %d admitted, %d re-deferred, %d skipped",
            len(pending),
            sum(1 for d in decisions if d.action == GateAction.ADMIT),
            sum(1 for d in decisions if d.action == GateAction.DEFER),
            sum(1 for d in decisions if d.action == GateAction.SKIP),
        )
        return admitted

    def update_name_index(self, name_index: Dict[str, int]) -> None:
        """Refresh the name index after the graph is rebuilt."""
        self.name_index = name_index

    def summary(self) -> dict:
        """Return gate statistics from the SQLite log."""
        if self._db is None:
            return {}
        cur = self._db.execute(
            "SELECT action, COUNT(*) FROM gate_log GROUP BY action"
        )
        return {row[0]: row[1] for row in cur.fetchall()}

    # ──────────────────────────────────────────────────────────────────────────
    # Rules
    # ──────────────────────────────────────────────────────────────────────────

    def _run_rules(
        self,
        sym: SymbolNode,
        embedding: Optional[np.ndarray],
        nearest_sim: Optional[float],
    ) -> GateDecision:

        # Rule 1 — Hard skip
        skip_reason = self._hard_skip(sym)
        if skip_reason:
            return GateDecision(GateAction.SKIP, skip_reason, score=0.0)

        # Rule 2 — Connectivity via imports
        import_hits = sum(1 for imp in sym.imports if imp in self.name_index)
        if import_hits >= self.min_import_hits:
            return GateDecision(
                GateAction.ADMIT,
                f"connected via {import_hits} imports",
                score=min(0.9, 0.5 + 0.1 * import_hits),
            )

        # Rule 3 — Embedding novelty
        sim = nearest_sim
        if sim is None and embedding is not None:
            # Fallback: no existing embs provided but embedding given — admit as novel
            sim = 0.0
        if sim is not None and sim < self.novelty_threshold:
            return GateDecision(
                GateAction.ADMIT,
                f"novel concept (nearest_sim={sim:.3f})",
                score=round(1.0 - sim, 3),
            )

        # Rule 4 — Docstring quality signal
        if len(sym.docstring) >= self.min_docstring_len:
            return GateDecision(
                GateAction.ADMIT,
                "has docstring",
                score=0.6,
            )

        # Rule 5 — Wikilinks in markdown notes are self-justifying
        if sym.kind == "note" and sym.outlinks:
            return GateDecision(GateAction.ADMIT, "note with outlinks", score=0.7)

        # Default
        return GateDecision(GateAction.DEFER, "low signal — defer to next cycle", score=0.2)

    def _hard_skip(self, sym: SymbolNode) -> Optional[str]:
        """Return a skip reason string if the symbol should be hard-skipped."""
        path_lower = sym.path.replace("\\", "/")
        for fragment in _SKIP_PATH_FRAGMENTS:
            if fragment in path_lower:
                return f"excluded path fragment: {fragment}"

        token_estimate = len((sym.body_snippet + sym.docstring).split())
        if token_estimate < self.min_tokens:
            return f"too small ({token_estimate} tokens)"
        if token_estimate > self.max_tokens:
            return f"too large ({token_estimate} tokens)"

        return None

    # ──────────────────────────────────────────────────────────────────────────
    # SQLite logging
    # ──────────────────────────────────────────────────────────────────────────

    def _init_db(self) -> None:
        try:
            db_path = self._log_path
            os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else ".", exist_ok=True)
            self._db = sqlite3.connect(db_path, check_same_thread=False)
            self._db.execute("""
                CREATE TABLE IF NOT EXISTS gate_log (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts        REAL NOT NULL,
                    path      TEXT,
                    name      TEXT,
                    kind      TEXT,
                    language  TEXT,
                    action    TEXT,
                    reason    TEXT,
                    score     REAL
                )
            """)
            self._db.execute("CREATE INDEX IF NOT EXISTS gate_log_ts ON gate_log(ts)")
            self._db.commit()
        except Exception as e:
            logger.warning("Could not initialise gate DB at %s: %s", self._log_path, e)
            self._db = None

    def _log(self, sym: SymbolNode, decision: GateDecision) -> None:
        if self._db is None:
            return
        try:
            self._db.execute(
                "INSERT INTO gate_log (ts, path, name, kind, language, action, reason, score) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (time.time(), sym.path, sym.name, sym.kind, sym.language,
                 decision.action.value, decision.reason, decision.score),
            )
            self._db.commit()
        except Exception as e:
            logger.debug("Gate log write error: %s", e)

    def __del__(self) -> None:
        if self._db:
            try:
                self._db.close()
            except Exception:
                pass

