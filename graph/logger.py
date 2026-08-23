"""
PromptLogger — write every agent session to the Obsidian vault as a node.

The vault IS the hub.  Every prompt + thinking + outcome becomes a permanent
node in Spotify-rip/sessions/.  PSSPPS discovers which existing nodes are
most semantically related and injects those as wikilinks.

This is the "push to graph" operation — it replaces git push for this project.

SQL write path (vault-only phase)
----------------------------------
After writing the .md projection, log_session() upserts the session into
graph.store (SQL source-of-truth for sessions).  Failures are soft — the .md
is never rolled back if the SQL write fails.
"""
from __future__ import annotations

import logging

import numpy as np

from graph.node import VAULT_ROOT, write_session_node

log = logging.getLogger(__name__)


def log_session(
    prompt: str,
    thinking: str,
    outcome: str,
    index_activations: np.ndarray | None = None,
    perspective_alpha: float = 0.3,
) -> dict:
    """
    Write this session to the vault and discover related graph links.

    Parameters
    ----------
    prompt              : the user's original message / intent
    thinking            : agent's reasoning summary (what was considered)
    outcome             : what was built, decided, or answered
    index_activations   : 8-dim harmonic index state (biases link discovery)
    perspective_alpha   : PSSPPS blend — 0.0 = pure semantic, 1.0 = pure harmonic

    Returns
    -------
    dict with: node_path, discovered_links, rag_confidence, n_docs_searched
    """
    activations = index_activations if index_activations is not None else np.zeros(8)

    # Discover related vault nodes via PSSPPS
    from psspps.pipeline import run_psspps

    full_query = f"{prompt} {thinking} {outcome}"
    result = run_psspps(
        full_query,
        activations,
        top_k=6,
        perspective_alpha=perspective_alpha,
    )
    discovered = [d.title for d in result.top_docs if d.semantic_score > 0.04]

    # Write the .md projection (unchanged — Obsidian facade)
    path = write_session_node(prompt, thinking, outcome, discovered)

    from graph.hub_classifier import classify_hub
    hub_name = classify_hub(prompt, thinking, outcome, discovered)

    try:
        from graph.tracker import record_stems
        record_stems(discovered, "used")
    except Exception:
        pass

    # Dual-write session into SQL store (soft failure — never blocks commit)
    rel_path = str(path.relative_to(VAULT_ROOT)).replace("\\", "/")
    _sql_upsert_session(
        rel_path=rel_path,
        hub=hub_name,
        wikilinks=discovered,
        text=path.read_text(encoding="utf-8"),
        prompt=prompt,
        thinking=thinking,
        outcome=outcome,
        discovered_links=discovered,
        rag_confidence=result.rag_confidence,
    )

    return {
        "node_path": rel_path,
        "discovered_links": discovered,
        "hub_name": hub_name,
        "rag_useful": result.rag_useful,
        "rag_confidence": result.rag_confidence,
        "n_docs_searched": result.n_docs_searched,
    }


def _sql_upsert_session(
    *,
    rel_path: str,
    hub: str,
    wikilinks: list[str],
    text: str,
    prompt: str,
    thinking: str,
    outcome: str,
    discovered_links: list[str],
    rag_confidence: float | None,
) -> None:
    """Write session into SQL store.  Exceptions are caught and logged."""
    try:
        from graph.store import get_store
        stem = rel_path.rsplit("/", 1)[-1].removesuffix(".md")
        get_store().upsert_session(
            rel_path=rel_path,
            title=stem,
            hub=hub,
            tags=["session"],
            wikilinks=wikilinks,
            text=text,
            prompt=prompt,
            thinking=thinking,
            outcome=outcome,
            discovered_links=discovered_links,
            rag_confidence=rag_confidence,
        )
    except Exception as exc:
        log.warning("log_session: SQL upsert failed (non-fatal) — %s", exc)
