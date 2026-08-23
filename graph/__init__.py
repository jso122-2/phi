"""
graph — autonomous Obsidian vault maintenance worker.

Operations: clean, link, nest, commit, topo_hubs, track, annotate.

The Obsidian vault IS the hub.  Sessions are nodes.  The harmonic index is
the memory.  Session push is graph_commit; code push is git to .hub.git.
Agent commentary is graph_annotate — first-class vault nodes in sessions/comments/.

SQL layer (vault-only phase)
-----------------------------
graph.store  — VaultStore: account-scoped SQLite (nodes, edges, session_meta,
               usage_events).  SQL is source-of-truth for sessions; .md is
               the Obsidian facade.  Station notes are mirrored on demand.
graph.migrate — run_migrate(): bootstrap SQL from existing .md vault.
"""

from graph.worker import (
    CleanReport,
    LinkReport,
    run_clean,
    run_link,
    run_nest,
    run_topo_hubs,
)
from graph.logger import log_session
from graph.node import (
    COMMENTS_DIR,
    write_comment_node,
    write_live_context,
)
from graph.topology_index import apply_fusion, fusion_from_report, incremental_fusion
from graph.store import VaultStore, get_store, reset_store
from graph.migrate import run_migrate
from graph.projector import project, project_all, projection_summary, ProjectionResult

__all__ = [
    "run_clean",
    "run_link",
    "run_nest",
    "run_topo_hubs",
    "log_session",
    "CleanReport",
    "LinkReport",
    "apply_fusion",
    "fusion_from_report",
    "incremental_fusion",
    # comment / live-context writers
    "write_comment_node",
    "write_live_context",
    "COMMENTS_DIR",
    # SQL store
    "VaultStore",
    "get_store",
    "reset_store",
    "run_migrate",
    # Projector — re-materialise .md from SQL
    "project",
    "project_all",
    "projection_summary",
    "ProjectionResult",
]
