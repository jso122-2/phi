# graph / topo_graph.py

#source #python

> path: graph/topo_graph.py  
> ext: .py  

---

# graph / topo_graph.py


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
  

Defines: build, ComponentRecord, TopoHubReport, analyse, _inject_tag, write_hub_tags, summary

---

## Semantic links

→ [[topo-hub]]
→ [[graph-init]]
→ [[graph-worker]]
→ [[graph-linker]]
→ [[graph]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-tests-test-topo-graph-py]]
→ [[cursor-ingest/2026-08-04-072347-source-graph-linker-md]]
→ [[cursor-ingest/2026-08-04-072347-phi-topology-topo-graph-py]]
→ [[cursor-ingest/2026-08-04-072347-graph-init-py]]
→ [[cursor-ingest/2026-08-04-072347-mcp-server-tools-graph-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
