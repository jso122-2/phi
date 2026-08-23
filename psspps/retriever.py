"""Obsidian vault document retriever for PSSPPS."""
from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path
from typing import TypedDict

from graph.layers import QUERY_LAYERS, in_layers
from graph.node import SKIP_DIRS, VAULT_ROOT

PROJECT_ROOT = VAULT_ROOT
# Directories inside the vault to skip — shared with graph.node
_SKIP_DIRS = SKIP_DIRS

# Numbers that land within the attractor-relevant range (for perspective mapping)
_NUM_RE = re.compile(r"-?\d+\.?\d*")
_ATTRACTOR_RANGE = (0.1, 20.0)

# YAML frontmatter block (between the first pair of --- fences).
# These contain metadata numbers (basin: 1.96, shard: 0) that must not
# feed into harmonic_affinity — they would give all music hubs a fake
# shard-0 affinity and let them win on any HOME-hot query.
_YAML_FRONT_RE = re.compile(r"^---\s*\n[\s\S]*?\n---", re.MULTILINE)

# Live session orientation docs are rewritten every session.  Keeping them
# in the corpus causes Phase-2 PSSPPS to retrieve itself as a top hit.
_LIVE_SESSION_STEMS = frozenset({"live-context", "live-init"})


class VaultDoc(TypedDict):
    path: str
    title: str
    text: str
    numbers: list[float]
    headings: list[str]
    wikilinks: list[str]
    clean_text: str


def load_vault_docs(layers: Sequence[str] | None = None) -> list[VaultDoc]:
    """
    Load vault notes for RAG.

    Default is stations + sessions (QUERY_LAYERS). Ingest (keep/source) is
    excluded unless callers pass layers=graph.layers.LAYERS.

    live-context.md and live-init.md are always excluded: they are rewritten
    every session and cause Phase-2 PSSPPS to surface itself as a top hit.
    """
    wanted = tuple(QUERY_LAYERS if layers is None else layers)
    docs: list[VaultDoc] = []
    for path in sorted(VAULT_ROOT.rglob("*.md")):
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        if path.stem in _LIVE_SESSION_STEMS and path.parent.name == "sessions":
            continue
        rel = str(path.relative_to(VAULT_ROOT)).replace("\\", "/")
        if not in_layers(rel, wanted):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        docs.append(_parse(path, text))
    return docs


def get_vault_corpus(layers: Sequence[str] | None = None) -> list[VaultDoc]:
    """Warm-up alias used by mcp_server.server at spawn."""
    return load_vault_docs(layers)


def _parse(path: Path, text: str) -> VaultDoc:
    headings = re.findall(r"^#{1,6}\s+(.+)$", text, re.MULTILINE)
    wikilinks = re.findall(r"\[\[([^\]|#]+?)(?:\|[^\]]+)?\]\]", text)
    # Strip YAML frontmatter before extracting numbers so metadata fields
    # (basin: 1.96, shard: 0) do not create false harmonic affinity.
    numbers = _extract_numbers(_YAML_FRONT_RE.sub(" ", text, count=1))
    clean = _clean(text)
    return VaultDoc(
        path=str(path.relative_to(VAULT_ROOT)),
        title=path.stem,
        text=text,
        numbers=numbers,
        headings=headings,
        wikilinks=wikilinks,
        clean_text=clean,
    )


def _extract_numbers(text: str) -> list[float]:
    results: list[float] = []
    for m in _NUM_RE.finditer(text):
        try:
            v = float(m.group())
            lo, hi = _ATTRACTOR_RANGE
            if lo <= abs(v) <= hi:
                results.append(v)
        except ValueError:
            pass
    return results


def _clean(text: str) -> str:
    """Strip markdown syntax to plain prose for TF-IDF."""
    # Remove code blocks
    text = re.sub(r"```[\s\S]*?```", " ", text)
    # Remove inline code
    text = re.sub(r"`[^`]+`", " ", text)
    # Remove wikilinks, keep label
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)
    # Remove markdown symbols
    text = re.sub(r"[#*>|←→↑↓~_]", " ", text)
    # Collapse whitespace
    return re.sub(r"\s+", " ", text).strip()
