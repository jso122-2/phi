# mcp-server

#code #command

The MCP server — exposes all sims and workers as tools that Cursor (or any MCP host) can call directly.

---

## Connections

→ [[CODE]] ← code hub  
→ [[HOME]] ← grand central  
→ [[COMMANDS]] — the slash commands that invoke these tools  
→ [[sims]] — tools call into sims functions  
→ [[workers]] — tools use Worker/BatchWorker  
→ [[harmonic-index]] — shared `_harmonic_index` lives for server lifetime  
→ [[attractors]] — double-well and neg-exp tools  
→ [[live-state]] — vault hub backwards channel (written after every mutating call)  

---

## Registration

Cursor reads `.cursor/mcp.json` on startup:

```json
{
  "mcpServers": {
    "spotify-rip": {
      "command": "mamba",
      "args": ["run", "-n", "spotify-rip", "--no-capture-output",
               "python", "-m", "mcp_server.server"],
      "cwd": "/Users/jacksonmacleod/Documents/Spotify-Rip"
    }
  }
}
```

The server speaks **MCP stdio protocol**.  
It must be restarted from Cursor settings if `server.py` changes.

---

## Cloud Agents — `phi` stdio MCP

Cloud Agents do **not** load laptop `~/.cursor/mcp.json`. Vault search is a first-class Cloud MCP, not an ad-hoc Python call.

Attach custom stdio MCP **phi** (dashboard MCP dropdown or API `mcpServers`):

```json
{
  "name": "phi",
  "type": "stdio",
  "command": "python3",
  "args": ["-m", "mcp_server.cloud"]
}
```

| Tool | What it does |
|---|---|
| `find_query` | Pericles `/find` over the vault |
| `psspps_query` | Perspective RAG |
| `gemini_clip` / `phi_enqueue` / `phi_queue` | Phi library actions |
| `phi_watchdog` | Pericles/Euler race-condition watchdog state |
| `session_audit` | Runtime MCP call ledger — family breakdown, violations, sequence |

`mcp_server.cloud` opens the session gate at spawn. If the mmap/celery worker is absent, `submit_and_maybe_wait` runs the registered bus task **in-process** (`source: "in-process"`).

Repo spec: `.cursor/mcp.json` · `mcp_server/cloud.py`

---

## Tool catalog

| Tool | MCP name | House | Slash command |
|---|---|---|---|
| Environment check | `init_check` | clean | `/health` |
| Double-well sim | `double_well_sim` | talk | `/sim <x0>` |
| Neg-exp iteration | `neg_exp_sim` | talk | `/neg-exp <x0>` |
| Sweep initial conditions | `sweep_attractors` | talk | `/sweep` |
| Harmonic index state | `harmonic_index_state` | modular | `/index` |
| Propagate index | `harmonic_propagate` | modular | `/propagate [steps]` |
| Hub state | `hub_state` | modular | — |
| Inject activation | `harmonic_inject` | edit | `/inject <shard> <value>` |
| Hub inject | `hub_inject` | edit | — |
| Reset index | `harmonic_reset` | clean | `/reset` |
| Run tests | `run_tests` | dev | `/test` |
| PSSPPS query | `psspps_query` | wire | — |
| System health | `system_status` | clean | `/status` |
| DOM queue state | `dom_queue_state` | clean | — |
| List hooks | `list_hooks` | clean | — |
| Register hook | `register_hook` | clean | — |
| Vault hub state | `vault_hub_state` | clean | — |

---

## Spawn sequence

On process start, three singletons are created in order:

```python
_harmonic_index = HarmonicIndex(n_harmonics=8, coupling=0.15)   # shared state
_dom_queue      = spawn_houses()                                  # 6 DOM houses opened
_vault_hub      = open_vault_hub(project_root)                    # backwards channel to vault
```

Every tool call passes through `_dom_queue.gate(tool_name)` before executing.  
Every mutating tool call pushes state back to `Spotify-rip/live-state.md` via `_vault_hub`.

---

## DOM Request Queue — 6 houses

| House | Purpose | Tools |
|---|---|---|
| `talk` | Explore the attractor landscape | `double_well_sim`, `neg_exp_sim`, `sweep_attractors` |
| `dev` | Build and validate | `run_tests` |
| `modular` | Shape harmonic structure | `harmonic_index_state`, `harmonic_propagate`, `hub_state` |
| `wire` | Connect knowledge (PSSPPS) | `psspps_query` |
| `edit` | Surgical injection | `harmonic_inject`, `hub_inject` |
| `clean` | Reset and verify | `harmonic_reset`, `init_check`, `system_status`, `dom_queue_state`, `list_hooks`, `register_hook`, `vault_hub_state` |

---

## Vault Hub — backwards channel

`mcp_server/vault_hub.py` enforces a backwards write from MCP → Obsidian vault:

```
Forward:   Spotify-rip/*.md  →  PSSPPS retriever  →  MCP tool results
Backwards: MCP tool results  →  VaultHub.push_*() →  Spotify-rip/live-state.md
```

After every mutating call (`/sim`, `/sweep`, `/propagate`, `/inject`, `/reset`, `/status`),
`live-state.md` is rewritten with the current harmonic state, last sim result,
and DOM queue snapshot.  Obsidian picks it up instantly via its file watcher.

→ See [[live-state]] for the current snapshot.

---

## Shared state

```python
_harmonic_index = HarmonicIndex(n_harmonics=8, coupling=0.15)
_dom_queue      = spawn_houses()     # 6 BMAD-trust-gated serialising lanes
_vault_hub      = open_vault_hub(…)  # writes Spotify-rip/live-state.md
```

---

## Starting manually

```bash
mamba activate spotify-rip
spotify-rip-mcp          # via console_scripts entry point

# or
python -m mcp_server.server
```

---

## Auto-linked

→ [[graph]]
→ [[agent-context]]
→ [[sessions]]
→ [[2026-07-13-042743-configure-the-obsidian-graph-as-the-hub-buil]]
→ [[2026-07-13-040611-configure-pushes-to-the-obsidian-graph-and-bu]]
→ [[psspps]]

→ [[2026-07-13-095004-cairrnify-the-mcp-server-fix-dom-queue-open]]
→ [[2026-07-13-102400-temporal-sharding-index-cairrn-aware-ana-chi-hosted]]
→ [[cairrn]]

→ [[worker]]
→ [[hub-classifier]]
→ [[temporal-index]]
→ [[2026-07-13-integrate-ana-chi-constant-modulate-cairrn-stable-states]]
→ [[logger]]

→ [[git-log]]
→ [[README]]

→ [[2026-07-13-configure-the-obsidian-graph-as-the-hub-buil]]
→ [[MATH]]
→ [[cursor-skills]]

→ [[mcp-server-server]]
→ [[mcp-server-vault-hub]]
→ [[mcp-server-tools-system]]
→ [[mcp-index]]
