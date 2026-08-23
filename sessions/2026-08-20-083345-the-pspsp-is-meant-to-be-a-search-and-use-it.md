# Session: 2026-08-20 08:33 UTC

#session #prompt

**Prompt:**

the pspsp is meant to be a search and use it control and modulate the search function to build into the mcp server

---

**Thinking:**

PSSPPS was a library the MCP wrapped with a static 0.5 alpha. Wired it as the MCP search function: live harmonic index modulates perspective_alpha (peaked=local/harmonic, diffuse=global/semantic, cold=0.5). Restored coherence scoring. graph_commit uses the same modulator. Broke a circular import in logger/linker so the pipeline can load.

---

**Outcome:**

psspps_query and find_query now auto-modulate from _harmonic_index. Caller can still pass perspective_alpha to override. 60 tests passed.

---

## Graph links discovered

→ [[mcp-server-tools-search]]
→ [[2026-08-20-081739-how-is-psps-utilised-for-the-mcp-server]]
→ [[mcp-server-tools-harmonic]]
→ [[COMMANDS]]
→ [[mcp-index]]
→ [[psspps-pipeline]]

---

→ [[sessions]] — session index  
→ [[graph]] — graph worker hub  

*Logged by `graph/logger.py` — vault is the hub.*
