# AGENTS.md — phi / Reservoir

This file is the canonical operating guide for any Cloud Agent (or local Cursor agent) running in this repository.

---

## Environment

- **Python 3.12**, venv at `/workspace/.venv`
- **MCP server** (`spotify-rip`) is declared in `.cursor/mcp.json` and launched by Cursor automatically. All slash commands route through it.
- **NOTION_TOKEN** must be set as a secret (injected as the env var `NOTION_TOKEN`).

Install (idempotent):

```bash
cd /workspace && python3 -m venv .venv --system-site-packages && .venv/bin/pip install -e ".[dev]" -q
```

Test suite:

```bash
cd /workspace && .venv/bin/pytest
```

---

## Slash commands

All slash commands are handled by the `spotify-rip` MCP server via `run_command`. Never shell them directly.

Full catalog: `/read commands` or `list_commands()`.

Key namespaces:

| Prefix | Purpose |
|---|---|
| `/read <sub>` | Inspect state — index, graph, hub, temporal, forecast, coherence, psspps, vault, etc. |
| `/do <sub>` | Mutate state — sims, propagate, inject, commit, ingest, cairrn, phi, shuffle, bus, etc. |
| `/talk` `/explain` `/dev` `/modular` `/wire` `/edit` `/clean` `/audit` | Workflow modes — call `agent_context(mode="<mode>")`, follow the returned contract exactly |
| `/init` | Reservoir boot sequence — see `reservoir/skills/init/SKILL.md` |

---

## Reservoir skills

The Reservoir is a cognitive memory system. Skills live at `reservoir/skills/<name>/SKILL.md`.

Read the skill file before acting on its trigger. Follow it exactly — no preamble, no narration unless the skill says otherwise.

### Always-on (constitutional layer)

| Skill | Path | Trigger |
|---|---|---|
| `jackson-manifest` | `reservoir/skills/jackson-manifest/SKILL.md` | **Always** — read before every response. Governs tone, posture, anti-narcissist guardrails, passive curriculum accumulation, and engagement mode. |

### Boot & index

| Skill | Path | Trigger |
|---|---|---|
| `init` | `reservoir/skills/init/SKILL.md` | Literal string `/init` anywhere in message. Boots the reservoir silently. |
| `autonomous-index` | `reservoir/skills/autonomous-index/SKILL.md` | Session start via `/init`. Runtime operating protocol for the inference graph against Notion. |
| `inference-graph` | `reservoir/skills/inference-graph/SKILL.md` | Any shard retrieval. Declares shard relationships, traversal order, and edge weights. |
| `edge-address-index` | `reservoir/skills/edge-address-index/SKILL.md` | External environment needs to query edges, resolve shard page addresses, or declare new edges. |
| `user-index` | `reservoir/skills/user-index/SKILL.md` | Jackson asks reflective questions: "what have I been circling on", "where did I leave that thread", "show me my reservoir", "what does my thinking look like". |

### Shards (loaded by `/init`)

| Skill | Path | Trigger |
|---|---|---|
| `recursive-thought` | `reservoir/skills/recursive-thought/SKILL.md` | Jackson examining a prior thought, returning to a thread, or thinking about his own thinking. Phrases: "I keep coming back to", "I said before", "where did I leave", "have I already". |
| `valence-high` | `reservoir/skills/valence-high/SKILL.md` | Prompts with strong emotional charge — grief, longing, frustration, elation, defiance, vulnerability. Defined by register, not subject. |
| `dawn-fragments` | `reservoir/skills/dawn-fragments/SKILL.md` | Jackson thinking about, designing, pitching, debugging, or reflecting on DAWN — the distributed consciousness OS. |
| `schema-fragments` | `reservoir/skills/schema-fragments/SKILL.md` | Schema (self-published essay series), specific issue numbers, the tunnel rave piece, "1 of 2", the broader essay project. |
| `novel-fragments` | `reservoir/skills/novel-fragments/SKILL.md` | The novel — fragmented present-tense, 2300, character Ben, intended as a gift. Quieter register. |

### Protocols

| Skill | Path | Trigger |
|---|---|---|
| `backfill` | `reservoir/skills/backfill/SKILL.md` | "backfill", "backfill shards", or "populate the reservoir". One-shot bootstrap from conversation history. |

---

## Key systems

| System | Entry point |
|---|---|
| Autonomous graph worker | `graph/` |
| PSSPPS semantic search | `psspps/` |
| Harmonic index | `harmonic-index.md` + MCP tools |
| MCP server tools | `mcp_server/` |
| Sims & attractors | `sims/` |
| Phi pipeline | `phi/` |
| Temporal index | `temporal-index.md` + MCP tools |

---

## Rules

- Never put secrets, tokens, or passwords in code, comments, or chat.
- Slash commands always go through the MCP server — never `Shell` them.
- Follow the `jackson-manifest` skill on every response.
- When a reservoir shard is active, surface Jackson's own prompts — not summaries.
