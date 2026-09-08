"""PSSPPS session-open context hook — Phase 2 async enrichment.

Two-document system
-------------------
Phase 1 (sync):  sessions/live-init.md   — written at gate-open by _env_check
Phase 2 (async): sessions/live-context.md — written here; PSSPPS top-k +
                 coherence queue ordered by shard activation score.

The `[coherence] ready` sentinel (distinct from legacy `[context]`) fires once
Phase 2 lands so the agent knows to read [[live-context]].

Flow per session:
  First tool call  → submit search.psspps to the mmap/celery bus,
                      spawn background thread to poll, return immediately.
  Subsequent calls → if result has landed, emit one notification line to
                      stderr so the agent knows live-context.md is ready.
  Bus unavailable  → fallback: run run_psspps() in-process in the same
                      background thread, same write path.
"""
from __future__ import annotations

import sys
import threading
from typing import Any

# Human-readable hub → search query mapping (mirrors HUB_SHARD_MAP in sims.harmonic)
_HUB_SHARD_QUERY: dict[str, str] = {
    "HOME":          "session history project overview",
    "MATH":          "harmonic simulation attractor mathematics",
    "CODE":          "engine scheduler implementation code",
    "COMMANDS":      "commands workflow operations",
    "agent-context": "agent context workflow protocol",
}

_context_hook_registered = threading.Event()
_context_result: dict[str, Any] = {}
_context_notified = threading.Event()


def _register_psspps_context_hook() -> None:
    """Register the two-phase PSSPPS context hook. Idempotent."""
    from mcp_server.hooks import REGISTRY as _hook_registry

    if _context_hook_registered.is_set():
        return

    _submitted = threading.Event()

    def _psspps_context_hook(tool_name: str, kwargs: dict) -> None:
        if not _submitted.is_set():
            _submitted.set()
            threading.Thread(
                target=_submit_context_psspps,
                name="psspps-context-bus",
                daemon=True,
            ).start()
            return
        if _context_result and not _context_notified.is_set():
            _context_notified.set()
            n_docs     = _context_result.get("n_docs", 0)
            n_comments = _context_result.get("n_comments", 0)
            source     = _context_result.get("source", "bus")
            n_queue    = len(_context_result.get("coherence_queue", []))
            print(
                f"[coherence] ready — {n_docs} docs, {n_comments} comment node(s), "
                f"{n_queue} hub(s) in coherence queue, source={source}. "
                f"Read [[live-context]] for PSSPPS results + coherence queue.",
                file=sys.stderr,
                flush=True,
            )

    _hook_registry.register(
        name="psspps_context",
        description=(
            "Stream PSSPPS at session open via the mmap/celery bus. "
            "Phase 1: submit + spawn poller (non-blocking). "
            "Phase 2+: emit one stderr notification when result lands."
        ),
        fn=_psspps_context_hook,
    )
    _context_hook_registered.set()


def _hot_shard_query(activations: Any) -> str:
    """Build a text query from the two hottest harmonic shards."""
    try:
        import numpy as np
        from sims.harmonic import HUB_SHARD_MAP

        acts = np.asarray(activations, dtype=float)
        total = float(np.abs(acts).sum())
        if total < 1e-12:
            return "recent session activity vault context agent comment"

        top_shards = set(int(i) for i in np.argsort(np.abs(acts))[::-1][:2])
        hub_queries: list[str] = []
        for hub, shards in HUB_SHARD_MAP.items():
            if any(s in top_shards for s in shards):
                hub_queries.append(_HUB_SHARD_QUERY.get(hub, hub))

        return " ".join(hub_queries) if hub_queries else "recent session activity"
    except Exception:
        return "recent session activity vault context"


def _submit_context_psspps() -> None:
    """
    Background thread: submit search.psspps to the bus, poll for result,
    fall back to direct pipeline if the bus is unavailable or stalls.
    """
    try:
        from mcp_server._state import _harmonic_index
        from mcp_server.bus.client import get_client, worker_alive
        from psspps.scorer import modulate_search_alpha

        activations = _harmonic_index.activation_vector()
        query = _hot_shard_query(activations)
        from graph.topology_index import t_b_to_alpha
        index_alpha = float(modulate_search_alpha(activations))
        t_b = getattr(_harmonic_index, "last_t_b_norm", None)
        if t_b is not None:
            alpha = 0.5 * index_alpha + 0.5 * t_b_to_alpha(float(t_b))
        else:
            alpha = max(0.5, index_alpha)

        client = get_client()
        if client is None or not worker_alive():
            print(
                "[psspps_context_hook] bus unavailable — falling back to direct pipeline",
                file=sys.stderr,
            )
            _fire_direct_psspps(query, activations, alpha)
            return

        ticket = client.submit("search.psspps", {
            "query":             query,
            "activations":       activations.tolist(),
            "top_k":             5,
            "perspective_alpha": alpha,
            "modulation":        None,
        })
        print(
            f"[psspps_context_hook] submitted job {ticket['job_id']!r} "
            f"(query={query!r}, alpha={alpha:.2f})",
            file=sys.stderr,
        )

        if ticket.get("status") == "error":
            _fire_direct_psspps(query, activations, alpha)
            return

        rec = client.wait(ticket["job_id"], timeout=45.0)
        if rec is None or rec.get("status") != "done":
            print(
                f"[psspps_context_hook] bus timed out for job {ticket['job_id']!r} "
                "— falling back to direct pipeline",
                file=sys.stderr,
            )
            _fire_direct_psspps(query, activations, alpha)
            return

        top_docs = rec.get("result", {}).get("top_docs", [])
        _write_and_notify(top_docs, alpha, query, source="bus", activations=activations)

    except Exception as exc:
        print(f"[psspps_context_hook] submit thread failed: {exc}", file=sys.stderr)


def _fire_direct_psspps(query: str, activations: Any, alpha: float) -> None:
    """Fallback: run the PSSPPS pipeline in-process when the bus is down."""
    try:
        from psspps.pipeline import run_psspps

        result = run_psspps(query, activations, top_k=5, perspective_alpha=alpha)
        top_docs = [
            {
                "title":          d.title,
                "path":           d.path,
                "combined_score": d.combined_score,
                "snippet":        d.snippet,
            }
            for d in result.top_docs
        ]
        _write_and_notify(top_docs, alpha, query, source="direct", activations=activations)
    except Exception as exc:
        print(f"[psspps_context_hook] direct fallback failed: {exc}", file=sys.stderr)


# Hub → suggested slash commands, ordered by specificity
_HUB_TOOL_MAP: dict[str, list[str]] = {
    "CODE":          ["/do ingest-source", "/do cairrn CODE 1.0", "/do 10 phi"],
    "MATH":          ["/do sim 1.5", "/do sweep", "/do mfpt"],
    "HOME":          ["/do commit", "/read graph", "/read clean"],
    "COMMANDS":      ["/read status", "/read health", "/read commands"],
    "agent-context": ["/read psspps <query>", "/read find <query>", "/read traverse <seed>"],
}


def _build_coherence_queue(activations: Any) -> list[dict[str, Any]]:
    """
    Build a coherence queue ordered by shard activation score (descending).

    Each entry has hub name, combined shard activation, and suggested tools.
    Only hubs with activation above a noise floor are included.

    Parameters
    ----------
    activations : numpy array of 8 shard activations

    Returns
    -------
    list of {"hub", "activation", "shards", "suggestions"} sorted desc by activation
    """
    try:
        import numpy as np
        from sims.harmonic import HUB_SHARD_MAP

        acts = np.asarray(activations, dtype=float)
        queue: list[dict[str, Any]] = []
        for hub, shard_indices in HUB_SHARD_MAP.items():
            hub_act = float(sum(acts[i] for i in shard_indices if i < len(acts)))
            if hub_act > 1e-4:  # noise floor
                queue.append({
                    "hub":         hub,
                    "activation":  round(hub_act, 4),
                    "shards":      list(shard_indices),
                    "suggestions": _HUB_TOOL_MAP.get(hub, []),
                })
        queue.sort(key=lambda e: e["activation"], reverse=True)
        return queue
    except Exception:
        return []


def _format_coherence_queue(queue: list[dict[str, Any]]) -> str:
    """Render the coherence queue as a Markdown section."""
    if not queue:
        return "*Harmonic index is cold — no coherence signal yet.*"
    lines = []
    for rank, entry in enumerate(queue, 1):
        hub = entry["hub"]
        act = entry["activation"]
        suggestions = entry["suggestions"]
        cmd_str = "  ".join(f"`{s}`" for s in suggestions[:3])
        lines.append(f"{rank}. **{hub}** — activation {act:.4f}")
        if cmd_str:
            lines.append(f"   → {cmd_str}")
    return "\n".join(lines)


def _ground_harmonic_from_docs(
    top_docs: list[dict[str, Any]],
    activations: Any,
) -> dict[str, int]:
    """
    Inject the session-open PSSPPS results into the harmonic ring.

    This is the grounding step that makes PSSPPS the first layer: the vault
    docs retrieved at session open shape the harmonic state, not just the
    other way around.

    Returns the hub_distribution dict for logging.
    """
    try:
        import numpy as np
        from psspps.hub_router import affinity_to_hub
        from mcp_server._state import _harmonic_index

        if _harmonic_index is None:
            return {}

        # Build hub distribution from top-doc affinity_vecs (if present)
        hub_dist: dict[str, int] = {}
        for doc in top_docs:
            aff_raw = doc.get("affinity_vec")
            if aff_raw:
                hub = affinity_to_hub(np.array(aff_raw, dtype=float))
            elif doc.get("peak_hub"):
                hub = doc["peak_hub"]
            else:
                continue
            hub_dist[hub] = hub_dist.get(hub, 0) + 1

        if not hub_dist:
            return {}

        # Gentle injection: 0.08 per doc vote into each hub's shards
        scale = 0.08
        for hub_name, count in hub_dist.items():
            value = min(count * scale, 0.50)  # cap per hub
            _harmonic_index.inject_from_hub(hub_name, value=value)

        # One local propagation step to spread the grounding signal
        _harmonic_index.propagate(steps=1, mode="local")

        return hub_dist

    except Exception as exc:
        print(f"[psspps_context_hook] grounding failed: {exc}", file=sys.stderr)
        return {}


def _write_and_notify(
    top_docs: list[dict[str, Any]],
    alpha: float,
    query: str,
    source: str = "bus",
    activations: Any = None,
) -> None:
    """
    Write live-context.md (Phase 2), ground the harmonic ring, fire sentinel.

    Three actions in one:
    1. Inject top-doc hub distribution into the harmonic ring (grounding).
    2. Write live-context.md with PSSPPS results + coherence queue.
    3. Emit [coherence] ready sentinel to stderr.
    """
    try:
        from graph.node import SESSIONS_DIR, write_live_context

        SESSIONS_DIR.mkdir(exist_ok=True)

        n_comments = sum(
            1 for d in top_docs
            if "sessions/comments/" in d.get("path", "").replace("\\", "/")
        )

        # Phase 2a: ground the harmonic ring from the retrieved docs
        hub_dist = _ground_harmonic_from_docs(top_docs, activations)

        # Build coherence queue from live activations (post-grounding)
        queue = _build_coherence_queue(activations) if activations is not None else []
        queue_md = _format_coherence_queue(queue)

        # Write base live-context.md (PSSPPS results)
        written = write_live_context(top_docs)

        # Append coherence queue + grounding summary
        grounding_line = (
            f"*Harmonic grounding: {hub_dist}*\n\n" if hub_dist else ""
        )
        coherence_section = (
            "\n---\n\n"
            "## Coherence Queue\n\n"
            "*Hubs ordered by shard activation — highest harmonic pressure first.*\n\n"
            f"{queue_md}\n\n"
            "---\n\n"
            f"{grounding_line}"
            f"*Phase 2 complete — source={source}, α={alpha:.2f}, "
            f"{len(top_docs)} docs, {n_comments} comment node(s).*\n"
        )
        with written.open("a", encoding="utf-8") as fh:
            fh.write(coherence_section)

        _context_result.update({
            "n_docs":          len(top_docs),
            "n_comments":      n_comments,
            "alpha":           alpha,
            "query":           query,
            "source":          source,
            "coherence_queue": queue,
            "hub_distribution": hub_dist,
        })

        print(
            f"[coherence] ready — {len(top_docs)} docs retrieved "
            f"({n_comments} comment node(s)), source={source}, α={alpha:.2f}. "
            f"Read [[live-context]] for PSSPPS results + coherence queue.",
            file=sys.stderr,
            flush=True,
        )
    except Exception as exc:
        print(f"[psspps_context_hook] write_and_notify failed: {exc}", file=sys.stderr)
