# topo-hub — Topological Hub Election (β₀)

#hub #code #graph

Option B hub discovery — hubs emerge from the vault's own link structure,
not from a manual schema.

---

## Algorithm

Build a directed wikilink graph **G** from the vault:

- **Nodes** = vault stems
- **Edges** = wikilinks  `source → target`

Find weakly-connected components (β₀ — the zeroth Betti number, count of
connected components).  Within each component, elect the node with the
highest **in-degree** as hub; all others become spokes.

```python
hubs = {
    comp: max(comp, key=lambda n: (G.in_degree(n), G.degree(n)))
    for comp in nx.weakly_connected_components(G)
    if len(comp) >= min_component_size
}
```

Tie-break: total degree → then shorter stem (more general node wins).

---

## Properties

**Pro:** hubs emerge organically.  Write many notes about one artist → they
naturally become a hub.  No schema maintenance required.

**Con:** a fully-connected vault (code/sim content is dense) collapses to
a single component.  Fragmentation only appears when sparse new clusters
are added (e.g. music notes before they're cross-linked).

**Current state:** vault is a single WCC.  Hub = `index` (in-degree 327).
Fragmentation will emerge as music/artist notes are populated.

---

## MCP tool

```
graph_topo_hubs(
    min_component_size = 2,     # skip singletons
    write_tags         = False, # inject #topo-hub when True
    prefix_filter      = "",    # restrict to e.g. "source/"
)
```

Returns: β₀ count, node/edge counts, top elected hubs by in-degree,
per-hub spoke lists.

---

## Implementation

| File | Role |
|---|---|
| `graph/topo_graph.py` | `build()`, `analyse()`, `write_hub_tags()` |
| `graph/worker.py` | `run_topo_hubs()` |
| `mcp_server/tools/graph.py` | `graph_topo_hubs()` MCP tool |
| `tests/test_topo_graph.py` | 17 unit tests |

---

## Connections

→ [[graph]] — graph worker hub  
→ [[CODE]] — code hub  
→ [[harmonic-index]] — topological hubs feed harmonic injection  
→ [[psspps]] — semantic links complement topological links  
