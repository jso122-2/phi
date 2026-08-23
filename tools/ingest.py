"""
General-purpose folder ingestion CLI.

Ingests any folder of .txt, .md, or .json files into the Obsidian vault
graph using MiniLM semantic similarity for link discovery.

Supported file types
--------------------
  .md   — Markdown: first `# Heading` becomes title, rest is body
  .txt  — Plain text: filename becomes title, content is body
  .json — Structured: expects {title?, text?, body?, content?, tags?[]}
          or Google Keep format (textContent, labels, etc.)

Output
------
  <vault>/<output-dir-name>/
      <timestamp>-<slug>.md        one file per ingested document
      index.md                     hub node listing all docs
      ingest-manifest.json         hub counts for graph_sync_manifest

Usage
-----
    python tools/ingest.py <source-folder> [--out-dir NAME]
                            [--threshold F] [--top-k N]
                            [--dry-run] [--no-wipe] [--skip-cross-link]

Arguments
---------
  source-folder   Path to the folder containing documents to ingest
  --out-dir       Name of the output subdirectory in the vault
                  (default: folder name of source)
  --threshold     Cosine similarity cutoff (default 0.30)
  --top-k         Max vault links per doc (default 5)
  --dry-run       Print what would happen, write nothing
  --no-wipe       Don't delete the output dir before re-running
  --skip-cross-link  Skip cross-linking docs within the batch
  --tags          Comma-separated tags to add to all docs
                  (default: "imported")
  --recursive     Recurse into subdirectories (default: False)

Examples
--------
    # Ingest a folder of markdown notes
    python tools/ingest.py ~/notes/ --out-dir notes

    # Ingest text files from Downloads with custom threshold
    python tools/ingest.py ~/Downloads/research/ --threshold 0.25 --top-k 8

    # Dry run to preview what would be ingested
    python tools/ingest.py ~/Documents/journal/ --dry-run
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Package root on sys.path
# ---------------------------------------------------------------------------

_PACKAGE_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_PACKAGE_ROOT))

from graph.ingestion import IngestedDoc, IngestionPipeline, write_import_index
from graph.node import VAULT_ROOT

_SLUG_RE = re.compile(r"[^a-z0-9]+")
_SUPPORTED_EXTS = {".md", ".txt", ".json"}


# ---------------------------------------------------------------------------
# File parsers
# ---------------------------------------------------------------------------


def _slug(text: str, max_len: int = 48) -> str:
    return _SLUG_RE.sub("-", text.lower()[:max_len]).strip("-") or "untitled"


def _now_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M%S")


def _parse_md(path: Path, extra_tags: list[str]) -> IngestedDoc | None:
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    if not text:
        return None
    title_m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    title = title_m.group(1).strip() if title_m else path.stem
    body = text if not title_m else text[title_m.end():].strip()
    stem = f"{_now_ts()}-{_slug(title)}"
    return IngestedDoc(
        title=title,
        text=body,
        tags=["imported"] + extra_tags,
        metadata={"Source": str(path), "created_ts": _now_ts()},
        stem_override=stem,
    )


def _parse_txt(path: Path, extra_tags: list[str]) -> IngestedDoc | None:
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    if not text:
        return None
    title = path.stem.replace("_", " ").replace("-", " ").title()
    stem = f"{_now_ts()}-{_slug(title)}"
    return IngestedDoc(
        title=title,
        text=text,
        tags=["imported"] + extra_tags,
        metadata={"Source": str(path), "created_ts": _now_ts()},
        stem_override=stem,
    )


def _parse_json(path: Path, extra_tags: list[str]) -> IngestedDoc | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None

    # Google Keep format
    if "textContent" in data or "title" in data:
        if data.get("isTrashed"):
            return None
        title = (data.get("title") or "").strip()
        text = (data.get("textContent") or "").strip()
        if not title and not text:
            return None
        tags = ["imported"] + extra_tags
        for label in data.get("labels", []):
            raw = label.get("name", "")
            if raw:
                tags.append(_SLUG_RE.sub("-", raw.lower()).strip("-"))
        created_usec = data.get("createdTimestampUsec", 0)
        ts_str = _now_ts()
        if created_usec:
            from datetime import timezone as _tz
            dt = datetime.fromtimestamp(created_usec / 1_000_000, tz=_tz.utc)
            ts_str = dt.strftime("%Y-%m-%d-%H%M%S")
        slug = _slug(title) if title else _slug(path.stem)
        stem = f"{ts_str}-{slug}"
        return IngestedDoc(
            title=title or stem.replace("-", " ").title(),
            text=text,
            tags=tags,
            metadata={"Source": str(path), "created_ts": ts_str},
            stem_override=stem,
        )

    # Generic JSON: try common text fields
    title = str(data.get("title") or data.get("name") or path.stem)
    text = str(
        data.get("text") or data.get("body") or data.get("content") or
        data.get("description") or ""
    )
    if not text.strip():
        return None
    tags_raw = data.get("tags") or data.get("labels") or []
    tags = ["imported"] + extra_tags + [str(t) for t in tags_raw if isinstance(t, str)]
    stem = f"{_now_ts()}-{_slug(title)}"
    return IngestedDoc(
        title=title,
        text=text,
        tags=tags,
        metadata={"Source": str(path), "created_ts": _now_ts()},
        stem_override=stem,
    )


def _parse_file(path: Path, extra_tags: list[str]) -> IngestedDoc | None:
    ext = path.suffix.lower()
    if ext == ".md":
        return _parse_md(path, extra_tags)
    if ext == ".txt":
        return _parse_txt(path, extra_tags)
    if ext == ".json":
        return _parse_json(path, extra_tags)
    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def run(
    source: Path,
    out_dir_name: str,
    threshold: float,
    top_k: int,
    dry_run: bool,
    no_wipe: bool,
    skip_cross_link: bool,
    extra_tags: list[str],
    recursive: bool,
) -> None:
    if not source.exists():
        print(f"ERROR: source folder not found: {source}")
        sys.exit(1)

    # Collect files
    glob_fn = source.rglob if recursive else source.glob
    files = sorted(
        p for ext in _SUPPORTED_EXTS
        for p in glob_fn(f"*{ext}")
        if p.is_file()
    )
    print(f"Found {len(files)} files in {source}  (exts: {', '.join(_SUPPORTED_EXTS)})")

    # Parse
    docs: list[IngestedDoc] = []
    skipped = 0
    for f in files:
        doc = _parse_file(f, extra_tags)
        if doc is None:
            skipped += 1
        else:
            docs.append(doc)

    print(f"  {len(docs)} docs to ingest  ({skipped} skipped / empty)")

    if dry_run:
        print("\n[DRY RUN — no files written]")
        for doc in docs[:10]:
            print(f"  → {doc.stem_override}.md  ({doc.title[:60]})")
        if len(docs) > 10:
            print(f"  ... and {len(docs) - 10} more")
        return

    out_dir = VAULT_ROOT / out_dir_name
    pipeline = IngestionPipeline(
        output_dir=out_dir,
        threshold=threshold,
        top_k=top_k,
        cross_link=not skip_cross_link,
    )

    manifest = pipeline.run(
        docs,
        wipe_output_dir=not no_wipe,
        exclude_dirs={out_dir_name},
    )

    stems = [n.stem for n in manifest.nodes]
    write_import_index(out_dir, stems, source_label=f"{source.name} import")
    print(f"  index → {out_dir_name}/index.md")

    print(f"\n{manifest.summary()}")
    print(
        f"\nTo sync the harmonic index, call in Cursor:\n"
        f"  /graph-sync-manifest {out_dir_name}/ingest-manifest.json"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest any folder of documents into the Obsidian vault graph"
    )
    parser.add_argument("source", type=Path, help="Folder containing documents to ingest")
    parser.add_argument(
        "--out-dir", type=str, default="",
        help="Vault subdirectory name for output (default: source folder name)",
    )
    parser.add_argument("--threshold", type=float, default=0.30)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-wipe", action="store_true")
    parser.add_argument("--skip-cross-link", action="store_true")
    parser.add_argument("--tags", type=str, default="", help="Comma-separated extra tags")
    parser.add_argument("--recursive", action="store_true", help="Recurse into subdirectories")
    args = parser.parse_args()

    out_dir_name = args.out_dir or _slug(args.source.name)
    extra_tags = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else []

    run(
        source=args.source,
        out_dir_name=out_dir_name,
        threshold=args.threshold,
        top_k=args.top_k,
        dry_run=args.dry_run,
        no_wipe=args.no_wipe,
        skip_cross_link=args.skip_cross_link,
        extra_tags=extra_tags,
        recursive=args.recursive,
    )


if __name__ == "__main__":
    main()
