"""
Cursor file ingestion — push all .cursor/ config into the Obsidian vault graph.

Scans two source trees:
  1. <workspace>/.cursor/   — local workspace rules, hooks, mcp config
  2. ~/.cursor/skills/       — project workflow skills
  3. ~/.cursor/skills-cursor/ — cursor-specific skills
  4. ~/.cursor/rules/        — global rules

Supported file types
--------------------
  .md  / .mdc  — Markdown / MDC rules  (first # heading = title)
  .sh          — Shell scripts          (filename = title, body = content)
  .json        — JSON config            (selective: skips mcp.json credential files)

Output
------
  <vault>/cursor-ingest/
      <timestamp>-<slug>.md        one file per Cursor config node
      index.md                     hub index listing all nodes
      ingest-manifest.json         for graph_sync_manifest

After running, call in Cursor:
  /graph-sync-manifest cursor-ingest/ingest-manifest.json
Then:
  samba_refresh (Samba GNN MCP tool)

Usage
-----
    python tools/cursor_ingest.py [--dry-run] [--no-wipe] [--threshold F] [--top-k N]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

_PACKAGE_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_PACKAGE_ROOT))

from graph.ingestion import IngestedDoc, IngestionPipeline, write_import_index
from graph.node import VAULT_ROOT

_SLUG_RE = re.compile(r"[^a-z0-9]+")

# Files / dirs to never ingest (credentials, binaries, caches)
_SKIP_NAMES = {
    "mcp.json",            # may contain API tokens
    ".gitignore",
    "extensions.json",
    ".obsolete",
    ".sync-manifest.json",
}
_SKIP_DIR_PARTS = {
    "extensions",           # VS Code extension binaries
    "__pycache__",
    "agent-transcripts",    # huge .jsonl files
    "projects",             # cursor project metadata
    "ai-tracking",          # sqlite DB
}
_SUPPORTED_EXTS = {".md", ".mdc", ".sh", ".json"}


def _now_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M%S")


def _slug(text: str, max_len: int = 48) -> str:
    return _SLUG_RE.sub("-", text.lower()[:max_len]).strip("-") or "untitled"


def _should_skip(path: Path) -> bool:
    if path.name in _SKIP_NAMES:
        return True
    for part in path.parts:
        if part in _SKIP_DIR_PARTS:
            return True
    return False


def _parse_md(path: Path, source_label: str) -> IngestedDoc | None:
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    if not text:
        return None
    title_m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    title = title_m.group(1).strip() if title_m else path.stem.replace("-", " ").replace("_", " ").title()
    body = text if not title_m else text[title_m.end():].strip()
    stem = f"{_now_ts()}-{_slug(title)}"
    return IngestedDoc(
        title=title,
        text=body,
        tags=["cursor", source_label, "imported"],
        metadata={"Source": str(path), "Type": path.suffix.lstrip("."), "created_ts": _now_ts()},
        stem_override=stem,
    )


def _parse_sh(path: Path, source_label: str) -> IngestedDoc | None:
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    if not text:
        return None
    # Use first comment line as description if present
    desc = ""
    for line in text.splitlines():
        stripped = line.strip().lstrip("#!").strip()
        if stripped and not stripped.startswith("/"):
            desc = stripped
            break
    title = path.stem.replace("-", " ").replace("_", " ").title()
    if desc:
        title = f"{title} — {desc[:60]}"
    stem = f"{_now_ts()}-{_slug(path.stem)}"
    return IngestedDoc(
        title=title,
        text=text,
        tags=["cursor", "hook", source_label, "imported"],
        metadata={"Source": str(path), "Type": "shell-hook", "created_ts": _now_ts()},
        stem_override=stem,
    )


def _parse_json(path: Path, source_label: str) -> IngestedDoc | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None

    # hooks.json — list or dict of hook definitions
    if path.name == "hooks.json":
        title = "Cursor Hooks Configuration"
        text = json.dumps(data, indent=2)
        stem = f"{_now_ts()}-cursor-hooks-configuration"
        return IngestedDoc(
            title=title,
            text=text,
            tags=["cursor", "hooks", source_label, "imported"],
            metadata={"Source": str(path), "Type": "hooks-config", "created_ts": _now_ts()},
            stem_override=stem,
        )

    # argv.json
    if path.name == "argv.json":
        title = "Cursor Startup Arguments"
        text = json.dumps(data, indent=2)
        stem = f"{_now_ts()}-cursor-startup-arguments"
        return IngestedDoc(
            title=title,
            text=text,
            tags=["cursor", "config", source_label, "imported"],
            metadata={"Source": str(path), "Type": "argv-config", "created_ts": _now_ts()},
            stem_override=stem,
        )

    # Generic: pull title + any text field
    title = str(data.get("title") or data.get("name") or path.stem.replace("-", " ").title())
    text_val = data.get("text") or data.get("body") or data.get("content") or data.get("description")
    if text_val is None:
        text = json.dumps(data, indent=2)
    else:
        text = str(text_val)

    if not text.strip():
        return None

    stem = f"{_now_ts()}-{_slug(title)}"
    return IngestedDoc(
        title=title,
        text=text,
        tags=["cursor", "config", source_label, "imported"],
        metadata={"Source": str(path), "Type": "json-config", "created_ts": _now_ts()},
        stem_override=stem,
    )


def _parse_file(path: Path, source_label: str) -> IngestedDoc | None:
    ext = path.suffix.lower()
    if ext in {".md", ".mdc"}:
        return _parse_md(path, source_label)
    if ext == ".sh":
        return _parse_sh(path, source_label)
    if ext == ".json":
        return _parse_json(path, source_label)
    return None


def _collect_sources() -> list[tuple[Path, str]]:
    """Return list of (path, source_label) for all Cursor source trees."""
    home = Path.home()
    workspace = VAULT_ROOT  # /Users/jacksonmacleod/Documents/Spotify-Rip

    sources = [
        (workspace / ".cursor", "workspace-cursor"),
        (home / ".cursor" / "skills", "global-skills"),
        (home / ".cursor" / "skills-cursor", "cursor-skills"),
        (home / ".cursor" / "rules", "global-rules"),
        (home / ".cursor" / "plans", "cursor-plans"),
    ]
    return [(p, label) for p, label in sources if p.exists()]


def collect_docs(sources: list[tuple[Path, str]]) -> list[IngestedDoc]:
    docs: list[IngestedDoc] = []
    skipped = 0
    seen_stems: set[str] = set()

    for source_dir, label in sources:
        files = sorted(
            p for ext in _SUPPORTED_EXTS
            for p in source_dir.rglob(f"*{ext}")
            if p.is_file()
        )
        for path in files:
            if _should_skip(path):
                skipped += 1
                continue
            doc = _parse_file(path, label)
            if doc is None:
                skipped += 1
                continue
            # Deduplicate by stem (same file found via multiple globs)
            if doc.stem_override in seen_stems:
                continue
            seen_stems.add(doc.stem_override)
            docs.append(doc)

    print(f"Collected {len(docs)} Cursor docs  ({skipped} skipped/empty)")
    return docs


def run(
    dry_run: bool = False,
    no_wipe: bool = False,
    threshold: float = 0.30,
    top_k: int = 5,
) -> None:
    sources = _collect_sources()
    print("Source trees:")
    for path, label in sources:
        print(f"  [{label}]  {path}")
    print()

    docs = collect_docs(sources)

    if dry_run:
        print("\n[DRY RUN — no files written]")
        for doc in docs[:15]:
            print(f"  → {doc.stem_override}.md  ({doc.title[:70]})")
        if len(docs) > 15:
            print(f"  ... and {len(docs) - 15} more")
        return

    out_dir = VAULT_ROOT / "cursor-ingest"
    pipeline = IngestionPipeline(
        output_dir=out_dir,
        threshold=threshold,
        top_k=top_k,
        cross_link=True,
    )

    manifest = pipeline.run(
        docs,
        wipe_output_dir=not no_wipe,
        exclude_dirs={"cursor-ingest"},
    )

    stems = [n.stem for n in manifest.nodes]
    write_import_index(out_dir, stems, source_label="Cursor config import")
    print(f"  index → cursor-ingest/index.md")
    print(f"\n{manifest.summary()}")
    print(
        "\nNext steps:\n"
        "  1. In Cursor: /graph-sync-manifest cursor-ingest/ingest-manifest.json\n"
        "  2. In Cursor: call samba_refresh (Samba GNN MCP)\n"
        "  3. Query:     /psspps <your query>  or  samba_route_query\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest all Cursor config files into the Obsidian vault graph")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--no-wipe", action="store_true", help="Don't clear output dir before writing")
    parser.add_argument("--threshold", type=float, default=0.30, help="Cosine similarity cutoff")
    parser.add_argument("--top-k", type=int, default=5, help="Max vault links per doc")
    args = parser.parse_args()

    run(
        dry_run=args.dry_run,
        no_wipe=args.no_wipe,
        threshold=args.threshold,
        top_k=args.top_k,
    )


if __name__ == "__main__":
    main()
