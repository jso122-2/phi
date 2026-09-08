"""Graph / vault tools: commit, clean, nest, link, sync, ingest, status, traverse, hub."""
from __future__ import annotations

import json
from collections import Counter
from typing import Any

from mcp_server._gate import requires_init
from mcp_server._state import _dom_queue, _harmonic_index, _vault_hub, mcp
from mcp_server.bus.client import submit_and_maybe_wait
from graph.node import VAULT_ROOT as _VAULT_ROOT
from graph.worker import (
    run_clean as _graph_run_clean,
    run_nest as _graph_run_nest,
    run_status as _graph_run_status,
)
from psspps.scorer import modulate_search_alpha as _modulate_search_alpha
from psspps.scorer import refresh_on_cache as _refresh_on_cache
from sims.harmonic import HUB_SHARD_MAP


@mcp.tool()
@requires_init
def graph_commit(
    prompt: str,
    thinking: str,
    outcome: str,
    wait_s: float = 60.0,
) -> dict[str, Any]:
    """
    Commit this agent session to the Obsidian vault as a permanent node.

    Heavy work (PSSPPS + node write) runs on the mmap/celery bus.
    Index injection happens in this process when the job completes.

    Parameters
    ----------
    prompt   : user intent (≤ 600 chars)
    thinking : agent reasoning summary
    outcome  : what was built, decided, or answered
    wait_s   : seconds to wait for the worker (0 = return job_id immediately)
    """
    with _dom_queue.gate("graph_commit"):
        activations = _harmonic_index.activation_vector()
        alpha = _modulate_search_alpha(activations)
        return submit_and_maybe_wait(
            "graph.commit",
            wait_s=wait_s,
            prompt=prompt,
            thinking=thinking,
            outcome=outcome,
            activations=activations.tolist(),
            perspective_alpha=float(alpha),
        )


@mcp.tool()
def graph_clean() -> dict[str, Any]:
    """
    Scan the Obsidian vault for structural problems (orphans + dead wikilinks).

    Read-only. Init-free — listed in _INIT_FREE_TOOLS.
    """
    with _dom_queue.gate("graph_clean"):
        report = _graph_run_clean()
        return {
            "n_nodes":       report.n_nodes,
            "hub_nodes":     report.hub_nodes,
            "session_nodes": report.session_nodes,
            "orphans":       report.orphans,
            "n_orphans":     len(report.orphans),
            "dead_links":    report.dead_links[:20],
            "n_dead_links":  len(report.dead_links),
        }


@mcp.tool()
def graph_nest() -> dict[str, Any]:
    """
    Suggest semantic hub assignments for untagged vault nodes.

    Read-only. Init-free — listed in _INIT_FREE_TOOLS.
    """
    with _dom_queue.gate("graph_nest"):
        report = _graph_run_nest()
        hub_counts = Counter(s["suggested_hub"] for s in report.suggestions)
        return {
            "n_untagged":         len(report.suggestions),
            "hub_distribution":   dict(hub_counts.most_common()),
            "suggestions":        report.suggestions[:50],
            "total_suggestions":  len(report.suggestions),
        }


@mcp.tool()
@requires_init
def graph_link(threshold: float = 0.25, wait_s: float = 60.0) -> dict[str, Any]:
    """
    Auto-link semantically related nodes within each corpus layer
    (TF-IDF cosine > threshold). Ingest never links into stations.

    Runs on the mmap/celery bus.

    Parameters
    ----------
    threshold : minimum cosine similarity to inject a link (default 0.25)
    wait_s    : seconds to wait for the worker (0 = return job_id immediately)
    """
    with _dom_queue.gate("graph_link"):
        return submit_and_maybe_wait("graph.link", wait_s=wait_s, threshold=threshold)


# Slash-only — Cursor catalog cap 60. Call via run_command("/do sync").
@requires_init
def graph_sync_manifest(manifest_path: str = "keep/ingest-manifest.json") -> dict[str, Any]:
    """
    Apply an ingestion manifest to the harmonic index.

    Reads hub_counts from the manifest, pulses each hub proportionally
    (value = n_docs × 0.10, capped at 2.0), then runs 5 local propagation steps.

    Parameters
    ----------
    manifest_path : path relative to vault root (default "keep/ingest-manifest.json")
    """
    with _dom_queue.gate("graph_sync_manifest"):
        manifest_file = _VAULT_ROOT / manifest_path
        if not manifest_file.exists():
            return {"error": "manifest_not_found", "path": str(manifest_file)}
        try:
            data = json.loads(manifest_file.read_text(encoding="utf-8"))
        except Exception as exc:
            return {"error": "manifest_parse_error", "detail": str(exc)}

        hub_counts: dict[str, int] = data.get("hub_counts", {})
        n_written: int = data.get("n_written", 0)
        if not hub_counts:
            return {
                "warning":       "manifest has no hub_counts — nothing to inject",
                "manifest_path": manifest_path,
                "n_written":     n_written,
            }

        injected: dict[str, Any] = {}
        for hub_name, count in hub_counts.items():
            if hub_name not in HUB_SHARD_MAP:
                injected[hub_name] = {"skipped": True, "reason": "unknown hub"}
                continue
            value = min(count * 0.10, 2.0)
            shards = list(_harmonic_index.inject_from_hub(hub_name, value=value))
            injected[hub_name] = {"count": count, "value": round(value, 4), "shards": shards}

        _harmonic_index.propagate(steps=5, mode="local")
        updated_state = _harmonic_index.state()
        _vault_hub.push_all(harmonic=updated_state)
        return {
            "synced":            True,
            "manifest_path":     manifest_path,
            "n_written":         n_written,
            "hub_injections":    injected,
            "index_step_after":  updated_state.get("step"),
            "total_activation":  round(updated_state.get("total_activation", 0.0), 6),
        }


@mcp.tool()
@requires_init
def graph_ingest(
    source_dir: str,
    dry_run: bool = False,
    max_files: int = 500,
    wait_s: float = 90.0,
) -> dict[str, Any]:
    """
    Run the Oesophagus ingestion pipeline against a source directory.

    Heavy work runs on the mmap/celery bus so progress prints cannot
    corrupt MCP stdout.

    Parameters
    ----------
    source_dir : absolute or vault-relative path to the directory to ingest
    dry_run    : scan and transform but do NOT write to vault
    max_files  : hard cap per run (default 500)
    wait_s     : seconds to wait for the worker (0 = return job_id immediately)
    """
    with _dom_queue.gate("graph_ingest"):
        return submit_and_maybe_wait(
            "graph.ingest",
            wait_s=wait_s,
            source_dir=source_dir,
            dry_run=dry_run,
            max_files=max_files,
        )


@mcp.tool()
def graph_status() -> dict[str, Any]:
    """
    Full graph health snapshot — node counts, sessions, orphans, dead links,
    total wikilinks, and the five most-linked nodes.

    Read-only. Init-free — listed in _INIT_FREE_TOOLS.
    """
    with _dom_queue.gate("graph_status"):
        s = _graph_run_status()
        _refresh_on_cache(s.n_nodes)
        return {
            "n_nodes":         s.n_nodes,
            "n_session_nodes": s.n_session_nodes,
            "n_hubs":          s.n_hubs,
            "n_orphans":       s.n_orphans,
            "n_dead_links":    s.n_dead_links,
            "total_wikilinks": s.total_wikilinks,
            "most_linked": [
                {"node": stem, "incoming": count}
                for stem, count in s.most_linked
            ],
        }


@mcp.tool()
@requires_init
def graph_traverse(
    seed: str,
    max_hops: int = 8,
    context_budget: int = 4_000,
    top_k: int = 3,
    sim_floor: float = 0.10,
    wait_s: float = 60.0,
) -> dict[str, Any]:
    """
    Ride the semantic minecart through the Obsidian vault graph.

    Embedding runs on the mmap/celery bus.

    Parameters
    ----------
    seed           : starting query or exact note title
    max_hops       : maximum vault nodes to visit (default 8)
    context_budget : character budget the cart can carry (default 4000)
    top_k          : candidate neighbours considered per hop (default 3)
    sim_floor      : minimum cosine similarity to keep riding (default 0.10)
    wait_s         : seconds to wait for the worker (0 = return job_id immediately)
    """
    with _dom_queue.gate("graph_traverse"):
        return submit_and_maybe_wait(
            "graph.traverse",
            wait_s=wait_s,
            seed=seed,
            max_hops=max_hops,
            context_budget=context_budget,
            top_k=top_k,
            sim_floor=sim_floor,
        )


@mcp.tool()
@requires_init
def graph_topo_hubs(
    min_component_size: int = 2,
    write_tags: bool = False,
    prefix_filter: str = "",
    apply_cairrn: bool = False,
    wait_s: float = 60.0,
) -> dict[str, Any]:
    """
    Elect topological hubs via β₀ weakly-connected components (Option B).

    Runs on the mmap/celery bus.

    Parameters
    ----------
    min_component_size : ignore components smaller than this (default 2)
    write_tags         : if True, inject ``#topo-hub`` into elected hub files
    prefix_filter      : restrict analysis to node stems starting with this
                         prefix e.g. "source" → only source/ nodes
    apply_cairrn       : if True, pipe the cairrn_snapshot through
                         CAIRRNBridge.ingest_topology as a third overlay
                         (hash-routes elected stems → shards)
    wait_s             : seconds to wait for the worker (0 = return job_id immediately)
    """
    with _dom_queue.gate("graph_topo_hubs"):
        return submit_and_maybe_wait(
            "graph.topo_hubs",
            wait_s=wait_s,
            min_component_size=min_component_size,
            write_tags=write_tags,
            prefix_filter=prefix_filter,
            apply_cairrn=apply_cairrn,
        )


@mcp.tool()
@requires_init
def graph_ingest_source(
    packages: str = "",
    dry_run: bool = False,
    output_subdir: str = "source",
    wait_s: float = 120.0,
) -> dict[str, Any]:
    """
    Ingest Python source modules from this project into the Obsidian vault graph.

    Embedding and vault writes run on the mmap/celery bus.

    Parameters
    ----------
    packages      : comma-separated list of package names to ingest
    dry_run       : extract and report but do NOT write to vault
    output_subdir : vault subdirectory to write nodes into (default "source")
    wait_s        : seconds to wait for the worker (0 = return job_id immediately)
    """
    with _dom_queue.gate("graph_ingest_source"):
        return submit_and_maybe_wait(
            "graph.ingest_source",
            wait_s=wait_s,
            packages=packages,
            dry_run=dry_run,
            output_subdir=output_subdir,
        )


@mcp.tool()
def graph_track_state() -> dict[str, Any]:
    """
    Usage ledger for vault notes: used / accessed / amended counts and heat.

    Git tracks a note only when it is hot (used, amended, or accessed often).
    Read-only. Init-free.
    """
    with _dom_queue.gate("graph_track_state"):
        from graph.tracker import state
        return state()


@mcp.tool()
@requires_init
def graph_track_sync() -> dict[str, Any]:
    """
    Apply usage-weighted git tracking.

    Rewrites the GRAPH-TRACK block in .gitignore so only hot vault notes
    (and hubs / sessions) are tracked, then stages them. Does not commit.
    """
    with _dom_queue.gate("graph_track_sync"):
        from graph.tracker import sync
        result = sync()
        _vault_hub.push_all(
            sim_tool="graph_track_sync",
            sim_result={"n_hot": result.get("n_hot"), "n_staged": result.get("n_staged")},
        )
        return result


@requires_init
def graph_cairrn_topo(
    min_component_size: int = 2,
    write_tags: bool = False,
    prefix_filter: str = "",
    wait_s: float = 60.0,
) -> dict[str, Any]:
    """
    Run topology hub election and pipe the cairrn_snapshot through
    CAIRRNBridge.ingest_topology as a third overlay.

    Equivalent to ``graph_topo_hubs(apply_cairrn=True)``.  The elected WCC
    hubs are hash-routed into the 8 harmonic shards by CAIRRNBridge so their
    topological weight bleeds across shard boundaries (as opposed to the
    station-aligned ``apply_fusion`` path which respects hub-shard mapping).

    Parameters
    ----------
    min_component_size : ignore components smaller than this (default 2)
    write_tags         : if True, inject ``#topo-hub`` into elected hub files
    prefix_filter      : restrict analysis to stems starting with this prefix
    wait_s             : seconds to wait for the worker (0 = return job_id)
    """
    with _dom_queue.gate("graph_cairrn_topo"):
        return submit_and_maybe_wait(
            "graph.topo_hubs",
            wait_s=wait_s,
            min_component_size=min_component_size,
            write_tags=write_tags,
            prefix_filter=prefix_filter,
            apply_cairrn=True,
        )


# Slash-only — Cursor catalog cap 60. Call via run_command("/read vault-hub").
@requires_init
def vault_hub_state() -> dict[str, Any]:
    """Return the current state of the Vault Hub backwards channel."""
    with _dom_queue.gate("vault_hub_state"):
        return {
            "vault_dir":      str(_vault_hub._vault_dir),
            "live_state_file": _vault_hub.LIVE_STATE_FILE,
            "push_count":     _vault_hub._push_count,
            "has_harmonic":   bool(_vault_hub._harmonic),
            "has_sim":        bool(_vault_hub._last_sim),
            "has_queue":      bool(_vault_hub._queue),
            "last_sim_tool":  _vault_hub._last_sim.get("tool") if _vault_hub._last_sim else None,
        }


@mcp.tool()
@requires_init
def graph_annotate(
    target_stem: str,
    comment: str,
    tool_context: str = "",
    confidence: float = 0.75,
) -> dict[str, Any]:
    """
    Write an agent commentary node that annotates an existing vault node.

    Creates sessions/comments/<timestamp>-comment-<slug>.md with frontmatter
    type: agent-comment. PSSPPS retrieves comment nodes with a +0.15 scoring
    boost so they surface above semantically equal station/session nodes.

    Parameters
    ----------
    target_stem  : stem of the vault node being annotated (e.g. "cairrn_dispatch")
    comment      : agent's insight, observation, or decision note (≤ 800 chars)
    tool_context : MCP tool name or short provenance label (e.g. "graph_commit")
    confidence   : float in [0, 1] expressing annotation certainty (default 0.75)
    """
    with _dom_queue.gate("graph_annotate"):
        from graph.node import VAULT_ROOT, write_comment_node
        path = write_comment_node(
            target_stem=target_stem,
            comment=comment,
            tool_context=tool_context,
            confidence=confidence,
        )
        rel = str(path.relative_to(VAULT_ROOT))
        return {
            "written":     rel,
            "target":      target_stem,
            "confidence":  confidence,
            "tool_context": tool_context or None,
        }


# ---------------------------------------------------------------------------
# SQL vault store — stats, project, migrate
# ---------------------------------------------------------------------------


# Slash-only — Cursor catalog cap 60. SQL stats are included in graph_status.
# Call via run_command("/read vault-store") or read graph_status["sql_store"].
def vault_store_stats() -> dict[str, Any]:
    """
    SQL vault store snapshot — node counts by layer, edges, and usage events.

    Read-only. Init-free — listed in _INIT_FREE_TOOLS.
    """
    with _dom_queue.gate("vault_store_stats"):
        from graph.store import get_store
        return get_store().stats()


@mcp.tool()
@requires_init
def vault_project(node_id: str, force: bool = False) -> dict[str, Any]:
    """
    Re-materialise a session .md from its SQL row.

    Only sessions written via the SQL-primary path (log_session → graph_commit)
    can be fully projected.  Migrated sessions return status="skipped".

    Parameters
    ----------
    node_id : canonical node_id e.g. "sessions/2026-08-23-..." or bare stem
    force   : overwrite even when the file hash already matches (default False)
    """
    with _dom_queue.gate("vault_project"):
        from graph.projector import project
        r = project(node_id, force=force)
        out: dict[str, Any] = {
            "node_id": r.node_id,
            "stem":    r.stem,
            "status":  r.status,
        }
        if r.path:
            out["path"] = str(r.path.relative_to(_VAULT_ROOT))
        if r.reason:
            out["reason"] = r.reason
        return out


# ---------------------------------------------------------------------------
# Formula-driven edge scoring
# ---------------------------------------------------------------------------


@mcp.tool()
@requires_init
def graph_edge_score(
    stem_a:     str,
    stem_b:     str,
    hop_count:  int   = 1,
    rag_O_N:    float = 1.0,
    rag_P_risk: float = 1.0,
) -> dict[str, Any]:
    """
    Compute the formula-driven edge activation score between two vault nodes.

    Every numeric result goes through FormulaRegistry.call() — the math is
    not hardcoded but driven by the formula_dictionary.yaml / Notion reservoir.
    Formulas used:

      F_COSINE_SIMILARITY — embedding cosine similarity between the two nodes
      F_JACCARD_AFFINITY  — tag set overlap (|A∩B| / |A∪B|)
      F_EDGE_WEIGHT       — reinforcement-weighted composite of the above
      F_RAG_PRIORITY      — P_sps retrieval priority (X_norm/O_N − T_pos/P_risk)
      F_PATH_COST         — traversal cost (hop_count × (1 − cosine_sim))

    The formula_trace in the response shows which formula_id produced which
    numeric value.  If a formula was updated via sync_notion() since the last
    server start, the new expression is used automatically.

    Parameters
    ----------
    stem_a / stem_b   Vault node stems (filename without extension).
                      Examples: "harmonic-index", "MATH", "mfpt".
    hop_count         Graph distance between the nodes (default 1 for direct link).
    rag_O_N           System complexity denominator for F_RAG_PRIORITY.
    rag_P_risk        Perplexity risk denominator for F_RAG_PRIORITY.

    Returns
    -------
    dict with:
        ok              True on success.
        stem_a/b        Echoed stems.
        cosine_sim      F_COSINE_SIMILARITY result.
        jaccard         F_JACCARD_AFFINITY result.
        edge_weight     F_EDGE_WEIGHT result.
        rag_priority    F_RAG_PRIORITY result (P_sps).
        path_cost       F_PATH_COST result.
        composite       Normalised edge activation strength [0, 1].
        formula_trace   formula_id → value for every formula used.
        fallback_used   True if registry was unavailable (no YAML / PyYAML).
    """
    with _dom_queue.gate("graph_edge_score"):
        try:
            from graph.node import VaultNode, load_vault
            from graph.edge_scorer import EdgeScorer
            from psspps.scorer import build_tfidf, query_vector
            from psspps.retriever import _clean

            scorer = EdgeScorer(rag_O_N=rag_O_N, rag_P_risk=rag_P_risk, edge_hop=hop_count)

            vault = load_vault()
            idx   = {n.stem: n for n in vault}

            if stem_a not in idx:
                return {"ok": False, "error": f"stem_a '{stem_a}' not found in vault"}
            if stem_b not in idx:
                return {"ok": False, "error": f"stem_b '{stem_b}' not found in vault"}

            node_a = idx[stem_a]
            node_b = idx[stem_b]

            # Build TF-IDF vectors as proxies for embeddings
            texts = [
                _clean(node_a.title + " " + node_a.text),
                _clean(node_b.title + " " + node_b.text),
            ]
            mat, vocab = build_tfidf(texts)
            vec_a = mat[0]
            vec_b = mat[1]

            tags_a = list(node_a.tags or [])
            tags_b = list(node_b.tags or [])

            edge = scorer.score_pair(
                stem_a    = stem_a,
                stem_b    = stem_b,
                vec_a     = vec_a,
                vec_b     = vec_b,
                tags_a    = tags_a,
                tags_b    = tags_b,
                hop_count = hop_count,
            )
            result = edge.to_dict()
            result["ok"] = True
            return result

        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc), "stem_a": stem_a, "stem_b": stem_b}


# Slash-only — Cursor catalog cap 60. Run via run_command("/do vault-migrate").
@requires_init
def vault_migrate(batch_size: int = 50) -> dict[str, Any]:
    """
    Scan all vault .md files and upsert them into the SQL store.

    Also replays .graph-usage.json events into usage_events.
    Safe to run repeatedly — skips unchanged nodes (hash match).

    Parameters
    ----------
    batch_size : nodes per commit batch (default 50)
    """
    with _dom_queue.gate("vault_migrate"):
        from graph.migrate import run_migrate
        return run_migrate(batch_size=batch_size)
