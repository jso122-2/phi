"""
GraphWorker — autonomous Obsidian graph maintenance.

Operations:

  run_clean       find orphan nodes + dead wikilinks
  run_link        auto-link semantically related nodes (calls linker.link_all)
  run_nest        suggest hub assignments for untagged nodes
  run_status      full graph health snapshot
  run_topo_hubs   elect hubs from weakly-connected wikilink components
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from graph.node import VaultNode, load_vault
from graph.linker import SIMILARITY_THRESHOLD, link_all
from graph.topo_graph import TopoHubReport, analyse as _topo_analyse, write_hub_tags as _topo_write_tags

HUB_TAGS = {"hub", "math", "code", "command", "session"}

# Folder indexes and ledgers — real stations are HOME / MATH / CODE / …
STRUCTURAL_HUBS = frozenset({
    "index", "sessions", "git-log", "live-state", "graph", "keep",
})


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class CleanReport:
    n_nodes: int
    orphans: list[str]           # nodes with zero incoming links (excluding hubs)
    dead_links: list[str]        # "source → [[target]]" for unresolved targets
    hub_nodes: list[str]
    session_nodes: int


@dataclass
class LinkReport:
    n_nodes_modified: int
    n_new_links: int
    modified: list[tuple[str, list[str]]]   # (stem, new_links)


@dataclass
class NestReport:
    suggestions: list[dict]     # [{node, suggested_hub, shared_links}]


@dataclass
class GraphStatus:
    n_nodes: int
    n_session_nodes: int
    n_hubs: int
    n_orphans: int
    n_dead_links: int
    total_wikilinks: int
    most_linked: list[tuple[str, int]]   # (stem, incoming_count) top-5


# ---------------------------------------------------------------------------
# Wikilink resolution (Obsidian path prefixes)
# ---------------------------------------------------------------------------


def _link_index(nodes: list) -> tuple[dict[str, str], set[str]]:
    """Map every recognisable path/stem → canonical stem."""
    stems = {n.stem for n in nodes}
    idx: dict[str, str] = {s: s for s in stems}
    for n in nodes:
        rel = getattr(n, "rel_path", "") or ""
        if rel:
            key = rel[:-3] if rel.endswith(".md") else rel
            idx[key.replace("\\", "/")] = n.stem
    return idx, stems


def _resolve_link(
    link: str,
    path_index: dict[str, str],
    stems: set[str],
) -> str | None:
    """
    Resolve a wikilink to its canonical bare stem, stripping any path prefix.

    Obsidian accepts [[keep/foo-bar]] and [[foo-bar]] as the same note.
    """
    if not link:
        return None
    key = link.strip().replace("\\", "/")
    if key in path_index:
        return path_index[key]
    if key in stems:
        return key
    bare = key.rsplit("/", 1)[-1]
    if bare in path_index:
        return path_index[bare]
    if bare in stems:
        return bare
    return None


def _tally(nodes: list) -> tuple[dict[str, int], list[str]]:
    """Incoming counts (resolved stems) and unresolved 'src → [[link]]' rows."""
    idx, stems = _link_index(nodes)
    incoming: dict[str, int] = defaultdict(int)
    dead: list[str] = []
    for node in nodes:
        for link in node.wikilinks:
            resolved = _resolve_link(link, idx, stems)
            if resolved:
                incoming[resolved] += 1
            else:
                dead.append(f"{node.stem} → [[{link}]]")
    return incoming, dead


# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------


def run_clean(vault: list[VaultNode] | None = None) -> CleanReport:
    """
    Scan the vault for structural problems:
    - Orphan nodes (no other node links to them, excluding hubs and sessions)
    - Dead wikilinks (point to nodes that don't exist)

    Path-prefixed links ([[keep/foo]], [[source/bar]]) resolve to the bare
    stem, matching Obsidian.
    """
    nodes = vault or load_vault()
    incoming, dead = _tally(nodes)

    hub_nodes = [n.stem for n in nodes if "hub" in n.tags]
    session_nodes = [n for n in nodes if "session" in n.tags]
    orphans = [
        n.stem
        for n in nodes
        if incoming[n.stem] == 0
        and "hub" not in n.tags
        and "session" not in n.tags
    ]

    return CleanReport(
        n_nodes=len(nodes),
        orphans=orphans,
        dead_links=dead,
        hub_nodes=hub_nodes,
        session_nodes=len(session_nodes),
    )


def run_link(
    vault: list[VaultNode] | None = None,
    threshold: float = SIMILARITY_THRESHOLD,
) -> LinkReport:
    """Auto-link semantically related nodes within each corpus layer."""
    nodes = vault or load_vault()
    modified = link_all(vault=nodes, threshold=threshold)
    return LinkReport(
        n_nodes_modified=len(modified),
        n_new_links=sum(len(lnks) for _, lnks in modified),
        modified=modified,
    )


def run_nest(vault: list[VaultNode] | None = None) -> NestReport:
    """
    Suggest hub assignment for nodes that have no hub-level tags.
    Scoring is based on shared wikilinks (fast, no TF-IDF cost).
    """
    nodes = vault or load_vault()
    hubs = [
        n for n in nodes
        if "hub" in n.tags and n.stem not in STRUCTURAL_HUBS
    ]
    untagged = [
        n for n in nodes
        if not HUB_TAGS.intersection(n.tags) and n.stem not in STRUCTURAL_HUBS
    ]

    suggestions: list[dict] = []
    for node in untagged:
        node_links = set(node.wikilinks)
        scores: list[tuple[int, str]] = []
        for hub in hubs:
            shared = len(node_links & set(hub.wikilinks))
            scores.append((shared, hub.stem))
        if scores:
            best_count, best_hub = max(scores)
            suggestions.append({
                "node": node.stem,
                "suggested_hub": best_hub,
                "shared_links": best_count,
            })

    return NestReport(suggestions=suggestions)


def run_status(vault: list[VaultNode] | None = None) -> GraphStatus:
    """Full graph health snapshot — runs clean + counts, no file writes."""
    nodes = vault or load_vault()
    incoming, dead = _tally(nodes)

    hubs = sum(1 for n in nodes if "hub" in n.tags)
    sessions = sum(1 for n in nodes if "session" in n.tags)
    orphans = sum(
        1 for n in nodes
        if incoming[n.stem] == 0 and "hub" not in n.tags and "session" not in n.tags
    )
    total_links = sum(len(n.wikilinks) for n in nodes)
    top5 = sorted(incoming.items(), key=lambda x: x[1], reverse=True)[:5]

    return GraphStatus(
        n_nodes=len(nodes),
        n_session_nodes=sessions,
        n_hubs=hubs,
        n_orphans=orphans,
        n_dead_links=len(dead),
        total_wikilinks=total_links,
        most_linked=top5,
    )


def run_topo_hubs(
    vault: list[VaultNode] | None = None,
    min_component_size: int = 2,
    write_tags: bool = False,
    prefix_filter: str = "",
) -> TopoHubReport:
    """
    Elect topological hubs via β₀ weakly-connected components.

    prefix_filter restricts analysis to stems starting with that prefix
    (e.g. "source" → only source-* nodes). write_tags injects #topo-hub.
    """
    nodes = vault or load_vault()
    if prefix_filter:
        nodes = [n for n in nodes if n.stem.startswith(prefix_filter)]
    report = _topo_analyse(vault=nodes, min_component_size=min_component_size)
    if write_tags:
        _topo_write_tags(report, vault=nodes)
    return report
