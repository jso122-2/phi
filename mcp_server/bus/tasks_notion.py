"""Bus tasks: Notion Reservoir tick (edge writes + score updates)."""
from __future__ import annotations

from typing import Any

from mcp_server.bus._task_registry import task


@task("notion.tick")
def notion_tick_task(
    shards: str = "dawn-fragments,schema-fragments,recursive-thought,valence-high,novel-fragments",
    note: str = "",
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Write pure edge activations and update Scores rows in Notion Reservoir.

    shards: comma-separated list of activated shard names
    note: one-line session context for edge Note fields
    dry_run: compute payload but do not write to Notion API
    """
    from mcp_server.tools.notion_reservoir import notion_reservoir_tick
    return notion_reservoir_tick(shards=shards, note=note, dry_run=dry_run)


@task("notion.state")
def notion_state_task() -> dict[str, Any]:
    """Return the current Notion Reservoir shard registry state."""
    from mcp_server.tools.notion_reservoir import notion_reservoir_state
    return notion_reservoir_state()
