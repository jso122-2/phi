"""
Samba GNN — MCP Server
Proper JSON-RPC 2.0 MCP server using FastMCP.
Registers with Cursor via .cursor/mcp.json and exposes the Obsidian graph
orchestration tools as native MCP tools.

Usage (Cursor handles this automatically via .cursor/mcp.json):
    python mcp_server.py

    # With a specific checkpoint:
    python mcp_server.py --checkpoint checkpoints/best.pt

    # To test tools manually:
    python mcp_server.py --dev

The server loads the model lazily on first tool call and caches it.
If no checkpoint exists yet, tools return a helpful "not trained" message
rather than crashing.

Tools exposed:
    samba_find_related      Find notes semantically related to a given note
    samba_suggest_links     Suggest wiki-links that are missing but should exist
    samba_route_query       Route a free-text query to the most relevant notes
    samba_get_clusters      Return topic clusters across the vault
    samba_graph_stats       Vault graph statistics (nodes, edges, χ, Euler spectrum)
    samba_euler_spectrum    Show learned oscillation frequencies from EulerSSM
    samba_refresh           Force re-encode and rebuild the graph representation

Agent write-zone tools (Option-3 write isolation):
    samba_write_note        Create a new note in agent-log/ (or named zone)
    samba_annotate          Append an agent comment to an existing note

Live daemon CAIRRN bridge (IPC via /tmp state file):
    cairrn_hub_state        Read live hub state from the running daemon
    cairrn_inject           Inject an activation into a daemon hub next cycle
"""
import argparse
import glob
import json
import logging
import os
import sys
from typing import Any, Optional

# Load .env from project root so OBSIDIAN_API_KEY and OBSIDIAN_VAULT_PATH are available
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
except ImportError:
    pass

# ── FastMCP ────────────────────────────────────────────────────────────────────
try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    print(
        "ERROR: 'mcp' package not found. Install with: pip install mcp>=1.0.0",
        file=sys.stderr,
    )
    sys.exit(1)

logging.basicConfig(level=logging.WARNING)   # keep stderr quiet during MCP stdio
logger = logging.getLogger("samba_mcp")

# ── Global server ──────────────────────────────────────────────────────────────
mcp = FastMCP(
    name="samba-obsidian",
    instructions=(
        "Samba GNN orchestrates your Obsidian knowledge graph using a lightweight "
        "1.3M-parameter graph neural network with Euler SSM dynamics. "
        "Use these tools to find related notes, surface missing links, cluster "
        "your vault by topic, or route any free-text query through the graph."
    ),
)

# ── Lazy orchestrator singleton ────────────────────────────────────────────────
_orchestrator = None
_checkpoint_path: Optional[str] = None
_config_path: str = os.path.join(os.path.dirname(__file__), "config", "config.yaml")


def _find_best_checkpoint(checkpoint_dir: str = "checkpoints") -> Optional[str]:
    """Auto-discover the best or most recent checkpoint."""
    base = os.path.join(os.path.dirname(__file__), checkpoint_dir)
    # Prefer best.pt
    best = os.path.join(base, "best.pt")
    if os.path.exists(best):
        return best
    # Fallback: most recent perpetual checkpoint
    pattern = os.path.join(base, "perpetual_step_*.pt")
    candidates = sorted(glob.glob(pattern))
    if candidates:
        return candidates[-1]
    # Fallback: most recent epoch checkpoint
    pattern = os.path.join(base, "epoch_*.pt")
    candidates = sorted(glob.glob(pattern))
    return candidates[-1] if candidates else None


def _get_orchestrator():
    """Return the cached SambaOrchestrator, loading it on first call."""
    global _orchestrator
    if _orchestrator is not None:
        return _orchestrator

    ckpt = _checkpoint_path or _find_best_checkpoint()
    if ckpt is None:
        return None

    try:
        from inference import SambaOrchestrator
        _orchestrator = SambaOrchestrator(
            checkpoint_path=ckpt,
            config_path=_config_path,
        )
        logger.info(f"Loaded orchestrator from {ckpt}")
    except Exception as e:
        logger.error(f"Failed to load orchestrator: {e}")
        return None

    return _orchestrator


def _not_trained_msg() -> str:
    return (
        "No trained checkpoint found. "
        "Run: python train.py --stage finetune\n"
        "Or for perpetual pretraining: python pretrain_loop.py\n"
        "Checkpoints will appear in checkpoints/ automatically."
    )


def _fmt(results: Any) -> str:
    """Format results as pretty JSON for MCP text response."""
    return json.dumps(results, indent=2, ensure_ascii=False)


# ──────────────────────────────────────────────────────────────────────────────
# Tools
# ──────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def samba_find_related(note: str, top_k: int = 10) -> str:
    """
    Find notes in your Obsidian vault that are semantically related to a given note.

    The Samba GNN uses Euler SSM dynamics over the knowledge graph to find notes
    that are not just lexically similar, but structurally connected through the
    graph's learned topology.

    Args:
        note:   Title of the source note (exact or approximate match)
        top_k:  Number of related notes to return (default 10)

    Returns:
        JSON list of {"title", "path", "score"} sorted by relevance
    """
    orch = _get_orchestrator()
    if orch is None:
        return _not_trained_msg()
    try:
        results = orch.find_related(note, top_k=top_k)
        if not results:
            return f'No results found for "{note}". Check the note title spelling.'
        return _fmt(results)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def samba_suggest_links(note: str, top_k: int = 5) -> str:
    """
    Suggest wiki-links that are semantically justified but don't yet exist in a note.

    Finds notes close in the GNN's learned embedding space to the source note
    that are NOT already linked, and returns them as [[wikilink]] suggestions.
    Useful for discovering missing connections in your knowledge graph.

    Args:
        note:   Title of the note to find missing links for
        top_k:  Number of link suggestions (default 5)

    Returns:
        JSON list of {"title", "path", "score", "suggested_link"} candidates
    """
    orch = _get_orchestrator()
    if orch is None:
        return _not_trained_msg()
    try:
        results = orch.suggest_links(note, top_k=top_k)
        if not results:
            return f'No missing link suggestions for "{note}".'
        return _fmt(results)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def samba_route_query(query: str, top_k: int = 5) -> str:
    """
    Route a free-text question or topic through the Obsidian knowledge graph.

    Encodes the query using the BERT clippings encoder and retrieves the most
    relevant notes using the GNN's learned retrieval head. Does not require the
    query to match any note title — it works on semantic content.

    Args:
        query:  Any text — a question, concept, or topic to look up
        top_k:  Number of relevant notes to return (default 5)

    Returns:
        JSON list of {"title", "path", "score"} — most relevant notes
    """
    orch = _get_orchestrator()
    if orch is None:
        return _not_trained_msg()
    try:
        results = orch.route_query(query, top_k=top_k)
        if not results:
            return "No relevant notes found."
        return _fmt(results)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def samba_get_clusters() -> str:
    """
    Return topic clusters discovered across the entire Obsidian vault.

    The GNN's cluster head uses learned prototype embeddings to soft-assign
    every note to a topic cluster. Each cluster represents a coherent area
    of your knowledge graph — similar to Louvain communities but shaped by
    the Euler SSM's learned dynamics.

    Returns:
        JSON list of {"cluster_id", "notes": [{"title", "score"}]}
        Only clusters with at least one strong member are included.
    """
    orch = _get_orchestrator()
    if orch is None:
        return _not_trained_msg()
    try:
        clusters = orch.get_clusters()
        # Filter to non-empty clusters
        active = [c for c in clusters if any(n["score"] > 0.1 for n in c["notes"])]
        return _fmt(active)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def samba_graph_stats() -> str:
    """
    Return structural statistics about the Obsidian knowledge graph.

    Includes:
    - Node count (V): total notes in vault
    - Edge count (E): total links (wikilinks + tag overlap + semantic)
    - Euler characteristic χ = V - E + T (topological signature)
    - Edge type breakdown
    - Euler SSM eigenvalue summary (learned oscillation frequencies)

    χ = 1  → tree-like vault (efficient, minimal redundancy)
    χ = 2  → sphere-like (closed, complete knowledge structure)
    χ < 0  → fragmented (orphaned notes, broken bridges)
    """
    orch = _get_orchestrator()
    if orch is None:
        return _not_trained_msg()
    try:
        G = orch.graph.nx_graph
        V = G.number_of_nodes()
        E = G.number_of_edges()

        # Triangle count (for χ)
        import networkx as nx
        triangles = sum(nx.triangles(G.to_undirected()).values()) // 3
        chi = V - E + triangles

        # Edge type breakdown
        edge_types = {}
        for _, _, d in G.edges(data=True):
            t = d.get("edge_type", "unknown")
            edge_types[t] = edge_types.get(t, 0) + 1

        # Euler SSM spectrum
        euler_summary = orch.model.euler_eigenvalue_report()

        stats = {
            "vault": {
                "notes": V,
                "links": E,
                "triangles": triangles,
                "euler_characteristic_chi": chi,
                "chi_interpretation": (
                    "tree-like (efficient)" if chi == 1
                    else "sphere-like (closed)" if chi == 2
                    else "complex/fragmented" if chi < 0
                    else f"χ={chi}"
                ),
            },
            "edge_types": edge_types,
            "euler_ssm_spectrum": euler_summary,
            "model_params": orch.model.parameter_report(),
        }
        return _fmt(stats)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def samba_euler_spectrum() -> str:
    """
    Show the learned Euler SSM eigenvalue spectrum — what oscillation frequencies
    the GNN has discovered in your note-writing patterns.

    Each state dimension in the EulerSSM learns:
    - r: contraction rate (how quickly that memory fades)
    - θ: oscillation frequency (how cyclically that concept recurs)

    Slow-rotating states (small θ) encode long-term conceptual threads.
    Fast-rotating states (large θ) encode rapid theme switching.
    States with r near 1 have very long memory; r near 0 forget quickly.

    Returns:
        JSON with r statistics, θ statistics, and estimated memory half-lives
    """
    orch = _get_orchestrator()
    if orch is None:
        return _not_trained_msg()
    try:
        import math
        import torch

        ssm = orch.model.gnn_layers[0].ssm
        r = torch.sigmoid(ssm.r_log).detach()
        theta = ssm.theta.detach()

        # Memory half-life: steps until |h| decays to 0.5 from 1.0
        # |h_t| = r^t → r^t = 0.5 → t = log(0.5)/log(r)
        eps = 1e-8
        half_lives = (math.log(0.5) / (torch.log(r.clamp(min=eps)))).clamp(max=1000)

        spectrum = {
            "contraction_rate_r": {
                "mean": r.mean().item(),
                "min": r.min().item(),
                "max": r.max().item(),
                "std": r.std().item(),
            },
            "oscillation_frequency_theta_rad": {
                "mean": theta.mean().item(),
                "std": theta.std().item(),
                "min": theta.min().item(),
                "max": theta.max().item(),
            },
            "memory_half_life_steps": {
                "mean": half_lives.mean().item(),
                "min": half_lives.min().item(),
                "max": half_lives.max().item(),
            },
            "interpretation": (
                f"Average memory half-life: {half_lives.mean().item():.1f} walk steps. "
                f"Fastest oscillation: {(theta.abs().max() / (2 * math.pi)).item():.3f} cycles/step. "
                f"Slowest oscillation: {(theta.abs().min() / (2 * math.pi)).item():.4f} cycles/step."
            ),
        }
        return _fmt(spectrum)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def samba_refresh() -> str:
    """
    Force the Samba GNN to re-encode all notes and rebuild graph representations.

    Call this after adding many new notes, or if samba_find_related results
    seem stale. Normally the server detects vault changes automatically
    every 30 seconds — this forces an immediate refresh.

    Returns:
        Confirmation with updated node/edge counts
    """
    global _orchestrator
    orch = _get_orchestrator()
    if orch is None:
        return _not_trained_msg()
    try:
        orch.refresh()
        G = orch.graph.nx_graph
        return _fmt({
            "status": "refreshed",
            "notes": G.number_of_nodes(),
            "links": G.number_of_edges(),
        })
    except Exception as e:
        return f"Error during refresh: {e}"


# ──────────────────────────────────────────────────────────────────────────────
# Coherence Engine Tools (write-capable)
# ──────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def samba_apply_links(note: str, dry_run: bool = True) -> str:
    """
    Suggest and optionally apply missing [[wikilinks]] to a note.

    Runs samba_suggest_links to find semantically justified missing links, then
    (when dry_run=False) writes them to the "## Related Notes" section of the
    note's markdown file in the vault.

    Args:
        note:     Title of the note to patch (exact or approximate match).
        dry_run:  If True (default), only reports what would be written.
                  Set to False to actually patch the vault file.

    Returns:
        JSON with suggested links and (if dry_run=False) the count written.
    """
    orch = _get_orchestrator()
    if orch is None:
        return _not_trained_msg()
    try:
        suggestions = orch.suggest_links(note, top_k=5)
        if not suggestions:
            return _fmt({"note": note, "suggestions": [], "links_written": 0})

        # Locate the note path from the orchestrator's graph
        node = None
        for n in orch.graph.notes.values():
            if n.title.lower() == note.lower():
                node = n
                break
        if node is None:
            return _fmt({"error": f"Note '{note}' not found in graph", "suggestions": suggestions})

        links_written = 0
        if not dry_run:
            from engine.vault_writer import VaultWriter
            writer = VaultWriter(dry_run=False)
            links_written = writer.append_links(node.path, suggestions)

        return _fmt({
            "note": note,
            "path": node.path,
            "dry_run": dry_run,
            "suggestions": suggestions,
            "links_written": links_written,
        })
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def samba_create_bridge(cluster_a_id: int, cluster_b_id: int, dry_run: bool = True) -> str:
    """
    Create a bridge note linking two topic clusters.

    Identifies the top representative note in each cluster and writes a new
    markdown file to the vault root containing [[wikilinks]] to both.

    Args:
        cluster_a_id:  Index of the first cluster (from samba_get_clusters).
        cluster_b_id:  Index of the second cluster.
        dry_run:       If True (default), reports what would be created without
                       writing. Set to False to create the file in the vault.

    Returns:
        JSON with the proposed bridge note title, path, and both anchor notes.
    """
    orch = _get_orchestrator()
    if orch is None:
        return _not_trained_msg()
    try:
        import torch
        from engine.bridge_factory import BridgeFactory

        factory = BridgeFactory(orch, min_bridges=0)  # force generation for this pair

        with torch.no_grad():
            assignments = orch.model.cluster(orch._h)  # (N, K)

        K = assignments.size(1)
        if cluster_a_id >= K or cluster_b_id >= K:
            return _fmt({"error": f"Cluster IDs must be < {K}"})

        def _top_note(k):
            scores = assignments[:, k]
            idx = scores.argmax().item()
            note = orch._id_to_note(idx)
            return note.title if note else None

        title_a = _top_note(cluster_a_id)
        title_b = _top_note(cluster_b_id)
        if not title_a or not title_b:
            return _fmt({"error": "Could not find representative notes for one or both clusters"})

        bridge_title = f"Bridge — {factory._short(title_a)} · {factory._short(title_b)}"
        body = (
            f"Connects concepts from cluster {cluster_a_id} ([[{title_a}]]) "
            f"and cluster {cluster_b_id} ([[{title_b}]])."
        )

        result = {
            "bridge_title": bridge_title,
            "cluster_a": {"id": cluster_a_id, "top_note": title_a},
            "cluster_b": {"id": cluster_b_id, "top_note": title_b},
            "dry_run": dry_run,
            "created": False,
        }

        if not dry_run:
            from engine.vault_writer import VaultWriter
            writer = VaultWriter(dry_run=False)
            path = writer.create_bridge_note(
                title=bridge_title,
                cluster_a_note=title_a,
                cluster_b_note=title_b,
                body=body,
            )
            result["created"] = True
            result["path"] = str(path)

        return _fmt(result)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def samba_coherence_report() -> str:
    """
    Full topological coherence report for the vault.

    Aggregates:
    - Current χ and vault topology stats
    - χ trend over the last 10 health log snapshots
    - Top 10 orphan notes (weakest cluster assignment) with link suggestions
    - Cluster health: size and mean assignment score per cluster
    - Prioritised action list: link patches and bridge notes pending

    Returns:
        JSON report suitable for display in a canvas dashboard or chat.
    """
    orch = _get_orchestrator()
    if orch is None:
        return _not_trained_msg()
    try:
        import torch
        import networkx as nx
        from engine.orphan_detector import OrphanDetector
        from engine.bridge_factory import BridgeFactory
        from engine.health_log import HealthLog

        G = orch.graph.nx_graph
        V = G.number_of_nodes()
        E = G.number_of_edges()
        triangles = sum(nx.triangles(G.to_undirected()).values()) // 3
        chi = V - E + triangles
        wikilink_count = sum(
            1 for _, _, d in G.edges(data=True)
            if d.get("edge_type") == "wikilink"
        )

        # χ trend
        health_log = HealthLog()
        recent = health_log.recent(n=10)
        chi_trend = [{"ts": r["ts"], "chi": r["chi"]} for r in recent]

        # Orphans
        detector = OrphanDetector(orch, threshold=0.15)
        orphans = detector.scan(top_k_links=3)
        top_orphans = [o.to_dict() for o in orphans[:10]]

        # Cluster health
        with torch.no_grad():
            assignments = orch.model.cluster(orch._h)  # (N, K)
        K = assignments.size(1)
        cluster_health = []
        for k in range(K):
            scores = assignments[:, k]
            members = (scores > 0.10).sum().item()
            if members == 0:
                continue
            cluster_health.append({
                "cluster_id": k,
                "member_count": int(members),
                "mean_score": round(scores[scores > 0.10].mean().item(), 4),
                "top_note": (lambda n: n.title if n else None)(
                    orch._id_to_note(scores.argmax().item())
                ),
            })
        cluster_health.sort(key=lambda c: -c["mean_score"])

        # Action queue
        factory = BridgeFactory(orch, min_bridges=1)
        bridge_specs = factory.scan()
        actions = []
        for o in orphans[:5]:
            if o.suggestions:
                actions.append({
                    "type": "patch_links",
                    "note": o.title,
                    "link_count": len(o.suggestions),
                    "command": f'samba_apply_links(note="{o.title}", dry_run=False)',
                })
        for b in bridge_specs[:5]:
            actions.append({
                "type": "create_bridge",
                "clusters": [b.cluster_a_id, b.cluster_b_id],
                "title": b.title,
                "command": (
                    f"samba_create_bridge("
                    f"cluster_a_id={b.cluster_a_id}, "
                    f"cluster_b_id={b.cluster_b_id}, "
                    f"dry_run=False)"
                ),
            })

        report = {
            "topology": {
                "notes": V,
                "edges": E,
                "triangles": triangles,
                "chi": chi,
                "wikilink_count": wikilink_count,
            },
            "chi_trend": chi_trend,
            "orphans": {
                "count": len(orphans),
                "threshold": 0.15,
                "top_10": top_orphans,
            },
            "cluster_health": cluster_health,
            "action_queue": actions,
        }
        return _fmt(report)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def samba_record_coherence(comment: str = "") -> str:
    """
    Record a coherence snapshot to the HealthLog — call this whenever you feel
    the vault is in a coherent or meaningful state.

    Computes current topology stats (χ, notes, edges, triangles, wikilink count)
    live from the graph, then writes a timestamped row to logs/coherence_health.db.
    The optional `comment` field lets you annotate *why* you judged the state
    coherent — this reasoning is stored alongside the metrics.

    The HealthLog is the vault's long-term memory of its own structural health.
    Agents can write to it directly; the coherence daemon also writes to it on
    every maintenance cycle. Use samba_coherence_report() to read recent entries.

    Args:
        comment: Free-text note explaining why you are recording this snapshot.
                 Examples: "just patched 3 orphan notes",
                           "cluster scores improved after bridging C1 and C8",
                           "vault feels topologically stable after today's session".

    Returns:
        JSON confirmation with the written snapshot values.
    """
    orch = _get_orchestrator()
    if orch is None:
        return _not_trained_msg()
    try:
        import networkx as nx
        from engine.health_log import HealthLog

        G = orch.graph.nx_graph
        V = G.number_of_nodes()
        E = G.number_of_edges()
        triangles = sum(nx.triangles(G.to_undirected()).values()) // 3
        chi = V - E + triangles
        wikilink_count = sum(
            1 for _, _, d in G.edges(data=True)
            if d.get("edge_type") == "wikilink"
        )

        snapshot = {
            "chi":            float(chi),
            "notes":          V,
            "edges":          E,
            "triangles":      triangles,
            "wikilink_count": wikilink_count,
            "comment":        comment or None,
        }

        log = HealthLog()
        log.append(snapshot)

        return _fmt({
            "status":   "recorded",
            "snapshot": {**snapshot, "ts": log.latest()["ts"]},
        })
    except Exception as e:
        return f"Error: {e}"


# ──────────────────────────────────────────────────────────────────────────────
# Agent write-zone tools
# ──────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def samba_write_note(
    title: str,
    body: str,
    links: Optional[list] = None,
    zone: str = "agent-log",
    session_id: Optional[str] = None,
) -> str:
    """
    Create a new note in the agent write-zone (default: agent-log/).

    Agents should call this when they discover something worth persisting
    to the vault — a new concept, a gap in the graph, a cross-task insight,
    a post-task summary, or an unanswered question surfaced during routing.

    This tool writes ONLY to the designated zone folder and never touches
    your curated notes. Notes are stamped with YAML frontmatter for provenance.

    When to call:
    - A concept or finding emerged that isn't already in the graph
    - The graph has a clear structural gap you want to flag for later
    - A task produced a reusable summary worth linking to other notes
    - An unanswered question warrants a persistent stub for future research

    When NOT to call:
    - Every single query or routine lookup (too noisy)
    - Trivial, session-specific ephemera that won't generalise
    - Content already well-covered by an existing note

    Args:
        title:      Title of the note — concise, descriptive, graph-friendly.
        body:       Main content in markdown. Should be self-contained.
        links:      Optional list of existing note titles to link to
                    (added as [[wikilinks]] in a Related Notes section).
        zone:       Write-zone subfolder. Must be one of the sanctioned zones:
                    "agent-log" (default), "agent-queries", "agent-stubs".
                    Do not pass paths outside the vault root.
        session_id: Optional chat or agent run ID for traceability.

    Returns:
        JSON with the created note's path and frontmatter summary.
    """
    ALLOWED_ZONES = {"agent-log", "agent-queries", "agent-stubs"}
    zone = zone if zone in ALLOWED_ZONES else "agent-log"

    try:
        from engine.vault_writer import VaultWriter
        writer = VaultWriter(dry_run=False)
        path = writer.write_agent_note(
            title=title,
            body=body,
            links=links or [],
            zone=zone,
            session_id=session_id,
        )
        return _fmt({
            "status": "created",
            "path": str(path),
            "zone": zone,
            "title": title,
            "links_added": len(links or []),
        })
    except Exception as e:
        return f"Error writing note: {e}"


@mcp.tool()
def samba_annotate(
    note: str,
    comment: str,
    dry_run: bool = False,
) -> str:
    """
    Append an agent-authored comment to an existing vault note.

    Use this to leave a traceable observation, question, or connection
    on a note you just read or referenced — without altering any of the
    original content. The comment appears under an "## Agent Notes" heading
    and is timestamped automatically.

    Curated content above the heading is never touched. Multiple agents
    can annotate the same note; each call appends a new timestamped entry.

    When to call:
    - You noticed a missing connection while reading a note
    - A note is directly relevant to the current task and worth flagging
    - You want to leave a question or follow-up for yourself or the user
    - A note has outdated or conflicting information worth surfacing

    When NOT to call:
    - You want to make substantive edits to the note's content (use the
      curated zone tools or ask the user instead)
    - The comment would be irrelevant outside the current session

    Args:
        note:     Title of the existing note to annotate (exact or approximate).
        comment:  The observation, question, or link to add. Plain text or markdown.
        dry_run:  If True, reports what would be written without touching the file.

    Returns:
        JSON confirming the annotation was written (or what would be written).
    """
    orch = _get_orchestrator()
    if orch is None:
        return _not_trained_msg()

    try:
        node = None
        for n in orch.graph.notes.values():
            if n.title.lower() == note.lower():
                node = n
                break
        if node is None:
            return _fmt({"error": f"Note '{note}' not found in graph"})

        from engine.vault_writer import VaultWriter
        writer = VaultWriter(dry_run=dry_run)
        modified = writer.annotate_note(node.path, comment)

        return _fmt({
            "status": "annotated" if (modified and not dry_run) else ("dry_run" if dry_run else "skipped"),
            "note": note,
            "path": node.path,
            "comment_preview": comment[:120] + ("…" if len(comment) > 120 else ""),
            "dry_run": dry_run,
        })
    except Exception as e:
        return f"Error annotating note: {e}"


# ──────────────────────────────────────────────────────────────────────────────
# Song derivative tools  (D1 → D4 hierarchical XGBoost scorer)
# ──────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def samba_song_derivatives(top_k: int = 20, min_d4: float = 0.0) -> str:
    """
    Compute D1 → D4 hierarchical derivative scores for all library tracks.

    Scores are derived from a two-arm XGBoost hierarchy trained on your
    library's acoustic, tonal, and social metadata:

        D_1  XGBoost on acoustic + tonal features   (rhythm, spectral, key)
        D_2  XGBoost on social features + D_1 fold  (popularity, plays, release)
        D_3  (D_1 + D_2) / 2                        inbetween mean
        D_4  rolling_mean(D_3, window=15% library)  master derivative curve

    All input features are percentile-rank quantized to [0, 1] before training
    so that BPM and last.fm listener count compete on the same scale.

    D_4 is the master primitive — the smoothed curve tracing quality across
    the sorted library.  It is the score to hand to subsequent systems.

    Args:
        top_k:  number of top-ranked tracks to return (default 20)
        min_d4: filter — only return tracks with D4 ≥ this value (default 0.0)

    Returns:
        JSON with fields:
            total_scored: int — total tracks scored
            tracks: [{rank, path, d1, d2, d3, d4, target}] sorted by D4 descending
    """
    try:
        from phi.models.song_derivative import SongDerivativeModel
        scores = SongDerivativeModel().score_library()
        if not scores:
            return _fmt({"error": "No tracks scored — run phi to populate the library first."})

        ranked = sorted(
            [(path, s) for path, s in scores.items() if s["d4"] >= min_d4],
            key=lambda kv: -kv[1]["d4"]
        )

        tracks = [
            {
                "rank": i + 1,
                "path": path,
                "d1": s["d1"],
                "d2": s["d2"],
                "d3": s["d3"],
                "d4": s["d4"],
                "target": s.get("target"),
            }
            for i, (path, s) in enumerate(ranked[:top_k])
        ]

        return _fmt({
            "total_scored": len(scores),
            "shown":        len(tracks),
            "tracks":       tracks,
        })
    except ImportError:
        return _fmt({"error": "xgboost not installed — pip install xgboost"})
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def samba_cluster_derivatives() -> str:
    """
    Map D4 derivative scores onto the vault's semantic clusters.

    For each cluster returned by the Samba GNN, computes the D4 statistics
    of tracks whose paths appear in that cluster.  This answers:

        "Which topic clusters in the vault contain the highest-quality songs?"
        "Where is quality unevenly distributed across the semantic graph?"

    The D4 spread within a cluster reveals internal heterogeneity — a large
    spread means the cluster spans both weak and strong tracks, a signal that
    the cluster boundary may not align with acoustic quality.

    Requires the vault to have been trained (samba_refresh must have run).
    Falls back gracefully if no library metadata is available.

    Returns:
        JSON list of cluster dicts — each extended with:
            d4_mean    mean D4 of scored tracks in the cluster
            d4_max     highest D4 track in the cluster
            d4_min     lowest D4 track in the cluster
            d4_spread  d4_max − d4_min  (quality dispersion)
            top_track  path of the highest-D4 track
            n_scored   number of cluster notes with D4 scores
    """
    orch = _get_orchestrator()
    if orch is None:
        return _not_trained_msg()
    try:
        from phi.models.song_derivative import SongDerivativeModel
        from phi.graph.derivative_bridge import cluster_d4_profile

        clusters = orch.get_clusters()
        if not clusters:
            return _fmt({"error": "No clusters found — run samba_refresh first."})

        # Gather all paths mentioned across clusters
        all_paths = list({
            note["path"]
            for c in clusters
            for note in c.get("notes", [])
        })

        scores = SongDerivativeModel().score_library(paths=all_paths)

        # Build a lightweight fake snapshot for the bridge
        # (we only need index_of() + d4_scores, not the full CLAP embedding)
        class _Snap:
            def __init__(self, paths, scores):
                self.paths = paths
                import torch, math
                d4 = torch.full((len(paths),), float("nan"), dtype=torch.float32)
                for i, p in enumerate(paths):
                    s = scores.get(p)
                    if s and s.get("d4") is not None and math.isfinite(s["d4"]):
                        d4[i] = s["d4"]
                self.d4_scores = d4
            def index_of(self, path):
                try:
                    return self.paths.index(path)
                except ValueError:
                    return None

        snap = _Snap(all_paths, scores)
        profiled = cluster_d4_profile(clusters, snap)

        # Sort clusters by mean D4 descending
        def _sort_key(c):
            v = c.get("d4_mean", float("nan"))
            import math
            return -v if math.isfinite(v) else float("inf")

        profiled.sort(key=_sort_key)
        return _fmt({"clusters": profiled})

    except ImportError:
        return _fmt({"error": "xgboost not installed — pip install xgboost"})
    except Exception as e:
        return f"Error: {e}"


# ──────────────────────────────────────────────────────────────────────────────
# Forecasting tools
# ──────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def samba_forecast_chi(horizon: int = 3, lookback: int = 20) -> str:
    """
    Forecast future vault topology (Euler χ) from the HealthLog time series.

    Uses exponentially-weighted velocity (Δχ per snapshot) to project chi
    forward by `horizon` steps and computes the Topology Forecast Index:

        pressure  = normalised rate of topological drift |Δχ| / χ_range
        capacity  = wikilink density (links / notes) — how well self-organised
        F         = min(1.0, pressure / capacity)    raw Forecast Index
        F*        = EMA-smoothed F across calls

    Interpretation
    --------------
        F* < 0.20  → stable — vault is settling, low structural drift
        F* < 0.50  → drifting — moderate drift, within normal range
        F* < 0.80  → stressed — drift is outpacing link density
        F* ≥ 0.80  → critical — topological pressure exceeds wikilink capacity

    Returns
    -------
    JSON with fields:
        chi_latest, velocity, forecast_chi (list), direction, pressure,
        capacity, forecast_index, forecast_smooth, status, n_snapshots

    Args:
        horizon:  Number of future snapshots to project (default 3).
        lookback: Number of recent HealthLog rows to consider (default 20).
    """
    try:
        from engine.forecasting_engine import TopologyForecaster
        fe = TopologyForecaster()
        report = fe.forecast(horizon=horizon, lookback=lookback)
        return _fmt(report.to_dict())
    except ValueError as e:
        return _fmt({"error": str(e)})
    except Exception as e:
        return f"Error: {e}"


# ──────────────────────────────────────────────────────────────────────────────
# Spotify enrichment tools
# ──────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def samba_spotify_enrich(limit: int = 100, retry_failed: bool = False) -> str:
    """
    Batch-enrich library tracks with Spotify audio features and popularity.

    Iterates tracks that have never been attempted (or previously failed if
    retry_failed=True) and runs:

      1. ISRC exact-match lookup  (if isrc is already stored in annotations)
      2. title + artist fuzzy search  (fallback)

    Each matched track gains:
      spotify_popularity, spotify_energy, spotify_valence, spotify_danceability,
      spotify_acousticness, spotify_instrumentalness, spotify_speechiness,
      spotify_liveness, spotify_loudness, spotify_tempo, spotify_key, spotify_mode,
      spotify_mood, spotify_enriched=True

    Unmatched tracks are marked spotify_enriched=False so they are not retried
    on subsequent daemon cycles unless retry_failed=True is passed.

    After enrichment, re-run samba_song_derivatives to pick up the new GROUP_B
    social signal in D_2.

    Args:
        limit:         Maximum tracks to attempt in this call (default: 100).
        retry_failed:  Also retry tracks that previously returned no match.

    Returns
    -------
    JSON with: attempted, succeeded, failed, skipped, errors
    """
    try:
        from phi.meta.spotify_bulk_enrich import run_bulk_enrich
        result = run_bulk_enrich(limit=limit, retry_failed=retry_failed)
        return _fmt({
            "attempted": result.attempted,
            "succeeded": result.succeeded,
            "failed":    result.failed,
            "skipped":   result.skipped,
            "errors":    result.errors,
            "summary":   str(result),
        })
    except Exception as e:
        return f"Error: {e}"


# ──────────────────────────────────────────────────────────────────────────────
# CAIRRN z-awareness tools
# ──────────────────────────────────────────────────────────────────────────────

_cairrn_bridge = None


def _get_cairrn():
    """Return the shared CairnBridge singleton, creating it on first call."""
    global _cairrn_bridge
    if _cairrn_bridge is not None:
        return _cairrn_bridge
    try:
        from engine.cairrn_bridge import CairnBridge
        _cairrn_bridge = CairnBridge(
            tau=30.0,
            coherence_floor=0.50,
            z_window=32,
            z_spawn_threshold=2.5,
        )
        logger.info("CairnBridge singleton initialised")
    except Exception as e:
        logger.error(f"Failed to initialise CairnBridge: {e}")
    return _cairrn_bridge


@mcp.tool()
def samba_cairrn_z_report() -> str:
    """
    Report the current CAIRRN hub state, including z-awareness scores for each hub.

    The z-awareness score measures how many standard deviations the current hub
    activation is from its rolling history (window=32 steps). This adds a
    magnitude-axis signal alongside the time-axis coherence score:

        coherence  — has this hub been running too long without a reset?
        z_awareness — is this hub's activation level statistically unusual RIGHT NOW?

    Interpretation of z_awareness:
        |z| < 1.0   normal
        |z| 1-2.5   mildly elevated — monitor
        |z| ≥ 2.5   z-hot spike — statistically anomalous

    Returns:
        JSON with per-hub state (activation, coherence, z_awareness, shard, steps)
        plus global_coherence, global_z_awareness, and any active z-hot hubs.
    """
    bridge = _get_cairrn()
    if bridge is None:
        return _fmt({"error": "CairnBridge not available"})
    try:
        state   = bridge.hub_state()
        gz      = bridge.global_z_awareness()
        gc      = bridge.global_coherence()
        z_hot   = bridge.z_awareness_signals()
        coh_sig = bridge.spawn_signals()

        return _fmt({
            "hubs":              state,
            "global_coherence":  round(gc, 4),
            "global_z":          round(gz, 4),
            "z_hot_hubs":        {k: round(v, 4) for k, v in z_hot.items()},
            "incoherent_hubs":   {k: round(v, 4) for k, v in coh_sig.items()},
            "summary":           bridge.report(),
        })
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def samba_cairrn_z_inject(
    snapshot: Optional[dict] = None,
    hub: str = "CODE",
    metric: float = 0.5,
    write_on_spike: bool = True,
) -> str:
    """
    Feed a metric (or full vault snapshot) into the CAIRRN bridge and surface
    z-awareness results. If a z-spike is detected and write_on_spike=True, writes
    a timestamped annotation to the vault so the event becomes part of the graph.

    Two usage modes:

    1. Single-hub step (simple):
         samba_cairrn_z_inject(hub="CODE", metric=0.85)
         Runs one metric through the named hub pipeline and returns the result.

    2. Full snapshot ingest (recommended for coherence daemon integration):
         samba_cairrn_z_inject(snapshot={"chi": 3.2, "V": 1500, "beta_1": 280,
                                          "orphan_count": 12, "links_written": 0.05})
         Routes all five vault metrics through their respective hubs in one call.
         Snapshot keys accepted:
             Full topology:  chi, V, beta_1, orphan_count, links_written
             Graph stats:    euler_chi, nodes, edges, components, density

    Vault write on spike:
        When |z| ≥ z_spawn_threshold (default 2.5) for any hub, the bridge writes
        a timestamped note to agent-log/ recording the spike — making z-awareness
        events part of the long-term vault graph rather than transient in-memory signals.

    Args:
        snapshot:       Full vault metrics dict (if provided, hub+metric are ignored).
        hub:            CAIRRN hub for single-hub mode (HOME/MATH/CODE/COMMANDS/agent-context).
        metric:         Raw scalar to feed through the hub pipeline [0, 1].
        write_on_spike: Write a vault annotation when a z-spike is detected.

    Returns:
        JSON with pipeline result(s), z-awareness signals, and vault write status.
    """
    bridge = _get_cairrn()
    if bridge is None:
        return _fmt({"error": "CairnBridge not available"})

    try:
        import time as _time
        from engine.vault_writer import VaultWriter

        results = []

        if snapshot:
            # Full snapshot mode — ingest_vault_snapshot steps all five hubs
            bridge.ingest_vault_snapshot(snapshot)
            for hub_name, hub_state in bridge.hub_state().items():
                results.append({
                    "hub":         hub_name,
                    "coherence":   hub_state["coherence"],
                    "z_awareness": hub_state["z_awareness"],
                    "activation":  hub_state["activation"],
                    "shard":       hub_state["shard"],
                })
        else:
            # Single-hub step mode
            result = bridge.step(hub, metric)
            results.append({
                "hub":         result.hub,
                "metric":      result.metric,
                "modulated":   result.modulated,
                "shard":       result.shard,
                "coherence":   result.coherence,
                "z_awareness": result.z_awareness,
                "rerouted":    result.rerouted,
            })

        z_signals  = bridge.z_awareness_signals()
        coh_signals = bridge.spawn_signals()
        vault_write = None

        # Vault write on z-spike — makes the event part of the graph
        if write_on_spike and z_signals:
            try:
                writer = VaultWriter()
                ts     = _time.strftime("%Y-%m-%d %H:%M:%S UTC", _time.gmtime())
                spike_lines = "\n".join(
                    f"- **{h}**: z={z:+.3f} ({'↑ burst' if z > 0 else '↓ collapse'})"
                    for h, z in sorted(z_signals.items(), key=lambda kv: -abs(kv[1]))
                )
                gz   = bridge.global_z_awareness()
                body = (
                    f"CAIRRN z-awareness spike detected at {ts}.\n\n"
                    f"**global_z** = {gz:.4f}  "
                    f"(threshold {bridge.z_spawn_threshold})\n\n"
                    f"## Hot hubs\n\n{spike_lines}\n\n"
                    f"## Full hub state\n\n"
                    + "\n".join(
                        f"- {n}: coh={s['coherence']:.3f}  z={s['z_awareness']:+.3f}  "
                        f"activation={s['activation']:.4f}  steps={s['steps']}"
                        for n, s in bridge.hub_state().items()
                    )
                )
                note_path = writer.write_agent_note(
                    title=f"CAIRRN z-spike {ts}",
                    body=body,
                    links=list(z_signals.keys()),
                    zone="agent-log",
                )
                vault_write = {"status": "written", "path": str(note_path)}
                logger.info("CAIRRN z-spike written to vault: %s", note_path)
            except Exception as we:
                vault_write = {"status": "error", "detail": str(we)}

        return _fmt({
            "pipeline_results": results,
            "z_signals":        {k: round(v, 4) for k, v in z_signals.items()},
            "coherence_signals": {k: round(v, 4) for k, v in coh_signals.items()},
            "global_z":         round(bridge.global_z_awareness(), 4),
            "vault_write":      vault_write,
            "summary":          bridge.report(),
        })

    except Exception as e:
        return f"Error: {e}"


# ──────────────────────────────────────────────────────────────────────────────
# Mycelial Network tools (CAIRRN-aware soft edge activation)
# ──────────────────────────────────────────────────────────────────────────────

_mycelial_net = None


def _get_mycelial() -> Optional[Any]:
    """Return the cached MycelialNetwork, initialising it on first call."""
    global _mycelial_net
    if _mycelial_net is not None:
        return _mycelial_net
    orch = _get_orchestrator()
    if orch is None:
        return None
    try:
        from engine.mycelial import MycelialNetwork
        _mycelial_net = MycelialNetwork(orch)
        logger.info("MycelialNetwork initialised")
    except Exception as e:
        logger.error(f"Failed to initialise MycelialNetwork: {e}")
        return None
    return _mycelial_net


@mcp.tool()
def samba_mycelial_spore(
    query: str,
    hub: str = "HOME",
    threshold: float = 0.30,
) -> str:
    """
    Inject a concept spore into the CAIRRN-aware mycelial network.

    Routes the query through Samba to find colonisation points (entry notes),
    runs the full CAIRRN three-layer pipeline (Ana-Chi → neg_exp sharding →
    coherence enforcement), then activates soft edges (hyphae) between related
    notes. Surfaces latent anastomoses — wiki-links that should exist but don't.

    CAIRRN hubs:
        HOME         true_center basin, gravity 3.0 — mutualistic, bidirectional
        MATH         white_peak,  gravity 2.0 — explorative, rattling decay
        CODE         mirror,      gravity 1.5 — reflective, rattling decay
        COMMANDS     escape,      gravity 1.0 — long-distance foraging runner
        agent-context boundary,   gravity 0.5 — marginal / edge ecology

    Args:
        query:      Free-text concept to inject (the spore)
        hub:        CAIRRN hub to route through (default HOME)
        threshold:  Minimum activation to count an edge as lit (default 0.30)

    Returns:
        JSON SporeResult with colonisation_points, activated_edges, anastomoses,
        and the full CAIRRN pipeline run report.
    """
    net = _get_mycelial()
    if net is None:
        return _not_trained_msg()
    try:
        result = net.spore(query=query, hub=hub, threshold=threshold)
        return _fmt(result.to_dict())
    except ValueError as e:
        return _fmt({"error": str(e)})
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def samba_mycelial_trace(
    note: str,
    threshold: float = 0.30,
) -> str:
    """
    Trace currently activated soft edges (hyphae) involving a note.

    Returns all edges where the note appears as source or target and whose
    activation strength is above threshold. Each edge reports:
        resting_score   — Samba GNN semantic similarity (static)
        activation      — current modulated activation (dynamic)
        conductance     — g_ij = σ(κ × score) mycelial flow capacity
        hub / shard     — CAIRRN routing that last activated this edge
        coherence       — CAIRRN coherence score at activation time
        decay_rate      — how fast this edge is fading (hub memory_decay)
        is_active       — whether activation ≥ threshold

    Args:
        note:       Title of the note to trace from (exact or approximate)
        threshold:  Activation floor (default 0.30)

    Returns:
        JSON list of HyphalEdge dicts sorted by activation descending
    """
    net = _get_mycelial()
    if net is None:
        return _not_trained_msg()
    try:
        results = net.trace_hyphae(note_title=note, threshold=threshold)
        if not results:
            return _fmt({"note": note, "message": "No active hyphae found. Run samba_mycelial_spore first."})
        return _fmt({"note": note, "active_hyphae": results, "count": len(results)})
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def samba_mycelial_state(active_only: bool = True) -> str:
    """
    Read the current mycelial activation map — the full live state of the network.

    Returns all tracked soft edges sorted by activation strength, with network
    summary statistics: total hyphae, active vs dormant counts, hub distribution,
    pipeline step counter, and current coherence score.

    Dormant edges (activation below floor) are not deleted — they can be
    reactivated by a future spore injection, just as dormant mycelia revive
    when nutrients return.

    Args:
        active_only:  If True (default), return only active edges (≥ 0.30).
                      Set False to include dormant hyphae as well.

    Returns:
        JSON with network_stats and edges list
    """
    net = _get_mycelial()
    if net is None:
        return _not_trained_msg()
    try:
        stats = net.network_stats()
        edges = net.activation_map(active_only=active_only)
        return _fmt({"network_stats": stats, "edges": edges, "active_only": active_only})
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def samba_mycelial_decay(steps: int = 1) -> str:
    """
    Advance the mycelial network by N dormancy ticks (C-layer of CAIRRN-AWARE).

    Each tick applies every edge's hub memory_decay:
        activation_t+1 = activation_t × decay_rate

    Decay rates by hub:
        HOME         0.98  — slowest fade (mutualistic, persistent)
        MATH         0.95  — moderate exploration fade
        CODE         0.93  — reflective fade
        COMMANDS     0.90  — fast escape-runner fade
        agent-context 0.90 — boundary-layer fade (matches Euler SSM r=0.90)

    Edges that fall below the 0.30 activation floor go dormant. This models
    hyphal thread dormancy — connections that haven't been reinforced by recent
    spore activity gradually lose their conductivity.

    Args:
        steps:  Number of decay ticks to apply (default 1)

    Returns:
        JSON summary: total_edges, active_after_decay, went_dormant per step
    """
    net = _get_mycelial()
    if net is None:
        return _not_trained_msg()
    try:
        results = []
        for i in range(steps):
            tick_result = net.decay_all()
            results.append({f"tick_{i+1}": tick_result})
        return _fmt({"decay_steps": steps, "ticks": results})
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def samba_mycelial_propagate(steps: int = 3) -> str:
    """
    Propagate activation N steps through the mycelial network via passive diffusion.

    Implements the passive flow formula from "Rationale: Mycelial Intelligence in DAWN":
        F_passive_ij = g_ij × (activation_i − activation_j)

    Each step, edges donate activation surplus to adjacent hyphae (edges that
    share a source or target note), weighted by conductance g_ij = σ(κ × score).
    This models nutrients diffusing along fungal threads toward lower-energy zones.

    Use after samba_mycelial_spore to let activation spread from the colonisation
    points outward through the network before reading anastomoses.

    Args:
        steps:  Number of diffusion steps (default 3; each step is one graph pass)

    Returns:
        JSON with before/after active edge counts and newly activated edges
    """
    net = _get_mycelial()
    if net is None:
        return _not_trained_msg()
    try:
        result = net.propagate(steps=steps)
        return _fmt(result)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def samba_mycelial_anastomoses(note: str, hub: str = "HOME", threshold: float = 0.30) -> str:
    """
    Surface latent anastomoses — hyphae that could become explicit wiki-links.

    Anastomoses are mycological junction points where separate hyphal threads
    fuse into one network. In the Obsidian graph, they are semantically justified
    connections that don't yet exist as wiki-links.

    Runs samba_suggest_links and weights each suggestion by the CAIRRN-modulated
    activation potential for the given hub, returning only those whose estimated
    anastomosis_strength exceeds the threshold.

    Args:
        note:       Title of the note to surface anastomoses for
        hub:        CAIRRN hub to use for modulation estimate (default HOME)
        threshold:  Minimum anastomosis_strength to include (default 0.30)

    Returns:
        JSON list of link suggestions with anastomosis_strength field,
        sorted by strength descending
    """
    net = _get_mycelial()
    if net is None:
        return _not_trained_msg()
    try:
        results = net.surface_anastomoses(note_title=note, hub=hub, threshold=threshold)
        if not results:
            return _fmt({
                "note": note,
                "hub": hub,
                "message": "No anastomoses above threshold. Try a lower threshold or a different hub.",
            })
        return _fmt({"note": note, "hub": hub, "threshold": threshold, "anastomoses": results})
    except ValueError as e:
        return _fmt({"error": str(e)})
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def samba_mycelial_apply_anastomoses(
    note: str,
    write_threshold: float = 0.60,
    hub: str = "HOME",
    dry_run: bool = True,
) -> str:
    """
    Write hot anastomoses for a note into the vault as [[wikilinks]].

    This is the growth arm of the CAIRRN-AWARE mycelial cycle:

      spore → activate hyphae → propagate → apply_anastomoses → vault grows

    Anastomoses above `write_threshold` are written to the note's
    "## Related Notes" section using the same atomic write path as all other
    vault modifications. Links already present are never duplicated.

    Runs dry_run=True by default — inspect the suggestions first, then call
    again with dry_run=False to commit to the vault.

    write_threshold vs activation_floor:
        activation_floor (0.30)   — edge is lit and visible in the network
        write_threshold  (0.60)   — edge is strong enough to write into the vault

    Args:
        note:             Source note to grow links from (exact or approximate title).
        write_threshold:  Minimum anastomosis_strength to write (default 0.60).
        hub:              CAIRRN hub for modulation estimate (default HOME).
        dry_run:          If True (default), report what would be written without
                          touching the vault. Set False to write.

    Returns:
        JSON with note, suggestions, links_written, and dry_run flag.
    """
    net = _get_mycelial()
    if net is None:
        return _not_trained_msg()
    try:
        result = net.apply_anastomoses(
            note_title=note,
            write_threshold=write_threshold,
            hub=hub,
            dry_run=dry_run,
        )
        if not result.get("suggestions"):
            return _fmt({
                "note": note,
                "message": (
                    f"No anastomoses above write_threshold={write_threshold}. "
                    "Try samba_mycelial_spore first, or lower the threshold."
                ),
            })
        return _fmt(result)
    except Exception as e:
        return f"Error: {e}"


# ──────────────────────────────────────────────────────────────────────────────
# Live daemon CAIRRN bridge tools (IPC via /tmp state file)
# ──────────────────────────────────────────────────────────────────────────────

_CAIRRN_STATE_FILE = "/tmp/samba_cairrn_state.json"
_CAIRRN_CMD_FILE   = "/tmp/samba_cairrn_cmds.json"


@mcp.tool()
def cairrn_hub_state() -> str:
    """
    Return the live CAIRRN hub state from the running OctopusTracer daemon.

    Reads from the state file broadcast by spawn_tracer.py after each cycle.
    If the daemon is not running, falls back to the in-process CairnBridge
    singleton (useful for interactive testing without the daemon).

    Returns:
        JSON with per-hub state (coherence, z_awareness, activation, shard,
        steps, tau), global coherence, harmonic index, and spawn/z signals.
        Also includes: pid, cycle, n_nodes, ts of the last daemon broadcast.
    """
    if os.path.exists(_CAIRRN_STATE_FILE):
        try:
            with open(_CAIRRN_STATE_FILE) as fh:
                state = json.load(fh)
            state["source"] = "daemon"
            return _fmt(state)
        except Exception as e:
            logger.warning("Could not read CAIRRN state file: %s", e)

    # Fallback: in-process bridge
    bridge = _get_cairrn()
    if bridge is None:
        return _fmt({"error": "No daemon state file and CairnBridge unavailable"})
    return _fmt({
        "source":           "in-process",
        "hubs":             bridge.hub_state(),
        "index":            bridge.index_state(),
        "global_coherence": round(bridge.global_coherence(), 4),
        "global_z":         round(bridge.global_z_awareness(), 4),
        "spawn_signals":    {k: round(v, 4) for k, v in bridge.spawn_signals().items()},
        "z_signals":        {k: round(v, 4) for k, v in bridge.z_awareness_signals().items()},
        "note": "daemon not running — state is from in-process bridge",
    })


@mcp.tool()
def cairrn_inject(hub: str, value: float) -> str:
    """
    Inject an activation directly into a CAIRRN hub on the running daemon.

    Writes a command to the IPC queue file that spawn_tracer.py drains at the
    start of the next cycle. Commands are consumed exactly once (file is deleted
    after draining). Multiple calls before the next cycle accumulate in the queue.

    If the daemon is not running, the injection is applied immediately to the
    in-process CairnBridge singleton.

    Hub names: HOME | MATH | CODE | COMMANDS | agent-context

    Args:
        hub:   CAIRRN hub to inject into (case-insensitive).
        value: Activation level [0, 1] to feed through the hub pipeline.

    Returns:
        JSON confirming the queued injection or the immediate pipeline result.
    """
    import time as _time

    hub = hub.strip()

    # ── If daemon state file is stale (> 5 min), fall through to in-process ──
    daemon_live = False
    if os.path.exists(_CAIRRN_STATE_FILE):
        try:
            age = _time.time() - os.path.getmtime(_CAIRRN_STATE_FILE)
            daemon_live = age < 300
        except OSError:
            pass

    if daemon_live:
        # Queue the command for the daemon to pick up next cycle
        try:
            existing: list = []
            if os.path.exists(_CAIRRN_CMD_FILE):
                with open(_CAIRRN_CMD_FILE) as fh:
                    existing = json.load(fh)
                if not isinstance(existing, list):
                    existing = [existing]
            existing.append({"hub": hub, "value": value})
            tmp = _CAIRRN_CMD_FILE + ".tmp"
            with open(tmp, "w") as fh:
                json.dump(existing, fh)
            os.replace(tmp, _CAIRRN_CMD_FILE)
            return _fmt({
                "status":     "queued",
                "hub":        hub,
                "value":      value,
                "queue_size": len(existing),
                "note":       "Will be applied at the start of the next daemon cycle",
            })
        except Exception as e:
            return _fmt({"error": f"Failed to queue command: {e}"})

    # Fallback: immediate in-process injection
    bridge = _get_cairrn()
    if bridge is None:
        return _fmt({"error": "Daemon not live and CairnBridge unavailable"})
    try:
        result = bridge.step(hub, value)
        return _fmt({
            "status":    "applied",
            "source":    "in-process",
            "hub":       result.hub,
            "modulated": round(result.modulated, 4),
            "shard":     result.shard,
            "coherence": round(result.coherence, 4),
            "z":         round(result.z_awareness, 4),
            "note":      "daemon not live — applied to in-process bridge",
        })
    except Exception as e:
        return f"Error: {e}"


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────

def main():
    global _checkpoint_path, _config_path

    parser = argparse.ArgumentParser(description="Samba GNN MCP Server")
    parser.add_argument("--checkpoint", default=None,
                        help="Path to model checkpoint (auto-detected if not set)")
    parser.add_argument("--config", default=None,
                        help="Path to config.yaml (default: config/config.yaml next to this file)")
    parser.add_argument("--dev", action="store_true",
                        help="Run in dev mode: list tools and exit")
    args = parser.parse_args()

    if args.checkpoint:
        _checkpoint_path = args.checkpoint
    if args.config:
        _config_path = args.config

    if args.dev:
        # Dev mode: print tool manifest and exit
        print("Samba GNN MCP Server — registered tools:")
        for tool in mcp._tool_manager.list_tools():
            print(f"  {tool.name}: {tool.description[:80]}...")
        ckpt = _checkpoint_path or _find_best_checkpoint()
        print(f"\nCheckpoint: {ckpt or 'NOT FOUND (run train.py first)'}")
        return

    # Run as stdio MCP server (Cursor connects via .cursor/mcp.json)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
