"""
Three first-class vault subgraphs. One vault on disk; walkers pick a layer.

  stations  — HOME/MATH/CODE/… + music ontology + project notes at vault root
  sessions  — sessions/ agent turns
  ingest    — keep/ + source/ (+ pipeline dump, agent-log)

PSSPPS defaults to stations+sessions. Phi playback retrieval uses stations only.
Phi's ObsidianGraph also walks source/ (code ingest) — not keep dumps.
# TODO: unify phi.data.obsidian_graph adjacency with graph.worker (one runtime).
"""
from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path

Layer = str

LAYERS: tuple[str, ...] = ("stations", "sessions", "ingest")
QUERY_LAYERS: tuple[str, ...] = ("stations", "sessions")
PHI_LAYERS: tuple[str, ...] = ("stations",)
# Code ingest is hidden from PSSPPS / playback retrieval, but Phi's
# ObsidianGraph needs the module map — keep dumps stay out.
PHI_VISIBLE_INGEST = frozenset({"source"})

INGEST_TOP = frozenset({"keep", "source", "spotify-pipeline", "agent-log"})
SESSION_TOP = frozenset({"sessions"})
# Root catalog notes that belong to ingest, not the station map
INGEST_ROOT_STEMS = frozenset({"keep", "source"})

STATION_HUB_STEMS = frozenset({
    "HOME", "MATH", "CODE", "COMMANDS", "agent-context",
    "graph", "cairrn", "phi",
    "VAULT", "GENRE", "MOOD", "ARTIST", "ENERGY", "MEMORY", "PLAYBACK", "TOPOLOGY",
    "sessions",
})

# Obsidian Graph view search: hide ingest + shadow corpus
OBSIDIAN_GRAPH_SEARCH = (
    "-path:keep -path:source -path:spotify-pipeline "
    "-path:cursor-ingest -path:agent-log"
)

_STEM_RENAMES: tuple[tuple[str, str], ...] = (
    ("keep/index.md", "keep/keep-index.md"),
    ("source/index.md", "source/source-index.md"),
    ("spotify-pipeline/index.md", "spotify-pipeline/spotify-pipeline-index.md"),
    ("spotify-pipeline/mcp-server.md", "spotify-pipeline/pipeline-mcp-server.md"),
)

_HUB_TOKEN = re.compile(r"(^|\s)#hub(?:-[\w]+)?(?![\w])")


def layer_of(rel_path: str) -> Layer:
    """Return stations | sessions | ingest for a vault-relative path."""
    rel = rel_path.replace("\\", "/").lstrip("./")
    if "/" not in rel:
        stem = rel[:-3] if rel.endswith(".md") else rel
        if stem in INGEST_ROOT_STEMS:
            return "ingest"
        return "stations"
    top = rel.split("/", 1)[0]
    if top in SESSION_TOP:
        return "sessions"
    if top in INGEST_TOP:
        return "ingest"
    return "stations"


def in_layers(rel_path: str, layers: Sequence[str]) -> bool:
    return layer_of(rel_path) in layers


def phi_visible(rel_path: str) -> bool:
    """True if Phi's ObsidianGraph should load this note."""
    if in_layers(rel_path, PHI_LAYERS):
        return True
    rel = rel_path.replace("\\", "/").lstrip("./")
    top = rel.split("/", 1)[0] if "/" in rel else ""
    return top in PHI_VISIBLE_INGEST


def cap_hub_tags(vault_root: Path | None = None) -> list[str]:
    """
    Strip #hub from notes that are not station hubs.
    Session files keep #session. Music ontology stems are in STATION_HUB_STEMS.
    """
    from graph.node import SKIP_DIRS, VAULT_ROOT, load_vault

    root = vault_root or VAULT_ROOT
    modified: list[str] = []
    for node in load_vault():  # all layers — maintenance
        if node.stem in STATION_HUB_STEMS:
            continue
        if "hub" not in node.tags:
            continue
        new = _HUB_TOKEN.sub(lambda m: m.group(1), node.text)
        if new == node.text:
            continue
        node.path.write_text(new, encoding="utf-8")
        modified.append(node.rel_path.replace("\\", "/"))
    return modified


def dedupe_index_stems(vault_root: Path | None = None) -> list[tuple[str, str]]:
    """Rename colliding ingest indexes so each stem is unique."""
    from graph.node import VAULT_ROOT

    root = vault_root or VAULT_ROOT
    done: list[tuple[str, str]] = []
    for src_rel, dst_rel in _STEM_RENAMES:
        src = root / src_rel
        dst = root / dst_rel
        if not src.exists() or dst.exists():
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        src.rename(dst)
        done.append((src_rel, dst_rel))
        _rewrite_moved_links(root, src_rel, dst_rel)
    return done


def _rewrite_moved_links(root: Path, src_rel: str, dst_rel: str) -> None:
    """Point path-prefixed and same-folder bare links at the new stem."""
    from graph.node import SKIP_DIRS

    old_stem = Path(src_rel).stem
    new_stem = Path(dst_rel).stem
    old_key = src_rel[:-3] if src_rel.endswith(".md") else src_rel
    new_key = dst_rel[:-3] if dst_rel.endswith(".md") else dst_rel
    folder = str(Path(src_rel).parent).replace("\\", "/")
    if folder == ".":
        folder = ""

    path_pat = re.compile(r"\[\[" + re.escape(old_key) + r"(?=[\]|#])")
    bare_pat = re.compile(r"\[\[" + re.escape(old_stem) + r"(?=[\]|#])")

    for p in root.rglob("*.md"):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        text = p.read_text(encoding="utf-8")
        updated = path_pat.sub(f"[[{new_key}", text)
        rel = str(p.relative_to(root)).replace("\\", "/")
        in_folder = (folder and rel.startswith(folder + "/")) or rel == src_rel or rel == dst_rel
        if in_folder:
            updated = bare_pat.sub(f"[[{new_stem}", updated)
        if updated != text:
            p.write_text(updated, encoding="utf-8")
