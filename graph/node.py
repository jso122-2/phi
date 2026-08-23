"""
VaultNode — read, parse, and write Obsidian markdown nodes.

The vault root is the Spotify-rip/ subdirectory.  All paths returned are
relative to it so they match Obsidian's wikilink resolution.
"""
from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

# The vault IS the package root — all .md files and Python packages coexist here
VAULT_ROOT = Path(__file__).parent.parent
SESSIONS_DIR = VAULT_ROOT / "sessions"
COMMENTS_DIR = SESSIONS_DIR / "comments"

# One skip list for every vault walker. cursor-ingest is a shadow corpus, not notes.
SKIP_DIRS = frozenset({
    ".obsidian", "__pycache__", ".git", ".hub.git",
    ".pytest_cache", "node_modules", "cursor-ingest",
})
_SKIP_DIRS = SKIP_DIRS


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class VaultNode:
    path: Path
    title: str
    tags: list[str]
    wikilinks: list[str]
    text: str

    @property
    def stem(self) -> str:
        return self.path.stem

    @property
    def rel_path(self) -> str:
        return str(self.path.relative_to(VAULT_ROOT))

    def has_tag(self, tag: str) -> bool:
        return tag in self.tags


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def load_node(path: Path) -> VaultNode:
    text = path.read_text(encoding="utf-8")
    title_m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    title = title_m.group(1).strip() if title_m else path.stem
    tags = re.findall(r"#(\w+)", text)
    wikilinks = re.findall(r"\[\[([^\]|#\n]+?)(?:\|[^\]]+)?\]\]", text)
    return VaultNode(path=path, title=title, tags=tags, wikilinks=wikilinks, text=text)


def load_vault(layers: Sequence[str] | None = None) -> list[VaultNode]:
    """
    Load vault .md files.

    layers=None loads all three subgraphs (maintenance: clean/status/prune).
    Pass QUERY_LAYERS or PHI_LAYERS from graph.layers to hide ingest.
    """
    from graph.layers import in_layers

    nodes: list[VaultNode] = []
    for p in sorted(VAULT_ROOT.rglob("*.md")):
        if any(part in _SKIP_DIRS for part in p.parts):
            continue
        rel = str(p.relative_to(VAULT_ROOT)).replace("\\", "/")
        if layers is not None and not in_layers(rel, layers):
            continue
        try:
            nodes.append(load_node(p))
        except Exception:
            pass
    return nodes


# ---------------------------------------------------------------------------
# Session node writer
# ---------------------------------------------------------------------------


def write_session_node(
    prompt: str,
    thinking: str,
    outcome: str,
    discovered_links: list[str],
) -> Path:
    """
    Write a session node to Spotify-rip/sessions/<timestamp>-<slug>.md.
    Returns the absolute path of the written file.
    """
    SESSIONS_DIR.mkdir(exist_ok=True)

    ts = datetime.now(timezone.utc)
    slug = re.sub(r"[^a-z0-9]+", "-", prompt[:45].lower()).strip("-")
    filename = f"{ts.strftime('%Y-%m-%d-%H%M%S')}-{slug}.md"

    link_lines = (
        "\n".join(f"→ [[{lnk}]]" for lnk in discovered_links)
        if discovered_links
        else "*none detected*"
    )

    # Truncate very long inputs so nodes stay readable
    prompt_body = prompt[:600] + ("…" if len(prompt) > 600 else "")
    thinking_body = thinking[:800] + ("…" if len(thinking) > 800 else "")
    outcome_body = outcome[:600] + ("…" if len(outcome) > 600 else "")

    content = f"""# Session: {ts.strftime('%Y-%m-%d %H:%M UTC')}

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
    path = SESSIONS_DIR / filename
    path.write_text(content, encoding="utf-8")
    try:
        from graph.tracker import record
        record(path.relative_to(VAULT_ROOT).as_posix(), "amended")
    except Exception:
        pass
    return path


# ---------------------------------------------------------------------------
# Agent comment node writer
# ---------------------------------------------------------------------------


def write_comment_node(
    target_stem: str,
    comment: str,
    tool_context: str = "",
    confidence: float = 0.75,
) -> Path:
    """
    Write an agent-comment node to sessions/comments/<timestamp>-comment-<slug>.md.

    Comment nodes are first-class vault nodes: PSSPPS retrieves them,
    graph_link cross-links them, and graph_commit surfaces them via PSSPPS injection.

    Parameters
    ----------
    target_stem  : stem of the vault node being annotated (wikilink target)
    comment      : agent's commentary / insight (≤ 800 chars stored)
    tool_context : MCP tool name or short context label for provenance
    confidence   : float in [0, 1] expressing annotation certainty
    """
    COMMENTS_DIR.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc)
    slug = re.sub(r"[^a-z0-9]+", "-", target_stem[:30].lower()).strip("-")
    filename = f"{ts.strftime('%Y-%m-%d-%H%M%S')}-comment-{slug}.md"

    comment_body = comment[:800] + ("…" if len(comment) > 800 else "")
    ctx_label = f"`{tool_context}`" if tool_context else "*—*"

    content = f"""# Agent Comment: {target_stem}

#agent-comment #session

**Target:** [[{target_stem}]]  
**Tool context:** {ctx_label}  
**Confidence:** {confidence:.2f}  
**Timestamp:** {ts.strftime('%Y-%m-%d %H:%M UTC')}

---

{comment_body}

---

→ [[{target_stem}]]  
→ [[sessions]] — session index  

*Written by `graph_annotate` — agent commentary layer.*
"""
    path = COMMENTS_DIR / filename
    path.write_text(content, encoding="utf-8")
    try:
        from graph.tracker import record
        record(path.relative_to(VAULT_ROOT).as_posix(), "amended")
    except Exception:
        pass
    return path


# ---------------------------------------------------------------------------
# Session init writer  (Phase 1 — synchronous, fires at gate-open)
# ---------------------------------------------------------------------------


def _last_session_summary() -> dict[str, str] | None:
    """
    Scan sessions/ for the most recently modified real session node.

    Excludes live-init.md, live-context.md, and anything in sessions/comments/.
    Returns {"stem": ..., "title": ..., "outcome_snippet": ...} or None.
    """
    if not SESSIONS_DIR.exists():
        return None
    skip_stems = {"live-init", "live-context"}
    candidates = [
        p for p in SESSIONS_DIR.glob("*.md")
        if p.stem not in skip_stems
    ]
    if not candidates:
        return None
    newest = max(candidates, key=lambda p: p.stat().st_mtime)
    try:
        text = newest.read_text(encoding="utf-8")
        title_m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
        title = title_m.group(1).strip() if title_m else newest.stem
        outcome_m = re.search(
            r"\*\*Outcome:\*\*\s*\n+(.+?)(?:\n---|\Z)", text, re.DOTALL
        )
        outcome = outcome_m.group(1).strip()[:200] if outcome_m else ""
        return {"stem": newest.stem, "title": title, "outcome_snippet": outcome}
    except Exception:
        return None


def write_live_init(
    hub_activations: dict[str, float],
    total_activation: float,
    step_count: int,
    startup_errors: dict[str, str],
    last_session: dict[str, str] | None = None,
) -> Path:
    """
    Write sessions/live-init.md — the synchronous session orientation document.

    Called at gate-open synchronously. Contains current harmonic state, last
    session summary, and boot status. Phase 2 (async PSSPPS) writes live-context.md
    as the coherence-enrichment document. Agents read this immediately after
    init_check() returns the init_account path.

    Parameters
    ----------
    hub_activations  : hub-name → scalar activation from HarmonicIndex.hub_activations()
    total_activation : sum of all shard activations
    step_count       : number of propagation steps since server start
    startup_errors   : copy of mcp_server._state.startup_errors
    last_session     : optional summary of the most recent session node
    """
    SESSIONS_DIR.mkdir(exist_ok=True)
    ts = datetime.now(timezone.utc)

    # Dominant hub = highest activation
    if hub_activations:
        dominant_hub = max(hub_activations, key=lambda h: hub_activations[h])
    else:
        dominant_hub = "—"

    # Shard-activation ordered hub list (descending)
    sorted_hubs = sorted(hub_activations.items(), key=lambda kv: kv[1], reverse=True)
    hub_lines = "\n".join(
        f"- **{hub}**: {act:.4f}" for hub, act in sorted_hubs
    ) or "- *unavailable*"

    # Last session block
    if last_session:
        session_stem = last_session.get("stem", "—")
        session_title = last_session.get("title", "—")
        outcome_snip = last_session.get("outcome_snippet", "")
        last_session_block = (
            f"- [[{session_stem}]] — {session_title}\n"
            f"- Outcome: {outcome_snip[:180]}"
        )
    else:
        last_session_block = "- *no prior session found*"

    # Boot status
    if startup_errors:
        error_lines = "\n".join(f"- `{k}`: {v[:80]}" for k, v in startup_errors.items())
        boot_status = f"⚠ degraded\n\n{error_lines}"
    else:
        boot_status = "✓ healthy — all singletons live"

    content = f"""# Session Init — {ts.strftime('%Y-%m-%d %H:%M UTC')}

#live-init #session

*Phase 1 of 2 — synchronous. Read [[live-context]] when \
`[coherence] ready` fires for the full PSSPPS enrichment.*

---

## Harmonic State

- Total activation: **{total_activation:.4f}**
- Dominant hub: **{dominant_hub}**
- Step count: {step_count}

### Hub activations (coherence order)

{hub_lines}

---

## Last Session

{last_session_block}

---

## Boot Status

{boot_status}

---

→ [[sessions]] — session index  
→ [[live-context]] — Phase 2 enrichment (async)  

*Written by `write_live_init` at gate-open — \
read [[live-context]] once `[coherence] ready` fires.*
"""
    path = SESSIONS_DIR / "live-init.md"
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Live context writer (session-open PSSPPS result — Phase 2 async)
# ---------------------------------------------------------------------------


def write_live_context(top_docs: list[dict]) -> Path:
    """
    Write PSSPPS top-k results to sessions/live-context.md.

    Overwritten at each session open by the psspps_context_hook.
    Agents can read this node to get harmonic-aware context without an
    explicit /psspps call.

    Parameters
    ----------
    top_docs : list of dicts with keys: title, path, combined_score, snippet
    """
    SESSIONS_DIR.mkdir(exist_ok=True)

    ts = datetime.now(timezone.utc)
    lines = [
        f"# Live Context — {ts.strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "#live-context #session",
        "",
        f"*Auto-generated at session open — {len(top_docs)} vault nodes retrieved.*",
        "",
        "---",
        "",
    ]
    for i, doc in enumerate(top_docs, 1):
        title = doc.get("title", "?")
        path_str = doc.get("path", "")
        snippet = doc.get("snippet", "")[:220]
        score = doc.get("combined_score", 0.0)
        lines += [
            f"## {i}. [[{title}]]",
            f"*path:* `{path_str}` · *score:* {score:.3f}",
            "",
            snippet,
            "",
        ]
    lines += [
        "---",
        "",
        "→ [[sessions]] — session index",
        "",
        "*Written by `psspps_context_hook` — harmonic session-open RAG.*",
    ]

    path = SESSIONS_DIR / "live-context.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
