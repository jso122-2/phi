"""
Google Keep Takeout → Obsidian vault importer.

Thin adapter over graph.ingestion.IngestionPipeline.  Handles the Google
Keep JSON schema (title, textContent, labels, timestamps, isTrashed) and
feeds clean IngestedDoc objects into the pipeline.

After writing, runs /graph-sync-manifest automatically by calling the
pipeline's manifest directly against the harmonic index — or prints the
manual command if the MCP server is not reachable.

Usage (from Spotify-rip/ with mamba base env Python):
    python tools/keep_ingest.py [--keep-dir PATH] [--dry-run]
                                [--threshold F] [--top-k N]
                                [--skip-cross-link] [--no-wipe]

Defaults
--------
--keep-dir      ~/Downloads/Takeout/Keep
--threshold     0.30   (cosine similarity cutoff)
--top-k         5      (max vault links per note)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Resolve package root so graph.* imports work from any cwd
# ---------------------------------------------------------------------------

_PACKAGE_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_PACKAGE_ROOT))

from graph.ingestion import IngestedDoc, IngestionPipeline, write_import_index
from graph.node import VAULT_ROOT

KEEP_DIR_DEFAULT = Path.home() / "Downloads" / "Takeout" / "Keep"
KEEP_OUT_DIR = VAULT_ROOT / "keep"

_SLUG_RE = re.compile(r"[^a-z0-9]+")


# ---------------------------------------------------------------------------
# Keep JSON → IngestedDoc
# ---------------------------------------------------------------------------


def _slug(text: str, max_len: int = 48) -> str:
    return _SLUG_RE.sub("-", text.lower()[:max_len]).strip("-") or "untitled"


def _ts_to_dt(usec: int) -> datetime:
    return datetime.fromtimestamp(usec / 1_000_000, tz=timezone.utc)


def _should_skip(note: dict) -> bool:
    if note.get("isTrashed"):
        return True
    title = (note.get("title") or "").strip()
    text = (note.get("textContent") or "").strip()
    return not title and not text


def _keep_note_to_doc(note: dict, source_path: Path) -> IngestedDoc:
    title = (note.get("title") or "").strip()
    text = (note.get("textContent") or "").strip()

    tags: list[str] = ["keep", "imported"]
    if note.get("isPinned"):
        tags.append("pinned")
    if note.get("isArchived"):
        tags.append("archived")
    for label in note.get("labels", []):
        raw = label.get("name", "")
        if raw:
            tags.append(_SLUG_RE.sub("-", raw.lower()).strip("-"))

    created_usec = note.get("createdTimestampUsec", 0)
    edited_usec = note.get("userEditedTimestampUsec", 0)
    dt = _ts_to_dt(created_usec) if created_usec else datetime.now(tz=timezone.utc)
    ts_str = dt.strftime("%Y-%m-%d-%H%M%S")

    slug = _slug(title) if title else _slug(source_path.stem)
    stem = f"{ts_str}-{slug}"

    meta = {
        "created_ts": ts_str,
        "Created": _ts_to_dt(created_usec).strftime("%Y-%m-%d %H:%M UTC") if created_usec else "unknown",
        "Edited": _ts_to_dt(edited_usec).strftime("%Y-%m-%d %H:%M UTC") if edited_usec else "unknown",
        "Source": "Google Keep",
    }

    return IngestedDoc(
        title=title or stem.replace("-", " ").title(),
        text=text,
        tags=tags,
        metadata=meta,
        stem_override=stem,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def run(
    keep_dir: Path,
    dry_run: bool,
    threshold: float,
    top_k: int,
    skip_cross_link: bool,
    no_wipe: bool,
) -> None:
    notes_json = sorted(keep_dir.glob("*.json"))
    print(f"Found {len(notes_json)} JSON files in {keep_dir}")

    docs: list[IngestedDoc] = []
    skipped = 0

    for path in notes_json:
        try:
            note = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"  SKIP (parse error) {path.name}: {exc}")
            skipped += 1
            continue

        if _should_skip(note):
            skipped += 1
            continue

        docs.append(_keep_note_to_doc(note, path))

    print(f"  {len(docs)} active notes  ({skipped} skipped)\n")

    if dry_run:
        print("[DRY RUN — no files written]")
        for doc in docs[:10]:
            print(f"  would write: {doc.stem_override}.md  ({doc.title[:50]})")
        if len(docs) > 10:
            print(f"  ... and {len(docs) - 10} more")
        print(f"\nTotal would write: {len(docs)}")
        return

    pipeline = IngestionPipeline(
        output_dir=KEEP_OUT_DIR,
        threshold=threshold,
        top_k=top_k,
        cross_link=not skip_cross_link,
    )

    manifest = pipeline.run(
        docs,
        wipe_output_dir=not no_wipe,
        exclude_dirs={"keep"},
    )

    # Write the hub index node
    stems = [n.stem for n in manifest.nodes]
    write_import_index(KEEP_OUT_DIR, stems, source_label="Google Keep import")
    print(f"  index → keep/index.md")

    print(f"\n{manifest.summary()}")
    print(
        "\nTo sync the harmonic index, call in Cursor:\n"
        "  /graph-sync-manifest keep/ingest-manifest.json"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import Google Keep Takeout into Obsidian vault"
    )
    parser.add_argument("--keep-dir", type=Path, default=KEEP_DIR_DEFAULT)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--threshold", type=float, default=0.30)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--skip-cross-link", action="store_true")
    parser.add_argument("--no-wipe", action="store_true", help="Don't delete keep/ before re-running")
    args = parser.parse_args()
    run(args.keep_dir, args.dry_run, args.threshold, args.top_k, args.skip_cross_link, args.no_wipe)


if __name__ == "__main__":
    main()
