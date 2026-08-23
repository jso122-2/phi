# agent-context

#hub #command

The workflow command kit — mode shells for how agents operate in this repo.
Defined in `.agent-context/` — read-only for context, agents follow their contracts.

---

## Connections

→ [[HOME]] ← grand central  
→ [[COMMANDS]] — the full command surface (MCP tools + workflow modes)  
→ [[CODE]] — what dev/wire/modular operate on  

---

## Workflow modes

| Command | File | One-liner |
|---|---|---|
| `/talk` | `.agent-context/talk.md` | Strategic discussion — align on direction before building |
| `/explain` | `.agent-context/explain.md` | Plain-language explanation of whatever was asked |
| `/dev` | `.agent-context/dev.md` | Workhorse build mode — write, run, iterate, ship |
| `/modular` | `.agent-context/modular.md` | Raw dev input → clean minimal Python packages |
| `/wire` | `.agent-context/wire.md` | Connect all work — imports, interfaces, pipeline end-to-end |
| `/edit` | `.agent-context/edit.md` | Surgical inline fixes — shape/type/logic bugs |
| `/clean` | `.agent-context/clean.md` | Fix the repo file tree — move, delete, normalise, gitignore |
| `/audit` | `.agent-context/audit.md` | Full system health audit — vault graph + codebase + env |
| `/cairrn [hub] [metric]` | `.agent-context/cairrn.md` | CAIRRN three-layer hub pipeline — Ana-Chi → shard → coherence |

---

## Typical flow

```
/audit     ← health check — know what's broken before you build
  ↓
/explain   ← make a thing understandable in plain words
/talk      ← lock direction
  ↓
/dev       ← build the thing
  ↓
/modular   ← package it cleanly
  ↓
/wire      ← connect everything, imports working, pipeline runs
  ↓
/clean     ← fix the file tree before committing
  ↓
/audit     ← final pass — confirm nothing broke

/explain   ← drop in anywhere a thing needs saying in plain words
/edit      ← surgical fix anywhere in the pipeline
/cairrn    ← run hub metrics through the CAIRRN pipeline at any point
```

---

## MCP execution commands

These are separate from the workflow modes — they call the MCP server directly:

```
/sim /sweep /neg-exp /index /propagate /inject /reset /status /health /test
```

Full catalog → [[COMMANDS]]

---

## Wire checklist (from `/wire`)

- All new modules importable from package root
- `__init__.py` at every package level exports what consumers need
- No circular imports
- Config values pass through function arguments, not globals
- End-to-end smoke test passes

---

## Dev behaviour contract (from `/dev`)

- **Read before write** — always inspect target file first
- **State then act** — one sentence announcing the next action, then do it
- **No scope creep** — only what was agreed in `/talk`
- **Fix broken things** — if an edit causes a linter error, fix it before moving on

---

## Auto-linked

→ [[mcp-server]]
→ [[2025-09-24-134434-2025-09-24t23-44-35-162-10-00]]
→ [[sessions]]
→ [[2025-09-24-134225-2025-09-24t23-42-27-440-10-00]]
→ [[environment]]
→ [[2025-09-03-235146-2025-09-04t09-51-54-358-10-00]]

→ [[2025-09-09-072136-2025-09-09t17-21-36-865-10-00]]
→ [[dev]]

→ [[2025-10-06-150602-2025-10-07t02-07-04-211-11-00]]
→ [[2025-05-28-154122-dawn-test-1]]
→ [[2026-03-09-104500-2026-03-09t21-45-00-844-11-00]]
→ [[README]]
→ [[2025-05-15-081254-2025-05-15t18-22-57-859-10-00]]

→ [[keep]]
→ [[2025-08-09-044150-soot-ash-residue-dynamics-in-dawn]]
→ [[2025-03-03-074553-gti-commands]]
→ [[2025-05-28-224414-2025-05-29t08-44-14-473-10-00]]
→ [[2025-06-08-062357-fresh-termial-instate-gpt]]
→ [[2025-05-19-163744-server-scribble]]

→ [[2025-02-20-075321-docker-and-celery-commands]]
→ [[2025-05-27-104057-visual-suite]]
→ [[2025-06-08-063438-linux-first-checklist-8-6-25]]
→ [[2025-09-19-041208-neofetch]]
→ [[2025-08-18-101454-security]]
→ [[2025-05-15-113345-pretty-code]]

→ [[2025-08-12-011708-a-disiplined-rebillion]]
→ [[2025-12-13-062815-miler-coat-of-arms]]
→ [[2025-12-12-032609-formulas-1212-25]]
→ [[2025-12-13-051108-formulas-13-12-25]]
→ [[2025-12-10-120936-2025-12-10t23-39-19-648-11-00]]
→ [[2025-05-24-025238-dawn-build-sprint-due-8-30-pm-aest]]
