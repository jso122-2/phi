#!/usr/bin/env python3
"""
scripts/setup_mcp.py — one-shot global MCP installer.

Run this once on any machine (laptop, workstation, CI) to install the
spotify-rip MCP entry into ~/.cursor/mcp.json.  After that, every Cursor
project on the machine can use the server without touching its own mcp.json.

Usage
-----
    python scripts/setup_mcp.py
    python scripts/setup_mcp.py --url https://HOST/mcp --token <TOKEN>

Environment (read when --url / --token are omitted)
----------------------------------------------------
    SPOTIFY_RIP_MCP_URL    Full path incl. /mcp, e.g. https://mcp.example.com/mcp
    SPOTIFY_RIP_MCP_TOKEN  Bearer token set on the remote server

When no concrete URL/token are available the script writes the
${env:...} placeholders so Cursor expands them from the shell environment
at runtime — which is still useful because you only need to set the env
vars once on the machine, not once per repo.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

GLOBAL_MCP = Path.home() / ".cursor" / "mcp.json"
SERVER_KEY = "spotify-rip"


def _load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"mcpServers": {}}
    except json.JSONDecodeError as exc:
        print(f"[setup_mcp] warning: {path} is not valid JSON ({exc}); starting fresh", file=sys.stderr)
        return {"mcpServers": {}}


def _atomic_write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=2) + "\n"
    fd, tmp = tempfile.mkstemp(prefix=".mcp.", suffix=".json", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def build_entry(url: str | None, token: str | None) -> dict:
    resolved_url   = url   or "${env:SPOTIFY_RIP_MCP_URL}"
    resolved_token = token or "${env:SPOTIFY_RIP_MCP_TOKEN}"
    return {
        "url": resolved_url,
        "headers": {
            "Authorization": f"Bearer {resolved_token}"
        },
    }


def install(
    *,
    url: str | None = None,
    token: str | None = None,
    target: Path = GLOBAL_MCP,
    dry_run: bool = False,
) -> bool:
    """
    Merge the entry into *target*.  Returns True if the file was changed.
    """
    entry = build_entry(url, token)
    existing = _load(target)
    servers = existing.setdefault("mcpServers", {})

    if servers.get(SERVER_KEY) == entry:
        print(f"[setup_mcp] {SERVER_KEY} already up to date in {target}")
        return False

    was_present = SERVER_KEY in servers
    servers[SERVER_KEY] = entry

    if dry_run:
        print(f"[setup_mcp] (dry-run) would write to {target}:")
        print(json.dumps({SERVER_KEY: entry}, indent=2))
        return True

    _atomic_write(target, existing)
    verb = "updated" if was_present else "added"
    print(f"[setup_mcp] {verb} {SERVER_KEY} in {target}")
    if "${env:" in entry["url"]:
        print(
            f"[setup_mcp] note: URL uses placeholder; set SPOTIFY_RIP_MCP_URL"
            f" in your shell profile so Cursor can expand it."
        )
    return True


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url",   default=None, help="Streamable HTTP endpoint incl. /mcp")
    parser.add_argument("--token", default=None, help="Bearer token")
    parser.add_argument("--target", default=str(GLOBAL_MCP), help=f"Target mcp.json (default: {GLOBAL_MCP})")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be written without modifying the file")
    args = parser.parse_args(argv)

    url   = args.url   or os.environ.get("SPOTIFY_RIP_MCP_URL")   or None
    token = args.token or os.environ.get("SPOTIFY_RIP_MCP_TOKEN") or None

    install(url=url, token=token, target=Path(args.target), dry_run=args.dry_run)


if __name__ == "__main__":
    main()
