"""Apply MCP-local side effects after a worker result lands (harmonic index, vault hub)."""
from __future__ import annotations

from typing import Any

from mcp_server.bus.client import save_job


def _notion_tick_async(shards: list[str], note: str = "") -> None:
    """
    Fire a Notion Reservoir tick for the given shards via the singleton bus.

    Fire-and-forget: submits the bus task and returns immediately.  The tick
    increments Qe/Ta in Notion so the Reservoir's stateful identity scores
    (Ns1, Ns2, Classification) update correctly across sessions.

    The SESSION_TOKEN (stamped at gate-open) is embedded in the note so every
    Notion edge is traceable back to the session that generated it.  This is
    the "shallow root / calcium identity" linkage — the Reservoir's edge graph
    becomes a temporal map of which cognitive domains fired in which sessions.

    Called from _apply() when a PSSPPS result carries notion_tick_shards.
    Silent on any bus/token failure — the MCP session must not block on Notion.
    """
    try:
        from mcp_server.bus.client import get_client, worker_alive
        from mcp_server._gate import SESSION_TOKEN

        client = get_client()
        if client is None or not worker_alive():
            return

        # Prefix note with session token for Notion edge traceability
        token_prefix = f"[{SESSION_TOKEN}] " if SESSION_TOKEN else ""
        full_note = f"{token_prefix}{note[:100]}" if note else (token_prefix.rstrip())

        client.submit("notion.tick", {
            "shards":  ",".join(shards),
            "note":    full_note[:120],
            "dry_run": False,
        })
    except Exception:
        pass


def apply_side_effects(record: dict[str, Any]) -> dict[str, Any]:
    if record.get("status") != "done":
        return record
    if record.get("side_effects_applied"):
        return record
    result = record.get("result")
    if not isinstance(result, dict):
        record["side_effects_applied"] = True
        save_job(record)
        return record

    try:
        _apply(result)
    except Exception:
        pass
    record["side_effects_applied"] = True
    save_job(record)
    return record


def _ledger_record(tool: str) -> None:
    """Record current harmonic state into the session ledger (silent on failure)."""
    try:
        from mcp_server._state import _harmonic_index, _session_ledger
        if _harmonic_index is None or not _session_ledger.is_open():
            return
        shards = [float(s.activation) for s in _harmonic_index.shards]
        step = int(getattr(_harmonic_index, "_step_count", 0))
        _session_ledger.record(tool=tool, snapshot=shards, step_count=step)
    except Exception:
        pass


def _apply(result: dict[str, Any]) -> None:
    from mcp_server._state import _harmonic_index, _temporal_index, _vault_hub
    from sims.harmonic import HUB_SHARD_MAP
    from sims.temporal import CAIRRN_HUBS

    if _harmonic_index is None:
        return

    pulse_home = result.get("pulse_home")
    if pulse_home:
        _harmonic_index.inject_from_hub("HOME", value=float(pulse_home))
        _harmonic_index.propagate(steps=2, mode="local")
        _ledger_record("side_effect:pulse_home")

    pulse_hubs = result.get("pulse_hubs") or result.get("hub_distribution")
    scale = float(result.get("pulse_scale") or 0.10)
    if isinstance(pulse_hubs, dict):
        for hub_name, count in pulse_hubs.items():
            if hub_name not in HUB_SHARD_MAP:
                continue
            value = min(int(count) * scale, 2.0)
            if value > 0:
                _harmonic_index.inject_from_hub(hub_name, value=value)
        if pulse_hubs:
            _harmonic_index.propagate(steps=5, mode="local")
            _ledger_record("side_effect:pulse_hubs")

    if result.get("touch_commit"):
        hub_name = result.get("hub_name")
        if hub_name in HUB_SHARD_MAP:
            _harmonic_index.inject_from_hub(hub_name, value=0.15)
        _harmonic_index.propagate(steps=3, mode="local")
        _ledger_record("side_effect:touch_commit")
        if hub_name in CAIRRN_HUBS and _temporal_index is not None:
            _temporal_index.record(hub_name, value=0.15)
        try:
            from graph.tracker import sync as _graph_track_sync
            result["git_track"] = _graph_track_sync()
        except Exception as exc:
            result["git_track"] = {"error": str(exc)}

    fusion = result.get("topology_fusion")
    if isinstance(fusion, dict) and fusion.get("apply"):
        from graph.topology_index import apply_fusion
        result["fusion_applied"] = apply_fusion(_harmonic_index, fusion)
        _ledger_record("side_effect:topology_fusion")
        try:
            from mcp_server._state import save_harmonic_snapshot
            save_harmonic_snapshot()
        except Exception:
            pass
        # Optional CAIRRN topology overlay — only when explicitly requested.
        if fusion.get("apply_cairrn"):
            cairrn_snap = fusion.get("cairrn_snapshot")
            if isinstance(cairrn_snap, dict) and cairrn_snap:
                try:
                    from engine.bridge_factory import make_bridge
                    bridge = make_bridge(_harmonic_index)
                    hub_activations = bridge.ingest_topology({"graph_snapshot": cairrn_snap})
                    result["cairrn_overlay"] = {
                        "applied": True,
                        "n_nodes": len(cairrn_snap),
                        "hub_activations": {
                            h: [round(v, 4) for v in vals]
                            for h, vals in hub_activations.items()
                        },
                    }
                except Exception as exc:
                    result["cairrn_overlay"] = {"applied": False, "error": str(exc)}

    # Automatic incremental topology sync on vault-write operations.
    # Fires on every session commit and on graph_link runs that modified at
    # least one node — bypassed if graph_topo_hubs already ran a full fusion.
    _needs_incremental = (
        fusion is None  # no explicit full fusion in this result
        and (
            result.get("touch_commit")
            or (
                result.get("n_nodes_modified") is not None
                and int(result.get("n_nodes_modified") or 0) > 0
            )
        )
    )
    if _needs_incremental:
        try:
            from graph.topology_index import incremental_fusion
            topo_delta = incremental_fusion(_harmonic_index)
            result["topology_delta"] = topo_delta
            if not topo_delta.get("skipped"):
                _ledger_record("side_effect:incremental_fusion")
                from mcp_server._state import save_harmonic_snapshot
                save_harmonic_snapshot()
        except Exception:
            pass

    if result.get("touch_harmonic"):
        _vault_hub.push_all(harmonic=_harmonic_index.state())

    sim_tool = result.get("vault_sim_tool")
    sim = result.get("vault_sim")
    if sim_tool and isinstance(sim, dict):
        _vault_hub.push_all(
            sim_tool=sim_tool,
            sim_result=sim,
            harmonic=_harmonic_index.state(),
        )
    elif pulse_hubs or pulse_home or result.get("touch_commit"):
        _vault_hub.push_all(harmonic=_harmonic_index.state())

    # Notion Reservoir tick — fired when PSSPPS retrieval is useful.
    # Uses the singleton bus so the write is async and never blocks tool returns.
    notion_shards = result.get("notion_tick_shards")
    if notion_shards and isinstance(notion_shards, list) and len(notion_shards) > 0:
        _notion_tick_async(notion_shards, result.get("notion_tick_note", ""))
