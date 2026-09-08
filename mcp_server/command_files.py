"""
Materialise slash-command .md files from mcp_server.commands.SPECS.

The catalog in commands.py is the source of truth. This module writes:

  .agent-context/<slash>.md     workflow behaviour contracts
  .cursor/commands/<slash>.md   Cursor command palette (dispatchers + workflows)
  .cursor/rules/slash-commands.mdc
  .cursor/hooks/command-hook.sh

Call:

    python -m mcp_server.command_files          # write into the vault root
    python -m mcp_server.command_files --check  # exit 1 if files are stale
"""
from __future__ import annotations

import argparse
import os
import stat
import sys
from pathlib import Path
from typing import Any

from mcp_server.commands import CATALOG, DO_SUBS, READ_SUBS, SPECS, CommandSpec, _args_for


REPO_ROOT = Path(__file__).resolve().parent.parent

PALETTE_SLASHES: tuple[str, ...] = (
    "read",
    "do",
    "talk",
    "explain",
    "dev",
    "modular",
    "wire",
    "edit",
    "clean",
    "audit",
)

PLUGIN_HOOKS: tuple[str, ...] = ("cloud_agent_hook.py",)
"""Python hook plugin files managed under .cursor/hooks/ by this module."""

# Extra contract referenced by agent-context.md (cairrn is MCP, not a workflow slash).
EXTRA_CONTRACTS: tuple[str, ...] = ("cairrn",)


# ---------------------------------------------------------------------------
# Workflow contracts
# ---------------------------------------------------------------------------


_CONTRACTS: dict[str, str] = {
    "talk": """# /talk — Strategic discussion

#command #workflow

Read this file immediately and follow its behaviour contract for the rest of this session. Do not skip it.

## Contract

- No file edits, no git writes, no MCP mutating tools.
- Output format: `RESTATE → OPTIONS → PICK → OPEN`
- Align on direction before `/dev`. If the ask is already locked, say so and stop.

## Shape

1. **RESTATE** the problem in one short paragraph.
2. **OPTIONS** — 2–4 distinct approaches, each with a cost and a risk.
3. **PICK** one option and say why the others lose.
4. **OPEN** questions that still block a build.

When the pick is clear, tell the operator to run `/dev`.
""",
    "explain": """# /explain — Plain language

#command #workflow

Read this file immediately and follow its behaviour contract for the rest of this session. Do not skip it.

## Contract

- No file edits, no build plan, no MCP mutating tools.
- Everyday words. If a term is load-bearing, define it once.
- Output format: `IN SHORT → HOW IT WORKS → EXAMPLE`

## Shape

1. **IN SHORT** — one or two sentences.
2. **HOW IT WORKS** — the mechanism, not the history.
3. **EXAMPLE** — one concrete walk-through using this repo if it helps.

Optional topic argument is the thing to explain. If none, explain the last ask.
""",
    "dev": """# /dev — Build mode

#command #workflow

Read this file immediately and follow its behaviour contract for the rest of this session. Do not skip it.

## Contract

- **Read before write** — inspect the target file first.
- **State then act** — one sentence announcing the next action, then do it.
- **No scope creep** — only what `/talk` (or the user) agreed.
- **Fix broken things** — a linter error from your edit is your bug; fix it before moving on.
- Write, run, iterate, ship. Prefer MCP `run_command` over Shell for catalog slashes.

## Done when

Tests covering the change pass, and the operator can see evidence (test output or a walkthrough).
""",
    "modular": """# /modular — Package cleanly

#command #workflow

Read this file immediately and follow its behaviour contract for the rest of this session. Do not skip it.

## Contract

Turn raw `/dev` output into a small, importable Python surface.

- One idea per module. Public names in `__init__.py`.
- No circular imports. No unused helpers left behind.
- Keep stdlib-only modules free of numpy / FastMCP unless they already depend on them.

## Done when

`python -c "from package import name"` works from the repo root, and tests import the same path.
""",
    "wire": """# /wire — Connect the seams

#command #workflow

Read this file immediately and follow its behaviour contract for the rest of this session. Do not skip it.

## Contract

Connect all pieces — imports, config, MCP catalog, tests — then smoke every seam.

## Checklist

- All new modules importable from their package root
- `__init__.py` at every package level exports what consumers need
- No circular imports
- Config values pass through function arguments, not new globals
- Slash aliases (`READ_SUBS` / `DO_SUBS`) match `CATALOG` if you added a command
- End-to-end smoke test passes (`/health`, a read tool, a mutate tool if you touched one)

Prefer MCP `run_command` over Shell for catalog slashes.
""",
    "edit": """# /edit — Surgical fix

#command #workflow

Read this file immediately and follow its behaviour contract for the rest of this session. Do not skip it.

## Contract

- Touch only the shape / type / logic bug named in the ask.
- No drive-by refactors. No new files unless the bug is "the file is missing".
- Read the failing test or traceback first, then patch, then re-run that test.

If the fix needs a design choice, switch to `/talk` instead of guessing.
""",
    "clean": """# /clean — File tree

#command #workflow

Read this file immediately and follow its behaviour contract for the rest of this session. Do not skip it.

## Contract

Fix the repo file tree — move, delete, normalise, update `.gitignore`.

- Do not rewrite working code while cleaning.
- Keep vault notes (`*.md` hubs) where wikilinks expect them.
- After moves, update imports and wikilinks in the same change.
- Leave generated caches (`__pycache__`, `.pytest_cache`) out of git.
""",
    "audit": """# /audit — Three-layer health

#command #workflow

Read this file immediately and follow its behaviour contract for the rest of this session. Do not skip it.

## Contract

Full health audit: vault graph + codebase + environment.
Output a `CRITICAL → HIGH → MEDIUM → LOW → PASS` report.
Wait for confirmation before fixing anything.

## Calls (read-only first)

1. MCP `run_command` `/read graph`
2. MCP `run_command` `/read clean`  (orphans + dead wikilinks)
3. MCP `run_command` `/read health`
4. MCP `run_command` `/read status`
5. pytest (MCP `/do test` or `run_tests`)
6. mypy if the environment has it

Do not apply fixes until the operator says so.
""",
    "read": """# /read — Inspect

#command #workflow #dispatcher

Read this file immediately and follow its behaviour contract for the rest of this session. Do not skip it.

## Contract

- Bare `/read` loads vault context from this file and [[HOME]] / [[COMMANDS]]. No mutations.
- `/read <sub> …` dispatches a read-only MCP tool. Call `run_command` with the full slash. Do not use Shell.
- `/read help` lists every inspect subcommand.

Unknown `<sub>` is a topic, not an error — stay in workflow mode and explain that topic.

Primary inspect subs live in `mcp_server.commands.READ_SUBS` (status, health, index, graph, commands, …).
""",
    "cairrn": """# /cairrn — Hub pipeline

#command #mcp

This is not a workflow mode. `/cairrn` is an MCP slash.

- Bare `/cairrn` → `hub_state` (geometry).
- `/cairrn <hub> <metric>` → `cairrn_hub_run`.

Hubs: HOME, MATH, CODE, COMMANDS, agent-context.

Call MCP `run_command` with the slash. Do not use Shell.
See [[cairrn]] for layers.
""",
}


def _dispatcher_palette_body(group: str) -> str:
    mapping = READ_SUBS if group == "read" else DO_SUBS
    if group == "read":
        lead = (
            "The user invoked `/read`. Bare `/read` is workflow mode "
            "(load vault context). `/read <sub>` dispatches a read-only tool."
        )
        bare = (
            "Bare `/read` (no sub): read `.agent-context/read.md` and follow it. "
            "`/read help` lists subs."
        )
    else:
        lead = (
            f"The user invoked `/{group}`. This is a dispatcher, not a shell command."
        )
        bare = (
            "Bare invocation (no sub) lists subcommands via run_command. "
            "`help` / `--help` also lists subs."
        )
    lines = [
        lead,
        "",
        "Call MCP `run_command` immediately with the full slash string.",
        "Do not use Shell. Do not ask the user to run it.",
        "",
        f"Command: /{group} $ARGUMENTS",
        "",
        bare,
        "",
        "Subcommands:",
    ]
    for sub, slash in mapping.items():
        target = CATALOG[slash]
        extra = f" → `{target.tool}`" if target.tool else ""
        lines.append(f"- `{sub}` (`/{slash}`){extra} — {target.description}")
    return "\n".join(lines) + "\n"


def _palette_body(spec: CommandSpec) -> str:
    if spec.slash in {"read", "do"}:
        return _dispatcher_palette_body(spec.slash)

    if spec.kind == "workflow":
        return (
            f"The user invoked `/{spec.slash}` workflow mode.\n\n"
            f"Read `{spec.context_file}` immediately and follow its behaviour "
            f"contract for the rest of this session. Do not skip it.\n\n"
            f"Optional: call MCP `run_command` with command=`/{spec.slash}` "
            f"to confirm the contract path.\n\n"
            f"{spec.description}\n"
        )

    args = " ".join(_args_for(spec))
    shown = f"/{spec.slash}" + (f" {args}" if args else "")
    return (
        f"The user invoked `/{spec.slash}`. This is an MCP command, not a shell command.\n\n"
        f"Call MCP `run_command` immediately.\n"
        f"Do not use Shell. Do not ask the user to run it.\n\n"
        f"Command: {shown}\n"
        f"Preferred: run_command(command=\"/{spec.slash} $ARGUMENTS\")\n"
        f"Direct tool: `{spec.tool}`\n\n"
        f"{spec.description}\n"
    )


def _palette_markdown(spec: CommandSpec) -> str:
    return (
        "---\n"
        f"description: {spec.description}\n"
        "---\n\n"
        f"{_palette_body(spec)}"
    )


def _slash_commands_mdc() -> str:
    read_subs = ", ".join(f"`{s}`" for s in READ_SUBS)
    do_subs = ", ".join(f"`{s}`" for s in DO_SUBS)
    workflows = [
        spec.slash for spec in SPECS if spec.kind == "workflow"
    ]
    wf_line = ", ".join(f"`/{s}`" for s in workflows)
    aliases = [
        f"`/{spec.slash}` → `{spec.tool}`"
        for spec in SPECS
        if spec.kind == "mcp" and spec.tool
    ]
    alias_block = "\n".join(f"- {row}" for row in aliases)
    return f"""---
description: Slash command catalog — call MCP run_command, never Shell
alwaysApply: true
---

# Slash commands

Agents execute catalog slashes through the `spotify-rip` MCP server.
Do **not** run `/command` in the Shell.

## Primary surface

- `/read <sub>` — inspect (read-only tools). Bare `/read` loads `.agent-context/read.md`.
- `/do <sub>` — mutate. Bare `/do` lists subcommands.

`/read help` and `/do help` list every subcommand.

Inspect subs: {read_subs}

Mutate subs: {do_subs}

## Preferred dispatch

Call MCP `run_command` with the raw slash string (including `/read` / `/do` form).
Legacy one-shot slashes still parse as aliases.

## Workflow modes

{wf_line}

Read the matching `.agent-context/<slash>.md` immediately and follow it.

## Legacy MCP aliases

{alias_block}

If a command is missing on disk, restore with:

```
python -m mcp_server.command_files
```
"""


def _tool_calls_mdc() -> str:
    init_free = sorted([
        "init_check", "system_status", "list_hooks", "register_hook",
        "dom_queue_state", "graph_status", "graph_clean", "graph_nest",
        "graph_track_state", "forecast_state", "bus_poll", "bus_status",
        "run_command", "list_commands",
    ])
    init_free_block = ", ".join(f"`{t}`" for t in init_free)
    return f"""---
description: >
  Tool call system — hook chain, session gate, DOM houses, plugin extension
  points.  Read before making tool calls or adding hooks.
alwaysApply: false
globs:
  - mcp_server/**/*.py
  - .cursor/hooks/**
---

# Tool call system

Every call to a `spotify-rip` MCP tool passes through three layers in order:

```
1. Session gate      — block if init not done (init-free tools bypass this)
2. Pre-hook chain    — ordered list of validators; any can raise HookViolation
3. DOM house gate    — serialising BMAD lock; one house per workflow mode
```

## Session gate

Tools that require an open session: everything **not** in the init-free set.
Call `init_check()` or `system_status()` first to open the gate.

Init-free tools (no session required): {init_free_block}

The gate contract hash is returned by `init_check` and `system_status` in the
`gate_contract_hash` field — use it to verify the gate has not been bypassed.

## Pre-hook chain (`mcp_server/hooks.py`)

An append-only registry of hook functions.  Every function runs before the
tool body.  Raise `HookViolation` to abort.

**Built-in base hooks (immutable after `_seal_base()`):**

| Hook | Purpose |
|---|---|
| `audit_log` | Log every tool call name + arg keys to stderr |
| `nan_guard` | Reject float args containing NaN or Inf |
| `param_bounds_guard` | Enforce safe bounds on lr, steps, alpha, value, … |

**Session hooks (registered at gate-open by `_startup_init`):**

| Hook | Purpose |
|---|---|
| `psspps_context` | Stream PSSPPS background signal; emit notification when ready |
| `code_change_guard` | Mandate open gate + non-empty fields for graph writes |
| `harmonic_guard` | Validate shard_index, hub_name, propagation mode |
| `cairrn_guard` | Validate CAIRRN hub names |
| `phi_action_guard` | Validate phi action kinds |
| `sim_guard` | Clamp x0 to safe range |
| `temporal_graph_guard` | Validate temporal record inputs |
| `search_guard` | Require non-empty query |
| `command_dispatch` | Parse + validate run_command slash strings |

**Cloud-agent default hooks (loaded from `.cursor/hooks/cloud_agent_hook.py`):**

| Hook | Purpose |
|---|---|
| `cloud_agent_run_limit` | Abort after N calls (SPOTIFY_RIP_SESSION_CALL_LIMIT, 0 = off) |
| `cloud_agent_tag_guard` | Reject empty / non-string `run_command` arguments |
| `cloud_agent_read_only` | Block mutating tools when SPOTIFY_RIP_READ_ONLY=1 |

## Hook plugins (`.cursor/hooks/`)

Any Python file in `.cursor/hooks/` that ends in `_hook.py` and exposes a
`register_plugins(registry)` function is auto-loaded at startup.

```python
# .cursor/hooks/my_hook.py
def register_plugins(registry):
    from mcp_server.hooks import HookViolation

    def my_guard(tool_name: str, kwargs: dict) -> None:
        if tool_name == "run_tests" and kwargs.get("coverage"):
            raise HookViolation("Coverage blocked in this environment")

    registry.register(
        name="my_guard",
        description="Block coverage in this env",
        fn=my_guard,
    )
```

Disable plugin loading: `SPOTIFY_RIP_DISABLE_CLOUD_AGENT_HOOKS=1`

## DOM Request Queue (`mcp_server/dom_queue.py`)

Tools are serialised into seven BMAD houses.  Concurrent calls to the same
house queue; calls to different houses proceed in parallel.

| House | Workflow | Key tools |
|---|---|---|
| `talk` | `/talk` | `double_well_sim`, `neg_exp_sim`, `sweep_attractors` |
| `dev` | `/dev` | `run_tests` |
| `modular` | `/modular` | `harmonic_index_state`, `harmonic_propagate`, `hub_state` |
| `wire` | `/wire` | `psspps_query`, `find_query` |
| `edit` | `/edit` | `harmonic_inject`, `hub_inject` |
| `clean` | `/clean` | `harmonic_reset`, `init_check`, `system_status`, `dom_queue_state` |
| `graph` | graph ops | `graph_commit`, `graph_ingest`, `graph_link` |

## Inspect and register hooks

```
/read hooks          → list_hooks()      — full chain state
/read status         → system_status()   — includes hook_chain_version
register_hook(name, description)         — add a placeholder slot
```

## Quick reference

```python
from mcp_server.hooks import REGISTRY, HookViolation

# Inspect
print(REGISTRY.state())           # full chain
print(REGISTRY.version)           # current length
print(REGISTRY.base_version)      # immutable base count

# Register (idempotent)
REGISTRY.register("my_hook", "What it does", fn)
```

Restore command files: `python -m mcp_server.command_files`
"""


def _command_hook_sh() -> str:
    return """#!/usr/bin/env bash
# Cursor pre-hooks → mcp_server.commands.hook_main
# Modes: prompt | shell | mcp   (also hook-prompt, hook-shell, hook-mcp)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
MODE="${1:-prompt}"
export PYTHONPATH="${ROOT}${PYTHONPATH:+:$PYTHONPATH}"
if command -v python3 >/dev/null 2>&1; then
  PY=python3
else
  PY=python
fi
exec "$PY" -m mcp_server.commands "$MODE"
"""


def planned_paths(root: Path | None = None) -> dict[str, Path]:
    """Map logical name → destination path."""
    base = root or REPO_ROOT
    out: dict[str, Path] = {}
    for spec in SPECS:
        if spec.kind == "workflow" and spec.context_file:
            out[spec.context_file] = base / spec.context_file
    for name in EXTRA_CONTRACTS:
        rel = f".agent-context/{name}.md"
        out[rel] = base / rel
    for slash in PALETTE_SLASHES:
        rel = f".cursor/commands/{slash}.md"
        out[rel] = base / rel
    out[".cursor/rules/slash-commands.mdc"] = base / ".cursor/rules/slash-commands.mdc"
    out[".cursor/rules/tool-calls.mdc"] = base / ".cursor/rules/tool-calls.mdc"
    out[".cursor/hooks/command-hook.sh"] = base / ".cursor/hooks/command-hook.sh"
    return out


def _cloud_agent_hook_py() -> str:
    """Return the canonical text of cloud_agent_hook.py by reading the live file."""
    src = REPO_ROOT / ".cursor" / "hooks" / "cloud_agent_hook.py"
    if src.exists():
        return src.read_text(encoding="utf-8")
    return ""


def render_files() -> dict[str, str]:
    """rel_path → file text."""
    files: dict[str, str] = {}
    for spec in SPECS:
        if spec.kind == "workflow" and spec.context_file:
            body = _CONTRACTS.get(spec.slash)
            if body is None:
                raise RuntimeError(f"missing workflow contract for /{spec.slash}")
            files[spec.context_file] = body
    files[".agent-context/cairrn.md"] = _CONTRACTS["cairrn"]
    for slash in PALETTE_SLASHES:
        spec = CATALOG[slash]
        files[f".cursor/commands/{slash}.md"] = _palette_markdown(spec)
    files[".cursor/rules/slash-commands.mdc"] = _slash_commands_mdc()
    files[".cursor/rules/tool-calls.mdc"] = _tool_calls_mdc()
    files[".cursor/hooks/command-hook.sh"] = _command_hook_sh()
    return files


def sync_command_files(root: Path | None = None) -> dict[str, Any]:
    """Write every command .md / hook file. Returns a summary."""
    base = root or REPO_ROOT
    rendered = render_files()
    written: list[str] = []
    unchanged: list[str] = []
    for rel, text in rendered.items():
        path = base / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        existing = path.read_text(encoding="utf-8") if path.exists() else None
        if existing == text:
            unchanged.append(rel)
            continue
        path.write_text(text, encoding="utf-8")
        if rel.endswith(".sh"):
            mode = path.stat().st_mode
            path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        written.append(rel)
    return {
        "n_written": len(written),
        "n_unchanged": len(unchanged),
        "written": written,
        "unchanged": unchanged,
        "n_total": len(rendered),
    }


def check_command_files(root: Path | None = None) -> list[str]:
    """Return human-readable problems (empty list means in sync)."""
    base = root or REPO_ROOT
    rendered = render_files()
    problems: list[str] = []
    for rel, text in rendered.items():
        path = base / rel
        if not path.exists():
            problems.append(f"missing {rel}")
            continue
        got = path.read_text(encoding="utf-8")
        if got != text:
            problems.append(f"stale {rel}")
        if rel.endswith(".sh") and not os.access(path, os.X_OK):
            problems.append(f"not executable {rel}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write slash-command markdown files from the catalog")
    parser.add_argument("--check", action="store_true", help="Verify files match the catalog; do not write")
    parser.add_argument("--root", type=Path, default=None, help="Override vault root")
    args = parser.parse_args(argv)
    root = args.root
    if args.check:
        problems = check_command_files(root)
        if problems:
            print("command files out of sync:", file=sys.stderr)
            for p in problems:
                print(f"  {p}", file=sys.stderr)
            return 1
        print(f"ok — {len(render_files())} command files match the catalog")
        return 0
    summary = sync_command_files(root)
    print(
        f"command files: wrote {summary['n_written']}, "
        f"unchanged {summary['n_unchanged']}, total {summary['n_total']}"
    )
    for rel in summary["written"]:
        print(f"  wrote {rel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
