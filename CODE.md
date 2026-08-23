# CODE — Codebase Hub

#hub #code

Central station for the Python implementation of this project.
Every module here has a mathematical counterpart in [[MATH]].

---

## Lines through this station

→ [[HOME]] ← grand central  
→ [[sims]] — `sims/attractors.py`, `sims/harmonic.py`  
→ [[workers]] — `workers/base.py`  
→ [[mcp-server]] — `mcp_server/server.py` — 11 MCP tools  
→ [[psspps]] — `psspps/` — RAG pipeline with harmonic perspective  
→ [[environment]] — `environment.yml`, `pyproject.toml`  

→ [[MATH]] — the mathematics powering this code  
→ [[COMMANDS]] — how to invoke all of the above  

---

## Module map

```
Spotify-Rip/
├── sims/
│   ├── __init__.py
│   ├── attractors.py     ← double-well, neg-exp, trajectory engine
│   └── harmonic.py       ← HarmonicIndex, HarmonicShard, LocalPropagator
├── workers/
│   ├── __init__.py
│   └── base.py           ← Worker, SimWorker, BatchWorker
├── psspps/
│   ├── __init__.py
│   ├── retriever.py      ← vault document loader + parser
│   ├── scorer.py         ← TF-IDF + harmonic perspective scoring
│   ├── router.py         ← pre/post RAG routing inference
│   └── pipeline.py       ← run_psspps() orchestrator
├── mcp_server/
│   ├── __init__.py
│   ├── server.py         ← FastMCP server, 11 tools
│   └── __main__.py
├── tests/
│   ├── test_attractors.py
│   ├── test_harmonic.py
│   └── test_workers.py
├── Scribble/             ← human notes (read-only for agents)
├── environment.yml       ← mamba env definition
├── pyproject.toml        ← build + entry points
├── HOME.md               ← this vault's Grand Central
└── .cursor/
    ├── mcp.json          ← hooks MCP server to Cursor
    └── rules/            ← agent rules + slash commands
```

---

## Data flow

```
User /sim x0
     │
     ▼
mcp_server/server.py   (receives MCP call)
     │
     ▼
sims/attractors.py     (runs gradient descent)
     │  returns Trajectory
     ▼
sims/harmonic.py       (inject final position → nearest shard)
     │  activates HarmonicShard          ← thread-safe via RLock
     ▼
HarmonicIndex          (propagate wave across ring)

User /psspps <query>
     │
     ▼
psspps/router.py       (should we retrieve?)
     │
     ▼
psspps/retriever.py    (load vault docs)
     │
     ▼
psspps/scorer.py       (TF-IDF semantic + harmonic perspective)
     │  uses HarmonicIndex.activation_vector()
     ▼
psspps/pipeline.py     (rank + PSPSPSResult)
```

---

## Entry points

| Command | What runs |
|---|---|
| `spotify-rip-mcp` | `mcp_server.server:main` via pyproject.toml console script |
| `python -m mcp_server.server` | same, manual |
| `mamba run -n spotify-rip python -m mcp_server.server` | from any shell |
| `/status` in Cursor | calls `system_status` MCP tool |

---

## Testing

```
/test           → pytest -v --tb=short
/test --cov     → pytest + coverage on sims/ workers/
```

---

## Auto-linked

→ [[sessions]]
→ [[live-state]]
→ [[attractors]]
→ [[graph]]
→ [[agent-context]]
→ [[git-log]]

→ [[hub-classifier]]
→ [[cairrn]]
→ [[2026-07-13-042743-configure-the-obsidian-graph-as-the-hub-buil]]
→ [[temporal-index]]

→ [[2026-07-13-102400-temporal-sharding-index-cairrn-aware-ana-chi-hosted]]
→ [[README]]
→ [[logger]]
→ [[2026-07-13-configure-the-obsidian-graph-as-the-hub-buil]]
→ [[2026-07-13-integrate-ana-chi-constant-modulate-cairrn-stable-states]]
→ [[worker]]

→ [[ana-chi]]
→ [[2026-07-13-095004-cairrnify-the-mcp-server-fix-dom-queue-open]]

→ [[harmonic-index]]
→ [[lambert-w]]
→ [[2026-07-13-040611-configure-pushes-to-the-obsidian-graph-and-bu]]

→ [[cursor-skills]]
→ [[config]]
→ [[mcp-server-tools-cairrn]]
→ [[scratch]]
