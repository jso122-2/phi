"""
Vault auto-linker — uses PSSPPS semantic scoring to discover and inject
wikilinks between related nodes.

Strategy
--------
For each node, build a TF-IDF query from its title + clean text, score every
other node, and inject links for any that exceed the similarity threshold.
Links are appended in a clearly-marked section so they can be audited or
removed without touching the human-authored content above.
"""
from __future__ import annotations

import re

from graph.layers import layer_of
from graph.node import VaultNode, load_vault
from psspps.scorer import build_tfidf, query_vector, semantic_scores

SIMILARITY_THRESHOLD = 0.25
MAX_LINKS_PER_NODE = 6
AUTO_LINK_MARKER = "## Auto-linked"
_AUTO_LINK_LINE = re.compile(
    r"^→\s*\[\[([^\]|#\n]+?)(?:\|[^\]]+)?\]\]\s*$"
)


# ---------------------------------------------------------------------------
# Core scoring
# ---------------------------------------------------------------------------


def score_against_corpus(
    target: VaultNode,
    corpus: list[VaultNode],
) -> list[tuple[float, VaultNode]]:
    """Return (score, node) pairs for every node in corpus except target."""
    from psspps.retriever import _clean

    texts = [_clean(n.text) for n in corpus]
    mat, vocab = build_tfidf(texts)
    q = query_vector(target.title + " " + _clean(target.text), vocab)
    scores = semantic_scores(q, mat)

    return [
        (float(scores[i]), corpus[i])
        for i in range(len(corpus))
        if corpus[i].stem != target.stem
    ]


def suggest_links(
    target: VaultNode,
    corpus: list[VaultNode],
    threshold: float = SIMILARITY_THRESHOLD,
) -> list[str]:
    """Return stems of nodes that should be linked from target (new links only)."""
    pairs = score_against_corpus(target, corpus)
    existing = set(target.wikilinks)
    results: list[str] = []

    for score, node in sorted(pairs, key=lambda x: x[0], reverse=True):
        if score < threshold:
            break
        if node.stem not in existing and node.stem not in results:
            results.append(node.stem)
        if len(results) >= MAX_LINKS_PER_NODE:
            break

    return results


# ---------------------------------------------------------------------------
# File writer
# ---------------------------------------------------------------------------


def inject_links(node: VaultNode, new_links: list[str]) -> bool:
    """
    Append or extend the Auto-linked section of a node file.
    Returns True if the file was modified.
    """
    if not new_links:
        return False

    text = node.path.read_text(encoding="utf-8")
    existing = set(re.findall(r"\[\[([^\]|#\n]+?)\]\]", text))
    to_add = [lnk for lnk in new_links if lnk not in existing]
    if not to_add:
        return False

    link_lines = "\n".join(f"→ [[{lnk}]]" for lnk in to_add)

    if AUTO_LINK_MARKER in text:
        # Extend existing section
        updated = text + "\n" + link_lines + "\n"
    else:
        updated = text.rstrip() + f"\n\n---\n\n{AUTO_LINK_MARKER}\n\n{link_lines}\n"

    node.path.write_text(updated, encoding="utf-8")
    try:
        from graph.tracker import record, record_stems
        record(node.rel_path.replace("\\", "/"), "amended")
        record_stems(to_add, "used")
    except Exception:
        pass
    return True


# ---------------------------------------------------------------------------
# Batch run
# ---------------------------------------------------------------------------


def link_all(
    vault: list[VaultNode] | None = None,
    threshold: float = SIMILARITY_THRESHOLD,
) -> list[tuple[str, list[str]]]:
    """
    Auto-link within each corpus layer. Ingest never receives station links.
    Returns a list of (stem, new_links) pairs for nodes that were modified.
    """
    from collections import defaultdict

    nodes = vault or load_vault()
    by_layer: dict[str, list[VaultNode]] = defaultdict(list)
    for node in nodes:
        by_layer[layer_of(node.rel_path)].append(node)

    modified: list[tuple[str, list[str]]] = []
    for group in by_layer.values():
        for node in group:
            links = suggest_links(node, group, threshold=threshold)
            if inject_links(node, links):
                modified.append((node.stem, links))

    return modified


def prune_unresolved_autolinks(
    vault: list[VaultNode] | None = None,
) -> dict[str, int]:
    """
    Drop Auto-linked arrow lines whose target does not resolve.
    Leaves human-authored body (including artist stubs) untouched.
    """
    from graph.worker import _link_index, _resolve_link

    nodes = vault or load_vault()
    idx, stems = _link_index(nodes)
    n_files = 0
    n_removed = 0

    for node in nodes:
        if AUTO_LINK_MARKER not in node.text:
            continue
        head, _, tail = node.text.partition(AUTO_LINK_MARKER)
        new_lines: list[str] = []
        removed_here = 0
        for line in tail.splitlines(keepends=True):
            m = _AUTO_LINK_LINE.match(line.strip("\n"))
            if m and _resolve_link(m.group(1), idx, stems) is None:
                removed_here += 1
                continue
            new_lines.append(line)
        if not removed_here:
            continue
        node.path.write_text(head + AUTO_LINK_MARKER + "".join(new_lines), encoding="utf-8")
        n_files += 1
        n_removed += removed_here

    return {"n_files": n_files, "n_removed": n_removed}
