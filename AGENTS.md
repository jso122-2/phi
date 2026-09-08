# Agent contract

Vault retrieval is an MCP tool call, not a shell one-liner.

## Spawn protocol (mandatory — enforced by pre-hook)

Every agent context window **must** begin with these two steps in order.
The `spawn_gate` pre-hook enforces this: calling any substantive tool before
`init_check()` raises a `HookViolation` and returns `session_not_initialized`.

### Step 1 — `/init`

```
init_check()
```

Opens the session gate, writes `sessions/live-init.md` (harmonic state,
last session summary, boot status), and emits the file content to the MCP
stderr channel.  The tool result includes a `spawn_context` field with the
full `live-init.md` content so the agent gets it directly.

### Step 2 — `/read` (automatic)

The `spawn_gate` hook fires on the **first** tool call after spawn.  It:

1. Verifies the gate is open (i.e. `init_check()` was called).
2. Reads `sessions/live-init.md` and `sessions/live-context.md`.
3. Emits both under `[SPAWN:init]` / `[SPAWN:read]` banners on stderr.
4. Marks the spawn sequence complete (fires exactly once per process).

The agent does **not** need to call a separate read command — the hook
emits the context automatically.  However, agents should read `spawn_context`
from the `init_check()` result to orient themselves before any other tool.

### Phase 2 — `[coherence] ready`

After spawn, a background PSSPPS query runs.  When it completes, the hook
emits `[coherence] ready` on stderr.  Read `[[live-context]]` at that point
for the full retrieval results and coherence queue.

---

## Search (required)

Call the **phi** MCP server:

- `find_query(query, mode="pericles")` — exact vault retrieval (Pericles funnel)
- `psspps_query(query, top_k=3)` — perspective-blended RAG

Do not run `python -c` / `psspps.find.run_find` / `run_psspps` ad hoc. The same bus tasks run in-process when the mmap worker is down.

Phi playback tools on the same server: `gemini_clip`, `phi_enqueue`, `phi_queue`.
Race-condition tools: `phi_watchdog()` — Pericles/Euler watchdog state.

## Cursor Cloud specific instructions

Cloud Agents do not inherit laptop `~/.cursor/mcp.json`. Attach stdio MCP **phi**:

| Field | Value |
|---|---|
| name | `phi` |
| command | `python3` |
| args | `["-m", "mcp_server.cloud"]` |
| env | `PYTHONPATH=/workspace`, `PYTHONUNBUFFERED=1` |

UI: [Cloud Agents MCP dropdown](https://cursor.com/agents). After attach, tools appear as the `phi` namespace (for example `phi-find_query`). If that namespace is missing, stop and tell the operator to add the server — do not fall back to ad-hoc Python.

Repo files: `.cursor/mcp.json` (stdio spec), `mcp_server/cloud.py` (entrypoint), `mcp_server/_spawn_gate.py` (spawn protocol).
