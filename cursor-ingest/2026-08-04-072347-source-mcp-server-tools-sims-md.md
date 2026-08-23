# source / mcp-server-tools-sims.md

#doc #md

> path: source/mcp-server-tools-sims.md  
> ext: .md  

---

# mcp_server/tools/sims

#code #module #mcp-server #code

> source_path: mcp_server/tools/sims.py  
> package: mcp_server  
> module: mcp_server/tools/sims  
> hub: CODE  
> created_ts:   

---

**Package:** `mcp_server`  
**Module:** `mcp_server/tools/sims`  
**Source:** `mcp_server/tools/sims.py`

Simulation tools: double_well, neg_exp, sweep, ana_chi.

## API

- `def double_well_sim` — Run a double-well attractor simulation from starting point x0.
- `def neg_exp_sim` — Iterate f(x) = −eˣ from starting point x0.
- `def sweep_attractors` — Sweep initial conditions across [x0_min, x0_max] for the double-well sim.
- `def ana_chi_sim` — Run gradient descent on the 5-basin Ana-Chi potential from chi_0.
- `def ana_chi_state` — Return the current Ana-Chi state of the harmonic index.

## Internal imports

`mcp_server._gate`, `mcp_server._state`, `sims.ana_chi`, `sims.attractors`

---

## Semantic links

→ [[sims]]
→ [[sims]]
→ [[COMMANDS]]
→ [[CODE]]
→ [[CODE]]

## Related notes

→ [[source/sims-attractors]]
→ [[source/sims-ana-chi]]
→ [[source/mcp-server-dom-queue]]
→ [[source/mcp-server-tools-harmonic]]
→ [[source/mcp-server-tools-prefeed-shuffle]]

— import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[mcp-server-main]]
→ [[mcp-index]]
→ [[mcp-server-tools-init]]
→ [[mcp-server-server]]
→ [[mcp-server-tools-forecast]]
→ [[mcp-server-tools-system]]

---

## Semantic links

→ [[mcp-server-main]]
→ [[mcp-server-tools-sims]]
→ [[mcp-server-server]]
→ [[mcp-server-tools-modular]]
→ [[mcp-server-tools-system]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-system-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-main-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-modular-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-init-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-state-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
