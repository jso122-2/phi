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

from workers.cairrn import f_crystallisation, f_edge_volatility, f_shimmer_decay, f_shimmer_base

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

# Per-shard Si memory for the f_crystallisation gate.
# Keyed by shard_page_id → last Si value written to Notion.
_r_node_prev: dict[str, float] = {}

# Ring volatility gate (f_edge_volatility).
# Suppresses notion.tick writes when the harmonic ring is too noisy.
V_EDGE_SUPPRESS_THRESHOLD: float = 2.0   # tune as needed — ring is volatile above this
_shard_activations_prev: list[float] = []  # activation vector from the last non-suppressed tick

# f_shimmer_decay tuning constants (Layer 6 — D(t) hysteresis floor on Ns2).
# shimmer_t = A · exp(−λ · t) + p · φ_hysteresis
SHIMMER_LAM: float = 0.1   # decay rate λ — controls how fast the floor drops with Et
SHIMMER_PHI: float = 0.2   # hysteresis factor φ — scales the pressure floor
SHIMMER_EPS: float = 0.05  # epsilon — width of the f_shimmer_base delta window

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


def hub_to_shard(hub_name: str) -> str | None:
    """Translate a CAIRRN hub name to its reservoir shard name, or None if unmapped."""
    return CAIRRN_HUB_TO_SHARD.get(hub_name)


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
    # D(t) hysteresis floor (Layer 6 — f_shimmer_decay).
    # A hot shard under pressure should not decay to zero.  shimmer_floor
    # provides an exponentially-decaying floor with a pressure-weighted tail.
    #   A   = raw signal amplitude (|Ec/Et|)
    #   t   = Et — edge activation threshold used as elapsed-time proxy
    #   p   = 0.5 — constant pressure proxy (TODO: wire real shard pressure)
    #   φ   = SHIMMER_PHI
    _shimmer_A = abs(ec / et) if et else 0.0
    shimmer_floor = f_shimmer_decay(
        A=_shimmer_A,
        lam=SHIMMER_LAM,
        t=et,
        p=0.5,  # TODO: replace with live pressure signal (shard coherence or activation level)
        phi_hysteresis=SHIMMER_PHI,
    )
    ns2 = max(ns2, shimmer_floor)
    ns3 = abs(ta - to_a) / max(ss, 0.01)
    cls = _classify(ns1, ns2, ns3, qe, qe_adj)
    # Crystallisation seed (f_shimmer_base) — diagnostic output.
    # Fires when the shimmer amplitude is near the reference tracking point.
    #   tp_rar_t  = shimmer_floor (the f_shimmer_decay output — reference point)
    #   decay_coef = SHIMMER_LAM * et  (accumulated decay)
    shimmer_base_val = f_shimmer_base(
        A=_shimmer_A,
        tp_rar_t=shimmer_floor,
        eps=SHIMMER_EPS,
        decay_coef=SHIMMER_LAM * et,
        p=0.5,
        phi_hysteresis=SHIMMER_PHI,
    )
    return {
        "Ec": round(ec, 4),
        "Ns1": round(ns1, 4),
        "Ns2": round(ns2, 4),
        "Ns3": round(ns3, 4),
        "Classification": cls,
        "shimmer_base": round(shimmer_base_val, 6),
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


def _fetch_current_scores(page_id: str, token: str) -> dict[str, float]:
    """
    Fetch the current numeric score properties from a Notion Scores page.

    Returns a dict with float values for any numeric property that exists on
    the page (e.g. ``{"Qe": 5.0, "Ta": 3.0, ...}``).  Returns an empty dict
    on any network / auth error so callers can safely fall back to 0.
    """
    try:
        resp = _notion_request("GET", f"pages/{page_id}", token=token)
        props = resp.get("properties", {})
        result: dict[str, float] = {}
        for key, val in props.items():
            if isinstance(val, dict) and val.get("type") == "number":
                num = val.get("number")
                if isinstance(num, (int, float)):
                    result[key] = float(num)
        return result
    except Exception:
        return {}


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
    global _shard_activations_prev

    # --- Outer guard: ring volatility gate (f_edge_volatility) ---
    # Must fire BEFORE the Si_delta gate (Phase C).  High V_edge means the
    # harmonic ring is in a soot phase — routes shift faster than crystallisation
    # can stabilise them.  Suppress the write and let the ring settle.
    all_shard_names = list(SHARD_REGISTRY.keys())
    activated_set = set(activated_shards)
    cur_activations = [1.0 if s in activated_set else 0.0 for s in all_shard_names]
    if _shard_activations_prev:
        edge_deltas = [abs(c - p) for c, p in zip(cur_activations, _shard_activations_prev)]
        v_edge = f_edge_volatility(edge_deltas, w=1.0)
        if v_edge > V_EDGE_SUPPRESS_THRESHOLD:
            return {
                "ts": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "activated": activated_shards,
                "dry_run": dry_run,
                "suppressed": True,
                "v_edge": round(v_edge, 6),
                "reason": "ring_volatile",
                "edges_written": [],
                "scores_updated": [],
                "si_skipped": [],
                "shimmer_base": {},
                "errors": [],
                "write_mode": "suppressed",
            }

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    to_a = len(activated_shards)  # global sum after this tick
    results: dict[str, Any] = {
        "ts": ts,
        "activated": activated_shards,
        "dry_run": dry_run,
        "edges_written": [],
        "scores_updated": [],
        "si_skipped": [],
        "shimmer_base": {},
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

        # Capture crystallisation seed diagnostic per shard.
        results["shimmer_base"][name] = scores.get("shimmer_base", 0.0)

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

        # -- Si_delta gate (f_crystallisation) --
        shard_page_id = reg["shard_page_id"]
        r_node_prev = _r_node_prev.get(shard_page_id, 0.0)
        current_si = float(reg["Si"])
        si_delta = abs(current_si - r_node_prev)
        thresh = f_crystallisation(eta=0.9, t_min=3, shimmerfield_t0=r_node_prev)
        si_gate_open = si_delta > thresh

        if can_write and si_gate_open:
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
                _r_node_prev[shard_page_id] = current_si
            except Exception as e:
                results["errors"].append(f"score update {name}: {e}")
        elif can_write and not si_gate_open:
            results["si_skipped"].append({
                "shard": name,
                "si_delta": round(si_delta, 6),
                "thresh": round(thresh, 6),
            })

    results["write_mode"] = "live" if can_write else ("dry-run" if dry_run else "no-token")
    # Update ring snapshot for the next volatility check.
    _shard_activations_prev = cur_activations
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
        "cairrn_hub_to_shard": CAIRRN_HUB_TO_SHARD,
        "token_configured": bool(os.environ.get("NOTION_TOKEN")),
    }
