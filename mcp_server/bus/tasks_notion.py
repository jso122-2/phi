"""Bus tasks: Notion Reservoir tick (edge writes + score updates).

In-transit accumulation
-----------------------
The lichen model: calcium forms inside the hyphal wall, not at the endpoint.

When the worker picks up a ``notion.tick`` job it scans the jobs directory for
other *queued* ``notion.tick`` jobs that share at least one shard with this one.
Those jobs are absorbed — their shard lists are merged and they are marked
``"batched"`` — so the resulting Notion write is a single fetch-increment-write
for all accumulated activations rather than N separate round-trips.

This makes shard increments commutative and race-free: even if several PSSPPS
queries fired simultaneous ticks for ``dawn-fragments``, only one Notion fetch
occurs and Qe is incremented by the correct combined count.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mcp_server.bus._task_registry import task


# ---------------------------------------------------------------------------
# Batching helpers
# ---------------------------------------------------------------------------

def _scan_queued_notion_ticks(
    current_job_id: str,
    target_shards: set[str],
    jobs_dir: Path,
) -> list[dict[str, Any]]:
    """
    Find other queued ``notion.tick`` jobs that share shards with this one.

    Returns a list of job records that will be absorbed.  Does not modify
    anything — the caller is responsible for marking them batched.
    """
    absorbed: list[dict[str, Any]] = []
    try:
        for p in sorted(jobs_dir.glob("*.json")):
            if p.stem == current_job_id:
                continue
            try:
                rec = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            if rec.get("task") != "notion.tick":
                continue
            if rec.get("status") not in ("queued", "pending"):
                continue
            kwargs = rec.get("kwargs") or {}
            other_shards = {
                s.strip()
                for s in str(kwargs.get("shards", "")).split(",")
                if s.strip()
            }
            if other_shards & target_shards:   # non-empty intersection
                absorbed.append(rec)
    except Exception:
        pass
    return absorbed


def _mark_batched(rec: dict[str, Any], jobs_dir: Path, batch_leader: str) -> None:
    """Mark an absorbed job as batched so it won't be picked up again."""
    try:
        from mcp_server.bus.client import save_job
        rec["status"] = "batched"
        rec["batched_into"] = batch_leader
        save_job(rec)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Bus tasks
# ---------------------------------------------------------------------------

@task("notion.tick")
def notion_tick_task(
    shards: str = "dawn-fragments,schema-fragments,recursive-thought,valence-high,novel-fragments",
    note: str = "",
    dry_run: bool = False,
    _job_id: str = "",
) -> dict[str, Any]:
    """
    Write pure edge activations and update Scores rows in Notion Reservoir.

    Before writing, scans the jobs directory for other queued ``notion.tick``
    jobs targeting overlapping shards.  Absorbed jobs are merged into this
    one and marked ``batched`` so the Notion API receives a single
    fetch-increment-write for the combined activation count.

    Parameters
    ----------
    shards   : comma-separated shard names
    note     : one-line session context embedded in Notion edge Note fields
    dry_run  : compute payload but do not write to Notion API
    _job_id  : injected by the task registry; used to identify this job during
               scan so it is never absorbed into itself
    """
    from mcp_server.bus.runtime import jobs_dir
    from mcp_server.tools.notion_reservoir import notion_reservoir_tick

    target_shards = {s.strip() for s in shards.split(",") if s.strip()}

    # In-transit accumulation: absorb sibling queued ticks
    absorbed: list[dict[str, Any]] = []
    if not dry_run and _job_id:
        jdir = jobs_dir()
        absorbed = _scan_queued_notion_ticks(_job_id, target_shards, jdir)
        for rec in absorbed:
            extra_shards = {
                s.strip()
                for s in str((rec.get("kwargs") or {}).get("shards", "")).split(",")
                if s.strip()
            }
            target_shards |= extra_shards
            _mark_batched(rec, jdir, _job_id)

    merged_shards = ",".join(sorted(target_shards))
    result = notion_reservoir_tick(shards=merged_shards, note=note, dry_run=dry_run)
    result["batched_job_count"] = len(absorbed)
    result["batched_job_ids"] = [r.get("job_id") for r in absorbed]
    return result


@task("notion.state")
def notion_state_task() -> dict[str, Any]:
    """Return the current Notion Reservoir shard registry state."""
    from mcp_server.tools.notion_reservoir import notion_reservoir_state
    return notion_reservoir_state()
