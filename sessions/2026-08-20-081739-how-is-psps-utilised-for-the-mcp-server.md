# Session: 2026-08-20 08:17 UTC

#session #prompt

**Prompt:**

how is psps utilised for the mcp server

---

**Thinking:**

Mapped every MCP-server call into psspps: search tools wrap pipeline/find; graph_commit uses run_psspps for wikilinks; graph_link uses scorer; graph_traverse uses embedder/retriever/traverser; server warmup caches the corpus; init_check imports psspps modules; DOM house wire owns the search tools.

---

**Outcome:**

PSSPPS is a library the MCP server wraps. Direct tools: psspps_query and find_query. Indirect: graph_commit, graph_link, graph_traverse, graph_status (O_n cache). Live harmonic activations are the perspective lens.

---

## Graph links discovered

→ [[mcp-server-tools-search]]
→ [[2026-08-04-072347-mcp-server-tools-graph-py]]
→ [[psspps-index]]
→ [[2026-08-04-072347-source-mcp-server-tools-search-md]]
→ [[2026-08-04-072347-mcp-server-tools-search-py]]
→ [[2026-08-04-072347-source-graph-init-md]]

---

→ [[sessions]] — session index  
→ [[graph]] — graph worker hub  

*Logged by `graph/logger.py` — vault is the hub.*
