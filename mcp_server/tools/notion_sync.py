"""
phi → Notion Sync — notion_pull() MCP tool.

Fetches skills text and shard config from the Notion workspace (via the
Notion API) and writes them as .md files into reservoir/ in the vault.

Each written file carries frontmatter:
    hub:       <hub-name>
    layer:     reservoir
    source:    notion
    synced_at: <ISO timestamp>

Requires NOTION_TOKEN env var (Notion integration secret).
Without a token the tool returns a dry-run summary with no files written.

Usage via MCP run_command:
    /do notion_pull
    /do notion_pull shards=dawn-fragments,recursive-thought
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Vault path — reservoir/ lives at repo root
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
_RESERVOIR_DIR = _REPO_ROOT / "reservoir"

# ---------------------------------------------------------------------------
# Shard → Notion page mapping
# Pulled from notion_reservoir.SHARD_REGISTRY for the shard config pages.
# ---------------------------------------------------------------------------

# Maps shard name → hub name (for frontmatter) + Notion shard_page_id
_SHARD_HUB_MAP: dict[str, dict[str, str]] = {
    "dawn-fragments":     {"hub": "HOME",          "page_id": "3ce350886c9d813291a2dfb80dccafb9"},
    "schema-fragments":   {"hub": "agent-context", "page_id": "3ce350886c9d8163b25ee5b1122c3cb5"},
    "recursive-thought":  {"hub": "MATH",          "page_id": "3ce350886c9d81ddaac8d07105affc0e"},
    "valence-high":       {"hub": "COMMANDS",      "page_id": "3ce350886c9d8106a752f73ffc14e47a"},
    "novel-fragments":    {"hub": "CODE",           "page_id": "3ce350886c9d81d296a4fcfa47b79093"},
}

# Skills database ID (Notion workspace — jack dev's Space)
_SKILLS_DB_ID = "54c008d6-e791-4f26-ab48-11dfe7c8e796"

# ---------------------------------------------------------------------------
# Notion API helper
# ---------------------------------------------------------------------------

def _notion_get(path: str, token: str) -> dict:
    """GET a Notion API endpoint and return the parsed JSON body."""
    url = f"https://api.notion.com/v1/{path.lstrip('/')}"
    req = urllib.request.Request(
        url,
        method="GET",
        headers={
            "Authorization": f"Bearer {token}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def _notion_query(path: str, body: dict, token: str) -> dict:
    """POST a Notion API query endpoint and return the parsed JSON body."""
    url = f"https://api.notion.com/v1/{path.lstrip('/')}"
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


# ---------------------------------------------------------------------------
# Rich-text extraction helper
# ---------------------------------------------------------------------------

def _rich_text_to_str(rich_text: list[dict]) -> str:
    """Flatten a Notion rich_text array to a plain string."""
    return "".join(span.get("plain_text", "") for span in rich_text)


# ---------------------------------------------------------------------------
# Markdown writer
# ---------------------------------------------------------------------------

def _write_reservoir_md(
    slug: str,
    hub: str,
    title: str,
    body: str,
    synced_at: str,
    extra_frontmatter: dict[str, Any] | None = None,
) -> Path:
    """
    Write a markdown file to reservoir/<slug>.md with standard frontmatter.

    Returns the Path that was written.
    """
    _RESERVOIR_DIR.mkdir(exist_ok=True)
    dest = _RESERVOIR_DIR / f"{slug}.md"

    fm_lines = [
        "---",
        f"hub: {hub}",
        "layer: reservoir",
        "source: notion",
        f"synced_at: {synced_at}",
    ]
    if extra_frontmatter:
        for k, v in extra_frontmatter.items():
            fm_lines.append(f"{k}: {v}")
    fm_lines.append("---")
    fm_lines.append("")

    content = "\n".join(fm_lines) + f"# {title}\n\n{body.strip()}\n"
    dest.write_text(content, encoding="utf-8")
    return dest


# ---------------------------------------------------------------------------
# Pull logic
# ---------------------------------------------------------------------------

def _pull_shard_pages(token: str, shard_names: list[str], synced_at: str) -> list[dict]:
    """Fetch shard config pages from Notion and write to reservoir/."""
    written: list[dict] = []
    for shard_name in shard_names:
        meta = _SHARD_HUB_MAP.get(shard_name)
        if meta is None:
            written.append({"shard": shard_name, "status": "unknown-shard"})
            continue
        try:
            page = _notion_get(f"pages/{meta['page_id']}", token)
            props = page.get("properties", {})

            # Extract title (Name or title property)
            title_prop = props.get("Name") or props.get("title") or {}
            title_list = title_prop.get("title", [])
            page_title = _rich_text_to_str(title_list) or shard_name

            # Build a simple body from all text-like properties
            body_lines: list[str] = []
            for prop_name, prop_val in props.items():
                ptype = prop_val.get("type", "")
                if ptype == "rich_text":
                    text = _rich_text_to_str(prop_val.get("rich_text", []))
                    if text:
                        body_lines.append(f"**{prop_name}**: {text}")
                elif ptype == "number" and prop_val.get("number") is not None:
                    body_lines.append(f"**{prop_name}**: {prop_val['number']}")
                elif ptype == "select" and prop_val.get("select"):
                    body_lines.append(f"**{prop_name}**: {prop_val['select']['name']}")

            body = "\n\n".join(body_lines) if body_lines else "_No properties extracted._"
            slug = f"shard-{shard_name}"
            dest = _write_reservoir_md(
                slug=slug,
                hub=meta["hub"],
                title=page_title,
                body=body,
                synced_at=synced_at,
                extra_frontmatter={"shard": shard_name},
            )
            written.append({"shard": shard_name, "status": "ok", "file": str(dest.relative_to(_REPO_ROOT))})
        except Exception as exc:
            written.append({"shard": shard_name, "status": "error", "error": str(exc)})
    return written


def _pull_skills(token: str, synced_at: str) -> list[dict]:
    """Query the Scores/Skills Notion DB and write one .md per entry."""
    written: list[dict] = []
    try:
        resp = _notion_query(
            f"databases/{_SKILLS_DB_ID}/query",
            {"page_size": 50},
            token,
        )
        pages = resp.get("results", [])
        for page in pages:
            props = page.get("properties", {})

            # Title
            title_prop = props.get("Name") or props.get("Skill") or props.get("title") or {}
            title_list = title_prop.get("title", [])
            skill_title = _rich_text_to_str(title_list).strip()
            if not skill_title:
                continue  # skip untitled rows

            # Slug: lowercase, replace spaces with hyphens
            slug = "skill-" + skill_title.lower().replace(" ", "-").replace("/", "-")

            # Build body from all readable properties
            body_lines: list[str] = []
            hub = "HOME"  # default
            for prop_name, prop_val in props.items():
                ptype = prop_val.get("type", "")
                if ptype == "rich_text":
                    text = _rich_text_to_str(prop_val.get("rich_text", []))
                    if text:
                        body_lines.append(f"**{prop_name}**: {text}")
                elif ptype == "number" and prop_val.get("number") is not None:
                    body_lines.append(f"**{prop_name}**: {prop_val['number']}")
                elif ptype == "select" and prop_val.get("select"):
                    val_name = prop_val["select"]["name"]
                    body_lines.append(f"**{prop_name}**: {val_name}")
                    if prop_name.lower() in ("hub", "register", "axis"):
                        hub = val_name
                elif ptype == "checkbox":
                    body_lines.append(f"**{prop_name}**: {prop_val.get('checkbox', False)}")

            body = "\n\n".join(body_lines) if body_lines else "_No properties extracted._"
            dest = _write_reservoir_md(
                slug=slug,
                hub=hub,
                title=skill_title,
                body=body,
                synced_at=synced_at,
            )
            written.append({"skill": skill_title, "status": "ok", "file": str(dest.relative_to(_REPO_ROOT))})
    except Exception as exc:
        written.append({"skill": "_query_", "status": "error", "error": str(exc)})
    return written


# ---------------------------------------------------------------------------
# MCP tool entry point
# ---------------------------------------------------------------------------

def notion_pull(
    shards: str = "all",
    include_skills: bool = True,
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    MCP tool: pull Notion shard configs and skills into reservoir/ as .md files.

    shards:         comma-separated shard names, or "all" for all 5 shards
    include_skills: if True (default), also query the Scores/Skills DB
    dry_run:        if True, return what would be written without touching files
    """
    token = os.environ.get("NOTION_TOKEN", "")
    synced_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if dry_run or not token:
        shard_list = list(_SHARD_HUB_MAP.keys()) if shards == "all" else [s.strip() for s in shards.split(",") if s.strip()]
        return {
            "status": "dry-run" if dry_run else "no-token",
            "would_write_shards": shard_list,
            "would_write_skills": include_skills,
            "reservoir_dir": str(_RESERVOIR_DIR.relative_to(_REPO_ROOT)),
            "token_configured": bool(token),
        }

    shard_list = list(_SHARD_HUB_MAP.keys()) if shards == "all" else [s.strip() for s in shards.split(",") if s.strip()]

    result: dict[str, Any] = {
        "synced_at": synced_at,
        "reservoir_dir": str(_RESERVOIR_DIR.relative_to(_REPO_ROOT)),
        "shards": [],
        "skills": [],
    }

    result["shards"] = _pull_shard_pages(token, shard_list, synced_at)

    if include_skills:
        result["skills"] = _pull_skills(token, synced_at)

    ok_shards = sum(1 for s in result["shards"] if s.get("status") == "ok")
    ok_skills = sum(1 for s in result["skills"] if s.get("status") == "ok")
    result["summary"] = f"{ok_shards}/{len(shard_list)} shards, {ok_skills} skills written to reservoir/"
    return result
