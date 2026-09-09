"""
phi → Notion Reservoir wire.

Writes pure edge activations and updates Scores rows in the Notion Reservoir
whenever a shard fires in a phi session.

Requires NOTION_TOKEN env var (Notion integration secret) for direct API writes.
Without a token the tool returns the computed payload for manual application.

Shard registry is hardcoded from the live Notion workspace (jack dev's Space).

CAIRRN hub → reservoir shard routing
-------------------------------------
CAIRRN hubs (HOME / MATH / CODE / COMMANDS / agent-context) map to reservoir
shards via CAIRRN_HUB_TO_SHARD.  Use hub_to_shard() for safe lookup with None
fallback.  The old HUB_TO_SHARD (DAWN/SCHEMA/RECUR keys) is removed.
"""
from __future__ import annotations

import json
import math
import os
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

EDGES_DB_ID = "1c53019e-6d7d-44b9-9bb7-540bad2ce732"
SCORES_COLLECTION = "54c008d6-e791-4f26-ab48-11dfe7c8e796"

# CAIRRN hub → reservoir shard routing.
# Keys are the live harmonic-index hub names (HOME / MATH / CODE / COMMANDS /
# agent-context).  Values are SHARD_REGISTRY keys.
#
# Rationale for the mapping:
#   HOME         → dawn-fragments     (foundation / structural scaffolding)
#   MATH         → recursive-thought  (formal / recursive computation)
#   CODE         → novel-fragments    (synthesis / generative output)
#   COMMANDS     → valence-high       (directive / high-charge actions)
#   agent-context → schema-fragments  (semantic / narrative context)
CAIRRN_HUB_TO_SHARD: dict[str, str] = {
    "HOME":          "dawn-fragments",
    "MATH":          "recursive-thought",
    "CODE":          "novel-fragments",
    "COMMANDS":      "valence-high",
    "agent-context": "schema-fragments",
}

# Inverse: shard name → CAIRRN hub name (for hub pulsing after traversal).
SHARD_TO_CAIRRN_HUB: dict[str, str] = {v: k for k, v in CAIRRN_HUB_TO_SHARD.items()}

# Prompt register → Edges DB Axis value.
REGISTER_TO_AXIS: dict[str, str] = {
    "architectural": "structural",
    "charged":       "valence",
    "recursive":     "recursive",
    "narrative":     "semantic",
    # pass-through aliases so callers can use axis names directly
    "semantic":      "semantic",
    "structural":    "structural",
    "valence":       "valence",
    "biographical":  "biographical",
}

# Weight → numeric priority for sorting.
_WEIGHT_SCORE: dict[str, int] = {"high": 3, "medium": 2, "low": 1}


def hub_to_shard(hub_name: str) -> str | None:
    """Translate a CAIRRN hub name to its reservoir shard name, or None if unmapped."""
    return CAIRRN_HUB_TO_SHARD.get(hub_name)


def _to_dashed_uuid(hex_id: str) -> str:
    """Convert a 32-char hex shard_page_id to dashed-UUID form (Notion API format)."""
    h = hex_id.replace("-", "")
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:]}"


# Reverse lookup: dashed UUID (from Notion API relation responses) → shard name.
_PAGE_ID_TO_SHARD: dict[str, str] = {
    _to_dashed_uuid(reg["shard_page_id"]): name
    for name, reg in SHARD_REGISTRY.items()
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
# Notion API helpers
# ---------------------------------------------------------------------------

def _notion_request(
    method: str,
    path: str,
    body: dict | None = None,
    token: str | None = None,
) -> dict:
    token = token or os.environ.get("NOTION_TOKEN", "")
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


def _fetch_current_scores(page_id: str, token: str) -> dict[str, Any]:
    """
    Fetch numeric score properties AND the Classification select from a Notion
    Scores page.

    Returns a dict with ``float`` values for numeric properties and ``str``
    values for select properties (e.g. ``{"Qe": 5.0, "Classification":
    "load-bearing", ...}``).  Returns an empty dict on any error so callers
    can safely fall back to defaults.
    """
    try:
        resp = _notion_request("GET", f"pages/{page_id}", token=token)
        props = resp.get("properties", {})
        result: dict[str, Any] = {}
        for key, val in props.items():
            if not isinstance(val, dict):
                continue
            if val.get("type") == "number":
                num = val.get("number")
                if isinstance(num, (int, float)):
                    result[key] = float(num)
            elif val.get("type") == "select":
                sel = val.get("select") or {}
                name = sel.get("name")
                if name:
                    result[key] = name
        return result
    except Exception:
        return {}


def _query_database(db_id: str, body: dict, token: str) -> dict:
    """POST /databases/{db_id}/query — return the raw Notion API response."""
    return _notion_request("POST", f"databases/{db_id}/query", body, token)


# ---------------------------------------------------------------------------
# Traversal — hyphae layer (Step 3 of the autonomous-index protocol)
# ---------------------------------------------------------------------------

def notion_traverse(
    shard: str,
    register: str = "",
    top_n: int = 2,
    token: str | None = None,
) -> dict[str, Any]:
    """
    Traverse adjacent edges from *shard* in the Notion Edges DB.

    Implements Step 3 of the Autonomous Index protocol:
    - Queries Edges DB for Type=adjacent rows where Shard A or Shard B
      contains the activated shard's page ID.
    - Scores each edge: F_edge = Ns1_A × Ns1_B / max(d², 0.01), then
      sorts by (axis_match DESC, F_edge DESC, weight_score DESC, d ASC).
    - Returns top_n unique connected shards with their current Classifications
      fetched from the Scores DB.

    Parameters
    ----------
    shard    : shard name from SHARD_REGISTRY
    register : prompt register (architectural / charged / recursive / narrative)
               used to prefer axis-matching edges
    top_n    : maximum adjacent shards to return (default 2)
    token    : Notion integration token; falls back to NOTION_TOKEN env var
    """
    reg = SHARD_REGISTRY.get(shard)
    if reg is None:
        return {"shard": shard, "error": f"unknown shard: {shard}", "adjacent": []}

    token_resolved = token or os.environ.get("NOTION_TOKEN", "")
    if not token_resolved:
        return {"shard": shard, "error": "NOTION_TOKEN not set", "adjacent": []}

    shard_uuid = _to_dashed_uuid(reg["shard_page_id"])
    preferred_axis = REGISTER_TO_AXIS.get(register, "")

    # --- query Edges DB --------------------------------------------------
    try:
        resp = _query_database(
            EDGES_DB_ID,
            {
                "filter": {
                    "and": [
                        {"property": "Type", "select": {"equals": "adjacent"}},
                        {
                            "or": [
                                {"property": "Shard A", "relation": {"contains": shard_uuid}},
                                {"property": "Shard B", "relation": {"contains": shard_uuid}},
                            ]
                        },
                    ]
                },
                "page_size": 30,
            },
            token_resolved,
        )
    except Exception as exc:
        return {"shard": shard, "error": str(exc), "adjacent": []}

    results = resp.get("results", [])

    # --- parse and score each edge ----------------------------------------
    edges: list[dict[str, Any]] = []
    for page in results:
        props = page.get("properties", {})

        weight = (props.get("Weight", {}).get("select") or {}).get("name", "low")
        axis   = (props.get("Axis",   {}).get("select") or {}).get("name", "")

        d_raw = props.get("d", {}).get("number")
        d = float(d_raw) if d_raw is not None else 2.0
        d = max(d, 0.01)

        ns1_a = float(props.get("Ns1_A", {}).get("number") or 0.0)
        ns1_b = float(props.get("Ns1_B", {}).get("number") or 0.0)
        f_edge = ns1_a * ns1_b / (d ** 2)

        title_parts = props.get("Label", {}).get("title") or []
        label = "".join(p.get("plain_text", "") for p in title_parts)

        note_parts = props.get("Note", {}).get("rich_text") or []
        note = "".join(p.get("plain_text", "") for p in note_parts)[:200]

        # Identify connected shards (opposite side, excluding input shard)
        shard_a_rel = props.get("Shard A", {}).get("relation") or []
        shard_b_rel = props.get("Shard B", {}).get("relation") or []
        connected: list[str] = []
        for rel_entry in shard_a_rel + shard_b_rel:
            pid = rel_entry.get("id", "")
            if pid == shard_uuid:
                continue
            name = _PAGE_ID_TO_SHARD.get(pid)
            if name and name not in connected:
                connected.append(name)

        if not connected:
            continue

        axis_match = 1 if (preferred_axis and axis == preferred_axis) else 0
        edges.append({
            "label":        label,
            "weight":       weight,
            "weight_score": _WEIGHT_SCORE.get(weight, 1),
            "axis":         axis,
            "axis_match":   axis_match,
            "d":            d,
            "f_edge":       round(f_edge, 6),
            "note":         note,
            "connected":    connected,
        })

    # Sort: axis_match desc, f_edge desc, weight_score desc, d asc
    edges.sort(key=lambda e: (-e["axis_match"], -e["f_edge"], -e["weight_score"], e["d"]))

    # Collect top_n unique connected shards in priority order
    seen: set[str] = set()
    top_shards: list[dict[str, Any]] = []
    for edge in edges:
        for adj_name in edge["connected"]:
            if adj_name in seen:
                continue
            seen.add(adj_name)
            entry: dict[str, Any] = {
                "shard":       adj_name,
                "via_edge":    edge["label"],
                "weight":      edge["weight"],
                "axis":        edge["axis"],
                "axis_match":  edge["axis_match"],
                "d":           edge["d"],
                "f_edge":      edge["f_edge"],
                "note":        edge["note"],
                "hub":         SHARD_TO_CAIRRN_HUB.get(adj_name, ""),
                # Classification fetched below
                "classification": "unknown",
                "ns1": 0.0,
                "ns2": 0.0,
            }
            adj_reg = SHARD_REGISTRY.get(adj_name)
            if adj_reg:
                scores = _fetch_current_scores(adj_reg["score_page_id"], token_resolved)
                entry["classification"] = scores.get("Classification", "unknown")
                entry["ns1"] = float(scores.get("Ns1", 0.0))
                entry["ns2"] = float(scores.get("Ns2", 0.0))
            top_shards.append(entry)
            if len(top_shards) >= top_n:
                break
        if len(top_shards) >= top_n:
            break

    return {
        "shard":          shard,
        "register":       register,
        "preferred_axis": preferred_axis,
        "n_edges_found":  len(edges),
        "adjacent":       top_shards,
    }


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

    token_resolved = token or os.environ.get("NOTION_TOKEN", "")
    can_write = bool(token_resolved) and not dry_run

    for name in activated_shards:
        reg = SHARD_REGISTRY.get(name)
        if reg is None:
            results["errors"].append(f"unknown shard: {name}")
            continue

        # Embed session token if available — makes the edge traceable in Notion
        try:
            from mcp_server._gate import SESSION_TOKEN as _TOKEN
            _session_ref = f" [{_TOKEN}]" if _TOKEN else ""
        except Exception:
            _session_ref = ""

        # -- Edge write --
        edge_note = session_note or f"phi tick — {name} activated"
        edge_label = f"{name} :: activation :: {ts}{_session_ref}"
        edge_payload = {
            "parent": {"database_id": EDGES_DB_ID},
            "properties": {
                "Label": {
                    "title": [{"text": {"content": edge_label}}]
                },
                "Type": {"select": {"name": "pure"}},
                "Axis": {"select": {"name": reg["axis"]}},
                "Weight": {"select": {"name": "high"}},
                "Direction": {"select": {"name": "A->B"}},
                "d": {"number": 1},
                "Ns1_A": {"number": 0},
                "Ns1_B": {"number": 0},
                "Note": {"rich_text": [{"text": {"content": edge_note}}]},
            },
        }

        # -- Score update --
        # Fetch the current Qe / Ta from Notion so we increment correctly.
        # Falls back to 0 when there is no token (dry-run / no-token path).
        current = _fetch_current_scores(reg["score_page_id"], token_resolved) if can_write else {}
        qe = int(current.get("Qe", 0)) + 1
        ta = int(current.get("Ta", 0)) + 1
        qe_adj = int(current.get("Qe_Adj", 0))
        scores = compute_scores(
            qe=qe, ta=ta, to_a=to_a,
            si=reg["Si"], et=reg["Et"], ss=reg["Ss"], idx=reg["Idx"],
            qe_adj=qe_adj,
        )

        score_patch = {
            "Qe": {"number": qe},
            "Ta": {"number": ta},
            "To_A": {"number": to_a},
            "Ec": {"number": scores["Ec"]},
            "Ns1": {"number": scores["Ns1"]},
            "Ns2": {"number": scores["Ns2"]},
            "Ns3": {"number": scores["Ns3"]},
            "Classification": {"select": {"name": scores["Classification"]}},
        }

        results["edges_written"].append({
            "shard": name,
            "label": edge_label,
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


def notion_reservoir_traverse(
    shards: str = "dawn-fragments",
    register: str = "",
    top_n: int = 2,
) -> dict[str, Any]:
    """
    MCP tool: traverse adjacent edges for one or more comma-separated shards.

    Returns traversal context: top_n adjacent shards per seed shard, ordered
    by axis match → F_edge → weight → d.  Classifications are fetched live
    from the Scores DB so the routing decision reflects the current graph heat.

    shards   : comma-separated shard names (e.g. "dawn-fragments,schema-fragments")
    register : prompt register for axis preference
               (architectural / charged / recursive / narrative)
    top_n    : adjacent shards to return per seed (default 2)
    """
    shard_list = [s.strip() for s in shards.split(",") if s.strip()]
    results: list[dict[str, Any]] = []
    seen_adjacent: set[str] = set()
    for shard in shard_list:
        result = notion_traverse(shard=shard, register=register, top_n=top_n)
        # Deduplicate adjacent across multiple seed shards
        filtered = [
            a for a in result.get("adjacent", [])
            if a["shard"] not in seen_adjacent and a["shard"] not in shard_list
        ]
        for a in filtered:
            seen_adjacent.add(a["shard"])
        result["adjacent"] = filtered
        results.append(result)
    return {
        "seeds": shard_list,
        "register": register,
        "traversals": results,
        "token_configured": bool(os.environ.get("NOTION_TOKEN")),
    }


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
        "cairrn_hub_to_shard": CAIRRN_HUB_TO_SHARD,
        "shard_to_cairrn_hub": SHARD_TO_CAIRRN_HUB,
        "register_to_axis": REGISTER_TO_AXIS,
        "token_configured": bool(os.environ.get("NOTION_TOKEN")),
    }
