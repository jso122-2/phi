"""
mcp_server.tools.notion — sync_notion MCP tool.

Exposes the Notion → Obsidian vault sync pipeline as an agent-callable
MCP tool.  The tool:

  1. Validates credentials (NOTION_API_TOKEN env var).
  2. Delegates to graph.notion_ingestion.run_notion_sync().
  3. Returns a structured result the agent can act on.
  4. Records "sync_notion" in the session CallLedger so the sequence
     enforcer can gate graph_commit on sync completion.

The sequence_hook plugin adds a rule::

    graph_commit requires [sync_notion]
    (only active once sync_notion has been called this session)

Credentials
-----------
Set ``NOTION_API_TOKEN`` in Cursor Dashboard → Cloud Agents → Secrets.
"""
from __future__ import annotations

import os
from typing import Any

from mcp_server._gate import requires_init
from mcp_server._state import mcp


@mcp.tool()
@requires_init
def sync_notion(
    max_pages:     int = 0,
    fetch_timeout: int = 30,
) -> dict[str, Any]:
    """
    Sync the Notion workspace (reservoir) into the Obsidian vault (graph).

    Fetches all pages and database pages accessible to the NOTION_API_TOKEN
    integration, converts them to Obsidian-format markdown, runs the
    IngestionPipeline to embed + cross-link them, and writes the results
    under ``<vault>/notion/``.

    After this tool returns, the Notion nodes are available in the vault
    and can be committed to the harmonic index with graph_commit.

    Parameters
    ----------
    max_pages       Safety cap on total Notion pages to fetch per run.
                    0 (default) means fetch everything accessible.
    fetch_timeout   HTTP timeout in seconds for each Notion API request.

    Returns
    -------
    dict with keys:
        ok            True if no critical errors occurred.
        n_pages       Number of Notion pages fetched.
        n_databases   Number of Notion databases scanned.
        n_written     Vault .md files written this run.
        n_skipped     Docs that were duplicate or empty.
        elapsed_s     Wall time of the sync run.
        errors        List of per-page error strings (empty on full success).
        manifest      Subset of IngestionManifest (n_written, hub_counts).
    """
    token = os.environ.get("NOTION_API_TOKEN", "")
    if not token:
        return {
            "ok":           False,
            "error":        (
                "NOTION_API_TOKEN is not set. "
                "Add it in Cursor Dashboard → Cloud Agents → Secrets."
            ),
            "n_pages":      0,
            "n_databases":  0,
            "n_written":    0,
            "n_skipped":    0,
            "elapsed_s":    0.0,
            "errors":       [],
            "manifest":     None,
        }

    try:
        from graph.notion_ingestion import run_notion_sync, NotionAuthError
        result = run_notion_sync(
            token         = token,
            max_pages     = max_pages,
            fetch_timeout = fetch_timeout,
        )
        return {
            "ok":           len(result.errors) == 0,
            "n_pages":      result.n_pages,
            "n_databases":  result.n_databases,
            "n_written":    result.n_written,
            "n_skipped":    result.n_skipped,
            "elapsed_s":    result.elapsed_s,
            "errors":       result.errors[:20],  # cap to avoid huge payloads
            "manifest":     result.to_dict().get("manifest"),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok":          False,
            "error":       str(exc),
            "n_pages":     0,
            "n_databases": 0,
            "n_written":   0,
            "n_skipped":   0,
            "elapsed_s":   0.0,
            "errors":      [str(exc)],
            "manifest":    None,
        }
