"""
phi → Notion Reservoir wire.

Writes pure edge activations and updates Scores rows in the Notion Reservoir
whenever a shard fires in a phi session.

Requires NOTION_TOKEN env var (Notion integration secret) for direct API writes.
Without a token the tool returns the computed payload for manual application.

Shard registry is hardcoded from the live Notion workspace (jack dev's Space).
"""
from __future__ import annotations

import json
import math
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

# ---------------------------------------------------------------------------
# Shard registry — sourced from Notion workspace
# ---------------------------------------------------------------------------

# Maps shard name → {score_page_id, shard_page_id, Si, Et, Ss, Idx, register, axis}
SHARD_REGISTRY: dict[str, dict[str, Any]] = {
    "dawn-fragments": {
        "score_page_id": "3ce350886c9d81c29c69ec34b5237951",
        "shard_page_id": "3ce350886c9d813291a2dfb80dccafb9",
        "Si": 1, "Et": 3, "Ss": 1, "Idx": 7,
        "register": "architectural", "axis": "structural",
    },
    "schema-fragments": {
        "score_page_id": "3ce350886c9d812eb8d9c1964fe6daf7",
        "shard_page_id": "3ce350886c9d8163b25ee5b1122c3cb5",
        "Si": 1, "Et": 3, "Ss": 1, "Idx": 7,
        "register": "narrative", "axis": "semantic",
    },
    "recursive-thought": {
        "score_page_id": "3ce350886c9d8167bacfc20a8f8b559a",
        "shard_page_id": "3ce350886c9d81ddaac8d07105affc0e",
        "Si": 1, "Et": 3, "Ss": 1, "Idx": 4,
        "register": "recursive", "axis": "recursive",
    },
    "valence-high": {
        "score_page_id": "3ce350886c9d810e8b2ae95333841c4d",
        "shard_page_id": "3ce350886c9d8106a752f73ffc14e47a",
        "Si": 1, "Et": 3, "Ss": 1, "Idx": 6,
        "register": "charged", "axis": "valence",
    },
    "novel-fragments": {
        "score_page_id": "3ce350886c9d81128180fd1faad1f7d5",
        "shard_page_id": "3ce350886c9d81d296a4fcfa47b79093",
        "Si": 1, "Et": 3, "Ss": 1, "Idx": 3,
        "register": "narrative", "axis": "semantic",
    },
}

EDGES_DB_ID = "82ab8055-ca05-49ef-a4ae-b176641e78fe"
SCORES_COLLECTION = "54c008d6-e791-4f26-ab48-11dfe7c8e796"

# Harmonic index → shard name routing (which phi hub → which Notion shard)
HUB_TO_SHARD: dict[str, str] = {
    "DAWN":      "dawn-fragments",
    "SCHEMA":    "schema-fragments",
    "RECUR":     "recursive-thought",
    "VALENCE":   "valence-high",
    "NOVEL":     "novel-fragments",
}


# ---------------------------------------------------------------------------
# Score computation
# ---------------------------------------------------------------------------

def _classify(ns1: float, ns2: float, ns3: float, qe: int, qe_adj: int) -> str:
    if ns1 > 10 and ns2 < 0:
        return "load-bearing"
    if ns2 > 0.5:
        return "informationally-live"
    if ns3 > 3:
        return "access-outlier"
    if ns2 < -5:
        return "drain-candidate"
    if qe < 2 and qe_adj > 3:
        return "cold-annotated"
    return "drain-candidate"


def compute_scores(
    qe: int, ta: int, to_a: int,
    si: float, et: float, ss: float, idx: float,
    qe_adj: int = 0,
) -> dict[str, float | str]:
    ec  = qe * si
    ns1 = idx * ec
    ns2 = abs(ec / et) - math.exp(ss) if et else -math.exp(ss)
    ns3 = abs(ta - to_a) / max(ss, 0.01)
    cls = _classify(ns1, ns2, ns3, qe, qe_adj)
    return {
        "Ec": round(ec, 4),
        "Ns1": round(ns1, 4),
        "Ns2": round(ns2, 4),
        "Ns3": round(ns3, 4),
        "Classification": cls,
    }


# ---------------------------------------------------------------------------
# Notion API helper
# ---------------------------------------------------------------------------

def _notion_request(
    method: str,
    path: str,
    body: dict | None = None,
    token: str | None = None,
) -> dict:
    token = token or os.environ.get("NOTION_TOKEN") or os.environ.get("notion", "")
    if not token:
        raise RuntimeError("NOTION_TOKEN not set")
    url = f"https://api.notion.com/v1/{path.lstrip('/')}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


# ---------------------------------------------------------------------------
# Core tick function
# ---------------------------------------------------------------------------

def notion_tick(
    activated_shards: list[str],
    session_note: str = "",
    token: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Fire a tick for the given activated shards.

    activated_shards: list of shard names from SHARD_REGISTRY
    session_note: one-line context for the edge Note field
    token: Notion integration token (falls back to NOTION_TOKEN env var)
    dry_run: compute and return payload without writing to Notion
    """
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    to_a = len(activated_shards)  # global sum after this tick
    results: dict[str, Any] = {
        "ts": ts,
        "activated": activated_shards,
        "dry_run": dry_run,
        "edges_written": [],
        "scores_updated": [],
        "errors": [],
    }

    token_resolved = token or os.environ.get("NOTION_TOKEN") or os.environ.get("notion", "")
    can_write = bool(token_resolved) and not dry_run

    for name in activated_shards:
        reg = SHARD_REGISTRY.get(name)
        if reg is None:
            results["errors"].append(f"unknown shard: {name}")
            continue

        # -- Edge write --
        edge_payload = {
            "parent": {"database_id": EDGES_DB_ID},
            "properties": {
                "Label": {
                    "title": [{"text": {"content": f"{name} :: activation :: {ts}"}}]
                },
                "Type": {"select": {"name": "pure"}},
                "Axis": {"select": {"name": reg["axis"]}},
                "Weight": {"select": {"name": "high"}},
                "Direction": {"select": {"name": "A->B"}},
                "d": {"number": 1},
                "Ns1_A": {"number": 0},
                "Ns1_B": {"number": 0},
                "Note": {"rich_text": [{"text": {"content": session_note or f"phi tick — {name} activated"}}]},
            },
        }

        # -- Score update --
        qe = 1  # incremental; caller should fetch current and add
        scores = compute_scores(
            qe=qe, ta=1, to_a=to_a,
            si=reg["Si"], et=reg["Et"], ss=reg["Ss"], idx=reg["Idx"],
        )

        score_patch = {
            "Qe": {"number": qe},
            "Ta": {"number": 1},
            "To_A": {"number": to_a},
            "Ec": {"number": scores["Ec"]},
            "Ns1": {"number": scores["Ns1"]},
            "Ns2": {"number": scores["Ns2"]},
            "Ns3": {"number": scores["Ns3"]},
            "Classification": {"select": {"name": scores["Classification"]}},
        }

        results["edges_written"].append({
            "shard": name,
            "label": f"{name} :: activation :: {ts}",
            "payload": edge_payload,
        })
        results["scores_updated"].append({
            "shard": name,
            "page_id": reg["score_page_id"],
            "scores": scores,
            "patch": score_patch,
        })

        if can_write:
            try:
                _notion_request("POST", "pages", edge_payload, token_resolved)
            except Exception as e:
                results["errors"].append(f"edge write {name}: {e}")
            try:
                _notion_request(
                    "PATCH",
                    f"pages/{reg['score_page_id']}",
                    {"properties": score_patch},
                    token_resolved,
                )
            except Exception as e:
                results["errors"].append(f"score update {name}: {e}")

    results["write_mode"] = "live" if can_write else ("dry-run" if dry_run else "no-token")
    return results


# ---------------------------------------------------------------------------
# MCP tool entry points
# ---------------------------------------------------------------------------

def notion_reservoir_tick(
    shards: str = "dawn-fragments,schema-fragments,recursive-thought,valence-high,novel-fragments",
    note: str = "",
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    MCP tool: fire a Notion Reservoir tick for the given comma-separated shard list.

    shards: comma-separated shard names (default: all 5)
    note: one-line session context appended to edge Note
    dry_run: if true, compute but do not write
    """
    shard_list = [s.strip() for s in shards.split(",") if s.strip()]
    result = notion_tick(activated_shards=shard_list, session_note=note, dry_run=dry_run)
    return result


def notion_reservoir_state() -> dict[str, Any]:
    """
    MCP tool: return the current registry state (no Notion API call required).
    """
    return {
        "shards": {
            name: {k: v for k, v in reg.items() if k not in ("score_page_id", "shard_page_id")}
            for name, reg in SHARD_REGISTRY.items()
        },
        "edges_db_id": EDGES_DB_ID,
        "scores_collection": SCORES_COLLECTION,
        "hub_to_shard_map": HUB_TO_SHARD,
        "token_configured": bool(os.environ.get("NOTION_TOKEN") or os.environ.get("notion")),
    }
