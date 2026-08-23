# sessions — Agent Session Index

#hub #session

Every agent session is logged here as a permanent vault node.
This is the chronological record of how the system was built — the commit log,
but in the graph.

---

## Structure

```
sessions/
└── <YYYY-MM-DD-HHmmss>-<slug>.md    ← one node per session
```

Each node records:
- The user's **prompt** (intent)
- The agent's **thinking** (reasoning summary)
- The **outcome** (what was built/decided)
- **Discovered links** (PSSPPS-detected related nodes)

---

## How sessions are created

The agent calls `/graph-commit` at the end of every session.
This can also fire automatically via the Cursor post-agent hook.

```
/graph-commit <prompt> | <thinking> | <outcome>
```

MCP tool: `graph_commit(prompt, thinking, outcome)`

---

## Why this replaces GitHub

- Zero billing overhead — the vault is local
- Every node is a full context snapshot, not just a diff
- The harmonic index + PSSPPS link sessions to the math and code they touch
- The graph is the documentation, the log, and the map simultaneously

---

## Connections

→ [[HOME]] ← grand central  
→ [[graph]] — graph worker hub  
→ [[psspps]] — semantic link discovery  
→ [[COMMANDS]] — `/graph-commit` slash command

---

## Auto-linked

→ [[2026-07-13-042743-configure-the-obsidian-graph-as-the-hub-buil]]
→ [[2026-07-13-040611-configure-pushes-to-the-obsidian-graph-and-bu]]
→ [[2026-07-13-120800-dawn-physics-scaffold-and-mycelial-layer-context-dump]]
→ [[mcp-server]]
→ [[CODE]]
→ [[2026-01-30-155439-2026-01-31t02-54-40-085-11-00]]

→ [[logger]]
→ [[2026-07-13-095004-cairrnify-the-mcp-server-fix-dom-queue-open]]
→ [[worker]]
→ [[hub-classifier]]
→ [[2026-07-13-102400-temporal-sharding-index-cairrn-aware-ana-chi-hosted]]

→ [[2026-07-13-configure-the-obsidian-graph-as-the-hub-buil]]
→ [[git-log]]
→ [[2026-07-15]]
→ [[2026-01-30-010049-2026-01-30t12-30-27-722-11-00]]

→ [[README]]

→ [[2026-01-15-080152-2026-01-15t21-30-47-349-11-00]]
→ [[2026-07-13-040738-2026-07-13t14-07-38-557-10-00]]
→ [[2025-12-16-065048-the-missle-paradigm]]
→ [[2026-02-01-092009-2026-02-01t20-34-03-112-11-00]]
→ [[2025-05-27-184212-2025-05-28t04-42-14-646-10-00]]
→ [[2026-06-04-124832-2026-06-04t22-48-34-493-10-00]]

→ [[2025-06-06-130633-2025-06-06t23-06-35-516-10-00]]
→ [[2026-01-06-171240-2026-01-07t04-13-12-402-11-00]]
→ [[2026-02-26-132809-2026-02-27t00-28-10-015-11-00]]
→ [[2026-05-02-151007-2026-05-03t01-10-07-853-10-00]]
→ [[2025-10-03-120206-2025-10-03t22-04-36-490-10-00]]
→ [[2026-01-23-060343-2026-01-23t17-03-51-868-11-00]]
