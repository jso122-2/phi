# graph — Autonomous Graph Worker Hub

#hub #code #command

The vault is the hub.  This node is the control centre for the autonomous
graph maintenance worker that keeps the Obsidian knowledge graph clean,
linked, and self-populating.

**GitHub is not used.** Session push = `graph_commit`. Code push = `git` to `.hub.git`.

---

## What the graph worker does

```
graph/
├── node.py           VaultNode dataclass — read, parse, write .md files
├── linker.py         PSSPPS-powered semantic auto-linker
├── worker.py         clean, nest, link, status operations
├── logger.py         session logger — every prompt → a node
├── ingestion.py      IngestionPipeline — embed, link, classify, write docs
└── hub_classifier.py keyword + link-topology hub classifier
```

```
workers/
├── base.py           Worker / SimWorker / BatchWorker / WorkerResult / Status
├── cerberus.py       three-head bind guard (ceb_1, ceb_2, factorial escalation)
├── oesophagus.py     file ingestion pipeline (scan → sentinel → transform → vault)
└── sentinel.py       sensitive-file gate (extension block, path quarantine, redaction)
```

### Operations

| Operation | What it does | MCP tool |
|---|---|---|
| **commit** | Write this session (prompt + thinking + outcome) as a vault node | `graph_commit` |
| **clean** | Find orphan nodes and dead wikilinks (resolves Obsidian path-prefix links) | `graph_clean` |
| **link** | Auto-link semantically related nodes via PSSPPS | `graph_link` |
| **nest** | Suggest semantic hub assignments for un-tagged nodes | `graph_nest` |
| **status** | Full graph health snapshot | `graph_status` |
| **traverse** | Walk the vault from a seed by semantic adjacency | `graph_traverse` |
| **topo_hubs** | Elect hubs via β₀ weakly-connected components (Option B) | `graph_topo_hubs` |
| **ingest** | Oesophagus pipeline: directory → vault nodes | `graph_ingest` |
| **ingest_source** | Ingest Python source modules into vault as nodes | `graph_ingest_source` |
| **sync_manifest** | Pulse hubs from an ingest manifest into the index | `graph_sync_manifest` |
| **track** | Usage ledger: used / accessed / amended → git hot-set | `graph_track_state` |
| **track_sync** | Apply heat to `.gitignore` + git index (no commit) | `graph_track_sync` |

### Graph health (current)

| Metric | Value |
|---|---|
| nodes | 482 |
| dead links | 0 |
| orphans | 0 |
| session nodes | 16 |
| semantic hubs | CODE, COMMANDS, HOME, MATH, agent-context |
| last audit | 2026-08-04 |
| tagged (routable) | 63 hub-tagged nodes |

---

## The session node format

Every agent session is logged as `sessions/<timestamp>-<slug>.md`:

```markdown
# Session: 2026-07-13 12:00 UTC

#session #prompt

**Prompt:** ...
**Thinking:** ...
**Outcome:** ...

## Graph links discovered
→ [[harmonic-index]]
→ [[psspps]]
```

---

## The push model

Session persistence (every agent turn's outcome) is MCP:

```
/graph-commit <prompt> | <thinking> | <outcome>
```

Code persistence (when the user asks to commit) is git to `Spotify-rip/.hub.git`.
Same vault, two channels — not substitutes. GitHub is not used.

---

## Auto-link mechanism

`graph/linker.py` runs TF-IDF semantic scoring (via `psspps/scorer.py`)
across the full vault.  Any pair of nodes with cosine similarity > 0.12 gets
a wikilink injected under an `## Auto-linked` section — separate from
human-authored content, auditable, removable.

---

## Connections

→ [[HOME]] ← grand central  
→ [[CODE]] — sibling modules  
→ [[psspps]] — provides the semantic scoring engine  
→ [[harmonic-index]] — provides the perspective activations  
→ [[sessions]] — session node index  
→ [[COMMANDS]] — `/graph-*` slash commands  

→ [[2026-07-13-042743-configure-the-obsidian-graph-as-the-hub-buil]]
→ [[2026-07-13-040611-configure-pushes-to-the-obsidian-graph-and-bu]]
→ [[2026-07-13-120800-dawn-physics-scaffold-and-mycelial-layer-context-dump]]
→ [[mcp-server]]
→ [[2025-08-09-023626-mycelium-note-gpt-scribble]]
→ [[2025-05-26-141815-semantic-feild-formule]]

→ [[worker]]
→ [[logger]]
→ [[2026-07-13-095004-cairrnify-the-mcp-server-fix-dom-queue-open]]
→ [[hub-classifier]]

→ [[2026-07-13-configure-the-obsidian-graph-as-the-hub-buil]]
→ [[2026-07-13-102400-temporal-sharding-index-cairrn-aware-ana-chi-hosted]]
→ [[README]]
→ [[git-log]]


→ [[workers]]
→ [[attractors]]
→ [[2026-07-13-integrate-ana-chi-constant-modulate-cairrn-stable-states]]
→ [[temporal-index]]

→ [[graph-init]]
→ [[graph-logger]]
→ [[mcp-server-tools-graph]]
→ [[graph-worker]]
→ [[graph-node]]
→ [[graph-index]]
