"""
graph.projector — re-materialise session .md files from SQL.

SQL is the source-of-truth for sessions written by log_session() (from this
point forward).  The projector rebuilds the Obsidian facade from the SQL row
so that:

  - A lost or deleted .md can be recovered exactly
  - Bulk re-render is possible after template changes
  - The text_hash in the store stays in sync with the file on disk

Only sessions with a session_meta row (i.e., written via SQL-primary path)
can be fully re-projected.  Sessions migrated from disk without session_meta
have no stored prompt/thinking/outcome — for those the original .md is the
authoritative source and the projector returns ProjectionResult.skipped.

Public API
----------
  project(node_id)         → ProjectionResult
  project_all(force=False) → list[ProjectionResult]
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from graph.node import SESSIONS_DIR, VAULT_ROOT


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class ProjectionResult:
    node_id: str
    stem: str
    status: str          # "written" | "unchanged" | "skipped" | "error"
    path: Path | None = None
    reason: str = ""

    @property
    def ok(self) -> bool:
        return self.status in ("written", "unchanged")


# ---------------------------------------------------------------------------
# Markdown template — mirrors graph.node.write_session_node exactly
# ---------------------------------------------------------------------------


def _session_ts_from_stem(stem: str) -> str:
    """
    Parse the ISO-style timestamp prefix from a session stem.
    e.g. "2026-08-23-085100-foo" → "2026-08-23 08:51 UTC"
    Falls back to the raw stem prefix on failure.
    """
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})-(\d{2})(\d{2})(\d{2})", stem)
    if not m:
        return stem[:16]
    y, mo, d, h, mi, s = m.groups()
    return f"{y}-{mo}-{d} {h}:{mi} UTC"


def _render_session_md(
    *,
    stem: str,
    prompt: str,
    thinking: str,
    outcome: str,
    discovered_links: list[str],
) -> str:
    """Render a session node using the canonical template from graph.node."""
    ts_label = _session_ts_from_stem(stem)

    link_lines = (
        "\n".join(f"→ [[{lnk}]]" for lnk in discovered_links)
        if discovered_links
        else "*none detected*"
    )

    prompt_body   = prompt[:600]   + ("…" if len(prompt) > 600 else "")
    thinking_body = thinking[:800] + ("…" if len(thinking) > 800 else "")
    outcome_body  = outcome[:600]  + ("…" if len(outcome) > 600 else "")

    return f"""# Session: {ts_label}

#session #prompt

**Prompt:**

{prompt_body}

---

**Thinking:**

{thinking_body}

---

**Outcome:**

{outcome_body}

---

## Graph links discovered

{link_lines}

---

→ [[sessions]] — session index  
→ [[graph]] — graph worker hub  

*Logged by `graph/logger.py` — vault is the hub.*
"""


def _text_hash(text: str) -> str:
    return hashlib.md5(text.encode("utf-8", errors="replace")).hexdigest()


# ---------------------------------------------------------------------------
# Core projection logic
# ---------------------------------------------------------------------------


def project(node_id: str, force: bool = False) -> ProjectionResult:
    """
    Re-materialise one session .md from its SQL row.

    Parameters
    ----------
    node_id : canonical node_id (rel_path without .md, forward-slash)
              OR a plain stem like "2026-08-23-085100-foo"
    force   : overwrite even if text_hash matches the existing file

    Returns
    -------
    ProjectionResult with status:
      "written"   — file written (new or updated)
      "unchanged" — file exists and hash matches; no write needed
      "skipped"   — no session_meta row; original .md is authoritative
      "error"     — exception raised
    """
    from graph.store import get_store

    store = get_store()

    # Normalise: accept bare stems (no "sessions/" prefix) or full node_ids
    candidates = [node_id]
    if not node_id.startswith("sessions/"):
        candidates.insert(0, f"sessions/{node_id}")

    # Two-step lookup: first check nodes table, then session_meta
    base_row: dict | None = None
    resolved_id: str = node_id
    for cid in candidates:
        base_row = store.get_node(cid)
        if base_row is not None:
            resolved_id = cid
            break

    if base_row is None:
        return ProjectionResult(
            node_id=node_id,
            stem=node_id.split("/")[-1],
            status="error",
            reason=f"node_id not found in store: {node_id!r}",
        )

    # Node exists — now fetch session_meta
    row = store.get_session(resolved_id)

    # session_meta row missing → migrated session; original .md is authoritative
    if row is None or row.get("prompt") is None:
        return ProjectionResult(
            node_id=resolved_id,
            stem=base_row["stem"],
            status="skipped",
            reason="no session_meta — migrated session; original .md is authoritative",
        )

    stem = row["stem"]
    discovered: list[str] = json.loads(row.get("discovered_links") or "[]")

    md = _render_session_md(
        stem=stem,
        prompt=row["prompt"] or "",
        thinking=row["thinking"] or "",
        outcome=row["outcome"] or "",
        discovered_links=discovered,
    )

    target = SESSIONS_DIR / f"{stem}.md"
    new_hash = _text_hash(md)

    # Check if existing file already matches
    if not force and target.exists():
        existing = target.read_text(encoding="utf-8")
        if _text_hash(existing) == new_hash:
            return ProjectionResult(
                node_id=row["node_id"],
                stem=stem,
                status="unchanged",
                path=target,
            )

    # Write
    try:
        SESSIONS_DIR.mkdir(exist_ok=True)
        target.write_text(md, encoding="utf-8")

        # Keep text_hash in sync
        with store._lock:
            store._conn.execute(
                "UPDATE nodes SET text_hash = ?, modified_at = ? WHERE node_id = ?",
                (new_hash, datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                 row["node_id"]),
            )
            store._conn.commit()

        # Record the write as an amended event
        try:
            from graph.tracker import record
            record(row["rel_path"], "amended")
        except Exception:
            pass

        return ProjectionResult(
            node_id=row["node_id"],
            stem=stem,
            status="written",
            path=target,
        )

    except Exception as exc:
        return ProjectionResult(
            node_id=row["node_id"],
            stem=stem,
            status="error",
            reason=str(exc),
        )


def project_all(force: bool = False) -> list[ProjectionResult]:
    """
    Re-materialise every session that has a session_meta row.

    Skips sessions without session_meta (migrated from disk).
    Returns a list of ProjectionResults.
    """
    from graph.store import get_store

    store = get_store()
    sessions = store.list_sessions(limit=10_000)

    results: list[ProjectionResult] = []
    for s in sessions:
        r = project(s["node_id"], force=force)
        results.append(r)

    return results


def projection_summary(results: list[ProjectionResult]) -> dict[str, Any]:
    """Aggregate a list of ProjectionResults into a tidy summary dict."""
    written   = [r for r in results if r.status == "written"]
    unchanged = [r for r in results if r.status == "unchanged"]
    skipped   = [r for r in results if r.status == "skipped"]
    errors    = [r for r in results if r.status == "error"]

    return {
        "n_written":   len(written),
        "n_unchanged": len(unchanged),
        "n_skipped":   len(skipped),
        "n_errors":    len(errors),
        "errors":      [{"node_id": r.node_id, "reason": r.reason} for r in errors],
        "written":     [r.stem for r in written],
    }
