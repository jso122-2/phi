"""
Usage-weighted git tracking for Obsidian vault notes.

Three signals, recorded by graph/PSSPPS tools (never by a full-vault scan):

  used      — retrieved as a result, linked, or discovered by graph_commit
  accessed  — visited (traverse hop, PSSPPS top-k)
  amended   — written on disk (session node, auto-link, ingest)

Heat:
  score = 3·used + 1·accessed + 2·amended
  hot   = hub | session | amended≥1 | used≥1 | accessed≥3 | score≥3

Git: vault *.md is ignored except the hot set. Code is unchanged.
The ledger is Spotify-rip/.graph-usage.json
"""
from __future__ import annotations

import json
import os
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from graph.node import SKIP_DIRS, VAULT_ROOT

Event = Literal["used", "accessed", "amended"]

LEDGER_PATH = VAULT_ROOT / ".graph-usage.json"
REPO_ROOT = VAULT_ROOT.parent
W_USED, W_ACCESSED, W_AMENDED = 3, 1, 2
HOT_SCORE = 3
ACCESS_ONLY_FLOOR = 3
NEVER_TRACK = frozenset({"live-state.md"})

BEGIN = "# BEGIN GRAPH-TRACK"
END = "# END GRAPH-TRACK"

_lock = threading.RLock()
_ledger: dict[str, dict[str, Any]] | None = None


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load() -> dict[str, dict[str, Any]]:
    global _ledger
    if _ledger is not None:
        return _ledger
    if LEDGER_PATH.exists():
        try:
            _ledger = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
        except Exception:
            _ledger = {}
    else:
        _ledger = {}
    return _ledger


def _save() -> None:
    LEDGER_PATH.write_text(
        json.dumps(_ledger or {}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def resolve_stem(stem: str) -> str | None:
    """Shortest vault-relative path for a note stem, or None."""
    bare = stem.rsplit("/", 1)[-1]
    matches: list[Path] = []
    for p in VAULT_ROOT.rglob(f"{bare}.md"):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        matches.append(p)
    if not matches:
        return None
    matches.sort(key=lambda p: (len(p.parts), str(p)))
    return matches[0].relative_to(VAULT_ROOT).as_posix()


def record(rel_path: str, event: Event, n: int = 1) -> None:
    """Increment one signal for a vault-relative .md path."""
    default = VAULT_ROOT / ".graph-usage.json"
    if os.environ.get("PYTEST_CURRENT_TEST") and LEDGER_PATH == default:
        return
    key = rel_path.replace("\\", "/").lstrip("/")
    if not key.endswith(".md"):
        key = f"{key}.md"
    with _lock:
        ledger = _load()
        row = ledger.setdefault(
            key,
            {"used": 0, "accessed": 0, "amended": 0},
        )
        row[event] = int(row.get(event, 0)) + n
        row[f"last_{event}"] = _now()
        _save()

    # Dual-write into SQL store (soft failure — never blocks the JSON write)
    try:
        from graph.store import get_store
        get_store().record_event(key, event, n)
    except Exception:
        pass


def record_stems(stems: list[str], event: Event) -> list[str]:
    """Resolve stems to paths and record. Returns paths that resolved."""
    hit: list[str] = []
    for stem in stems:
        if not stem:
            continue
        path = resolve_stem(stem.strip())
        if path:
            record(path, event)
            hit.append(path)
    return hit


def score(row: dict[str, Any]) -> int:
    return (
        W_USED * int(row.get("used", 0))
        + W_ACCESSED * int(row.get("accessed", 0))
        + W_AMENDED * int(row.get("amended", 0))
    )


def is_hot(rel_path: str, row: dict[str, Any] | None = None, hub: bool = False) -> bool:
    if rel_path in NEVER_TRACK:
        return False
    if hub or rel_path.startswith("sessions/"):
        return True
    row = row or _load().get(rel_path, {})
    if int(row.get("amended", 0)) >= 1:
        return True
    if int(row.get("used", 0)) >= 1:
        return True
    if int(row.get("accessed", 0)) >= ACCESS_ONLY_FLOOR:
        return True
    return score(row) >= HOT_SCORE


def _hub_paths() -> set[str]:
    from graph.node import load_vault
    return {n.rel_path.replace("\\", "/") for n in load_vault()
            if n.has_tag("hub") and n.rel_path.replace("\\", "/") not in NEVER_TRACK}


def hot_paths(include_hubs: bool = True) -> list[str]:
    """Vault-relative paths that should be git-tracked."""
    with _lock:
        ledger = _load()
    hubs = _hub_paths() if include_hubs else set()
    hot: set[str] = set()
    sessions = VAULT_ROOT / "sessions"
    if sessions.is_dir():
        for p in sessions.glob("*.md"):
            hot.add(p.relative_to(VAULT_ROOT).as_posix())
    hot.update(hubs)
    for rel, row in ledger.items():
        if is_hot(rel, row, hub=rel in hubs):
            hot.add(rel)
    return sorted(hot)


def _gitignore_block(hot: list[str]) -> str:
    lines = [
        BEGIN,
        "# Vault notes are git-tracked only when used, accessed, or amended.",
        "# Regenerated by graph.tracker — do not hand-edit this block.",
        "Spotify-rip/*.md",
        "Spotify-rip/**/*.md",
        "!Spotify-rip/sessions/",
        "!Spotify-rip/sessions/**",
    ]
    seen_dirs: set[str] = set()
    for rel in hot:
        if rel.startswith("sessions/"):
            continue
        parts = Path(rel).parts
        accum = Path("Spotify-rip")
        for part in parts[:-1]:
            accum = accum / part
            d = accum.as_posix() + "/"
            if d not in seen_dirs:
                lines.append(f"!{d}")
                seen_dirs.add(d)
        lines.append(f"!Spotify-rip/{rel}")
    lines.append(END)
    return "\n".join(lines) + "\n"


def write_gitignore(gitignore: Path, hot: list[str]) -> None:
    block = _gitignore_block(hot)
    text = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
    if BEGIN in text and END in text:
        pre = text[: text.index(BEGIN)]
        post = text[text.index(END) + len(END) :]
        if post.startswith("\n"):
            post = post[1:]
        text = pre.rstrip() + "\n\n" + block + post
    else:
        text = text.rstrip() + "\n\n" + block
    gitignore.write_text(text, encoding="utf-8")


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
    )


def sync_git_index(repo: Path, hot: list[str]) -> dict[str, Any]:
    """Stage hot vault notes; unstage cold ones. Does not create a commit."""
    if not (repo / ".git").exists():
        return {"git": False, "reason": "not_a_git_repo"}

    listed = _git(repo, "ls-files", "Spotify-rip")
    tracked = [
        line[len("Spotify-rip/") :]
        for line in listed.stdout.splitlines()
        if line.startswith("Spotify-rip/") and line.endswith(".md")
    ]
    hot_set = set(hot)
    staged: list[str] = []
    unstaged: list[str] = []

    for rel in hot:
        path = f"Spotify-rip/{rel}"
        if (repo / path).is_file():
            _git(repo, "add", "-f", "--", path)
            staged.append(rel)

    usage = "Spotify-rip/.graph-usage.json"
    if (repo / usage).is_file():
        _git(repo, "add", "-f", "--", usage)

    for rel in tracked:
        if rel.startswith("sessions/"):
            continue
        if rel not in hot_set:
            _git(repo, "rm", "--cached", "-q", "--", f"Spotify-rip/{rel}")
            unstaged.append(rel)

    return {
        "git": True,
        "n_staged": len(staged),
        "n_unstaged": len(unstaged),
        "staged_sample": staged[:12],
        "unstaged_sample": unstaged[:12],
    }


def sync(repo: Path | None = None) -> dict[str, Any]:
    """Rewrite the GRAPH-TRACK gitignore block and update the git index."""
    root = repo or REPO_ROOT
    hot = hot_paths()
    write_gitignore(root / ".gitignore", hot)
    git = sync_git_index(root, hot)
    return {
        "n_hot": len(hot),
        "hot_sample": hot[:16],
        "ledger_entries": len(_load()),
        **git,
    }


def state() -> dict[str, Any]:
    with _lock:
        ledger = _load()
    rows = []
    for rel, row in ledger.items():
        rows.append({
            "path": rel,
            "used": int(row.get("used", 0)),
            "accessed": int(row.get("accessed", 0)),
            "amended": int(row.get("amended", 0)),
            "score": score(row),
            "hot": is_hot(rel, row),
        })
    rows.sort(key=lambda r: (-r["score"], r["path"]))
    return {
        "n_tracked_in_ledger": len(rows),
        "n_hot": sum(1 for r in rows if r["hot"]),
        "weights": {"used": W_USED, "accessed": W_ACCESSED, "amended": W_AMENDED},
        "top": rows[:20],
    }
