"""
topo_graph.py — topological hub election via β₀ connected components.

Strategy (Option B)
-------------------
Build a directed wikilink graph G from the vault.  Find weakly-connected
components (β₀).  Within each component, elect the node with the highest
in-degree as the topological hub; all others become spokes.

    hubs = {comp_id: argmax_in_degree(comp)}

Hubs emerge from the vault's own link structure — no manual schema.
If many nodes reference one node it naturally becomes a hub.

Degree metric
-------------
  in_degree   : how many other nodes link TO this node  →  "referenced by"
  Tie-break   : total degree (in + out) when in-degrees are equal

Min component size
------------------
  Components of size 1 are isolated nodes (orphans from run_clean's
  perspective).  They receive no hub tag — they need more links first.
  Default min_component_size = 2.

Tag injection
-------------
  When write_tags=True, the elected hub's .md file gets a `#topo-hub` tag
  appended to its first `#tag` line.  Idempotent — skips if already tagged.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import networkx as nx

from graph.node import VaultNode, load_vault, VAULT_ROOT

_TOPO_HUB_TAG = "topo-hub"


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------


def build(
    vault: list[VaultNode] | None = None,
) -> nx.DiGraph:
    """
    Build a directed wikilink graph from the vault.

    Nodes = vault stem strings.
    Edges = directed wikilinks: source_stem → target_stem.
    Only resolved edges are included (dead links are dropped).
    """
    nodes = load_vault() if vault is None else vault
    stems = {n.stem for n in nodes}

    G: nx.DiGraph = nx.DiGraph()
    G.add_nodes_from(stems)

    for node in nodes:
        src = node.stem
        for link in node.wikilinks:
            bare = link.rsplit("/", 1)[-1]
            if bare in stems and bare != src:
                G.add_edge(src, bare)

    return G


# ---------------------------------------------------------------------------
# β₀ component analysis
# ---------------------------------------------------------------------------


@dataclass
class ComponentRecord:
    component_id: int
    size: int
    hub: str                         # elected hub stem
    hub_in_degree: int
    hub_total_degree: int
    spokes: list[str]                # all non-hub stems in component
    already_hub_tagged: bool = False  # True if hub already has #hub or #topo-hub


@dataclass
class TopoHubReport:
    n_nodes: int
    n_edges: int
    n_components: int
    n_singletons: int                # components of size 1
    n_elected: int                   # components that got a hub
    components: list[ComponentRecord]
    # Convenience maps
    hub_to_spokes: dict[str, list[str]] = field(default_factory=dict)
    spoke_to_hub: dict[str, str] = field(default_factory=dict)

    def summary(self) -> dict[str, Any]:
        return {
            "nodes":        self.n_nodes,
            "edges":        self.n_edges,
            "components":   self.n_components,
            "singletons":   self.n_singletons,
            "elected_hubs": self.n_elected,
            "top_hubs": [
                {
                    "hub":        c.hub,
                    "in_degree":  c.hub_in_degree,
                    "size":       c.size,
                    "spokes":     len(c.spokes),
                }
                for c in sorted(
                    self.components, key=lambda c: c.hub_in_degree, reverse=True
                )[:10]
            ],
        }


def analyse(
    G: nx.DiGraph | None = None,
    vault: list[VaultNode] | None = None,
    min_component_size: int = 2,
) -> TopoHubReport:
    """
    Find weakly-connected components and elect a hub per component.

    Parameters
    ----------
    G                   : pre-built DiGraph (built from vault if None)
    vault               : pre-loaded vault (loaded if None)
    min_component_size  : components smaller than this receive no hub (default 2)

    Returns
    -------
    TopoHubReport with per-component hub + spoke membership.
    """
    nodes = load_vault() if vault is None else vault

    node_map = {n.stem: n for n in nodes}
    G = G or build(nodes)

    # Weakly-connected components — treats directed edges as undirected
    wccs = list(nx.weakly_connected_components(G))
    wccs.sort(key=len, reverse=True)  # largest first

    components: list[ComponentRecord] = []
    hub_to_spokes: dict[str, list[str]] = {}
    spoke_to_hub: dict[str, str] = {}
    n_singletons = 0
    n_elected = 0

    for idx, comp in enumerate(wccs):
        if len(comp) < min_component_size:
            n_singletons += len(comp)
            continue

        # Elect hub = argmax in-degree within component,
        # tie-broken by total degree, then alphabetically for stability.
        hub = max(
            comp,
            key=lambda n: (
                G.in_degree(n),
                G.degree(n),
                -len(n),   # shorter stem preferred (more general node)
            ),
        )

        spokes = sorted(comp - {hub})
        already_tagged = False
        if hub in node_map:
            tags = node_map[hub].tags
            already_tagged = _TOPO_HUB_TAG in tags or "hub" in tags

        rec = ComponentRecord(
            component_id=idx,
            size=len(comp),
            hub=hub,
            hub_in_degree=G.in_degree(hub),
            hub_total_degree=G.degree(hub),
            spokes=spokes,
            already_hub_tagged=already_tagged,
        )
        components.append(rec)
        hub_to_spokes[hub] = spokes
        for s in spokes:
            spoke_to_hub[s] = hub
        n_elected += 1

    return TopoHubReport(
        n_nodes=G.number_of_nodes(),
        n_edges=G.number_of_edges(),
        n_components=len(wccs),
        n_singletons=n_singletons,
        n_elected=n_elected,
        components=components,
        hub_to_spokes=hub_to_spokes,
        spoke_to_hub=spoke_to_hub,
    )


# ---------------------------------------------------------------------------
# Tag injection
# ---------------------------------------------------------------------------


_TAG_LINE_RE = re.compile(r"^(#\w[\w\-]*)(\s+#[\w\-]+)*\s*$", re.MULTILINE)


def _inject_tag(path: Path, tag: str) -> bool:
    """
    Add `#<tag>` to the first tag line in `path`.
    Returns True if the file was modified.
    """
    text = path.read_text(encoding="utf-8")

    # Skip if already tagged
    if f"#{tag}" in text:
        return False

    # Find first tag line (line made only of #word tokens)
    m = _TAG_LINE_RE.search(text)
    if m:
        old_line = m.group(0)
        new_line = old_line.rstrip() + f" #{tag}"
        updated = text.replace(old_line, new_line, 1)
    else:
        # No tag line found — append after the first heading
        heading_m = re.search(r"^#\s+.+$", text, re.MULTILINE)
        if heading_m:
            end = heading_m.end()
            updated = text[:end] + f"\n\n#{tag}" + text[end:]
        else:
            return False  # Can't inject safely

    path.write_text(updated, encoding="utf-8")
    return True


def write_hub_tags(
    report: TopoHubReport,
    vault: list[VaultNode] | None = None,
    tag: str = _TOPO_HUB_TAG,
    skip_if_already_hub: bool = True,
) -> list[str]:
    """
    Write `#topo-hub` tags to each elected hub node.

    Parameters
    ----------
    report              : from analyse()
    vault               : pre-loaded vault (loaded if None)
    tag                 : tag to inject (default "topo-hub")
    skip_if_already_hub : skip nodes already tagged #hub (default True)

    Returns
    -------
    List of stems that were actually modified.
    """
    nodes = vault or load_vault()
    stem_to_path = {n.stem: n.path for n in nodes}
    modified: list[str] = []

    for rec in report.components:
        if skip_if_already_hub and rec.already_hub_tagged:
            continue
        path = stem_to_path.get(rec.hub)
        if path and _inject_tag(path, tag):
            modified.append(rec.hub)

    return modified
